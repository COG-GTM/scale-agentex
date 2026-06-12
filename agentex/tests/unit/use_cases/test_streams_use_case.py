"""
Unit tests for StreamsUseCase — stream operations for real-time SSE communication.
All repositories and services are mocked with AsyncMock.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from src.domain.entities.task_stream_events import (
    TaskStreamConnectedEventEntity,
    TaskStreamErrorEventEntity,
)
from src.domain.use_cases.streams_use_case import StreamsUseCase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stream_repository():
    repo = AsyncMock()
    repo.cleanup_stream = AsyncMock()
    repo.get_stream_tail_id = AsyncMock(return_value="0-0")
    # read_messages is an async generator, not a coroutine — use MagicMock so
    # calling it returns the side_effect result directly (not wrapped in a coro).
    repo.read_messages = MagicMock()
    return repo


@pytest.fixture
def mock_task_service():
    return AsyncMock()


@pytest.fixture
def mock_environment_variables():
    env = Mock()
    env.SSE_KEEPALIVE_PING_INTERVAL = 15
    return env


@pytest.fixture
def streams_use_case(
    mock_stream_repository, mock_task_service, mock_environment_variables
):
    return StreamsUseCase(
        stream_repository=mock_stream_repository,
        task_service=mock_task_service,
        environment_variables=mock_environment_variables,
    )


# ---------------------------------------------------------------------------
# Helpers — async generator factories for mock_stream_repository.read_messages
# ---------------------------------------------------------------------------


def _gen_events(*events):
    """Return a side_effect callable that yields the given (id, dict) tuples."""

    async def _gen(**kwargs):
        for item in events:
            yield item

    return _gen


async def _gen_empty(**kwargs):
    """Async generator that yields nothing."""
    return
    yield  # noqa: F841


async def _gen_cancel(**kwargs):
    """Async generator that immediately raises CancelledError."""
    raise asyncio.CancelledError()
    yield  # noqa: F841


# ---------------------------------------------------------------------------
# read_messages
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestReadMessages:
    async def test_yields_validated_events(
        self, streams_use_case, mock_stream_repository
    ):
        """read_messages should yield (id, entity) for each valid stream message."""
        mock_stream_repository.read_messages.side_effect = _gen_events(
            ("1-0", {"type": "connected", "taskId": "task-1"}),
        )

        results = []
        async for msg_id, entity in streams_use_case.read_messages(topic="task:task-1"):
            results.append((msg_id, entity))

        assert len(results) == 1
        assert results[0][0] == "1-0"
        assert isinstance(results[0][1], TaskStreamConnectedEventEntity)

    async def test_skips_invalid_events(self, streams_use_case, mock_stream_repository):
        """Invalid stream data should be silently skipped (logged warning)."""
        mock_stream_repository.read_messages.side_effect = _gen_events(
            ("1-0", {"bad": "data"}),
        )

        results = []
        async for msg_id, entity in streams_use_case.read_messages(topic="t"):
            results.append((msg_id, entity))

        assert len(results) == 0

    async def test_passes_parameters_through(
        self, streams_use_case, mock_stream_repository
    ):
        """read_messages should forward topic, last_id, timeout_ms, count to repo."""
        mock_stream_repository.read_messages.side_effect = _gen_empty

        async for _ in streams_use_case.read_messages(
            topic="t", last_id="5-0", timeout_ms=1000, count=5
        ):
            pass

        mock_stream_repository.read_messages.assert_called_once_with(
            topic="t",
            last_id="5-0",
            timeout_ms=1000,
            count=5,
        )

    async def test_yields_multiple_events(
        self, streams_use_case, mock_stream_repository
    ):
        """Multiple valid events should all be yielded."""
        mock_stream_repository.read_messages.side_effect = _gen_events(
            ("1-0", {"type": "connected", "taskId": "t1"}),
            ("2-0", {"type": "error", "message": "oops"}),
        )

        results = []
        async for msg_id, entity in streams_use_case.read_messages(topic="t"):
            results.append((msg_id, entity))

        assert len(results) == 2
        assert isinstance(results[0][1], TaskStreamConnectedEventEntity)
        assert isinstance(results[1][1], TaskStreamErrorEventEntity)

    async def test_valid_after_invalid(self, streams_use_case, mock_stream_repository):
        """Valid events after invalid ones should still be yielded."""
        mock_stream_repository.read_messages.side_effect = _gen_events(
            ("1-0", {"bad": "data"}),
            ("2-0", {"type": "connected", "taskId": "t1"}),
        )

        results = []
        async for msg_id, entity in streams_use_case.read_messages(topic="t"):
            results.append((msg_id, entity))

        assert len(results) == 1
        assert results[0][0] == "2-0"


# ---------------------------------------------------------------------------
# cleanup_stream
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestCleanupStream:
    async def test_delegates_to_repository(
        self, streams_use_case, mock_stream_repository
    ):
        await streams_use_case.cleanup_stream("task:abc")
        mock_stream_repository.cleanup_stream.assert_awaited_once_with("task:abc")

    async def test_propagates_exception(self, streams_use_case, mock_stream_repository):
        mock_stream_repository.cleanup_stream.side_effect = RuntimeError("redis down")
        with pytest.raises(RuntimeError, match="redis down"):
            await streams_use_case.cleanup_stream("task:abc")


# ---------------------------------------------------------------------------
# stream_task_events — these tests use CancelledError to exit the infinite loop
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestStreamTaskEvents:
    async def test_raises_when_no_id_or_name(self, streams_use_case):
        """Must raise ValueError when neither task_id nor task_name is provided."""
        with pytest.raises(
            ValueError, match="Either task_id or task_name must be provided"
        ):
            async for _ in streams_use_case.stream_task_events():
                pass

    async def test_resolves_task_id_from_name(
        self, streams_use_case, mock_task_service, mock_stream_repository
    ):
        """When only task_name is given, the use case should look up the task."""
        mock_task_service.get_task.return_value = Mock(id="resolved-id")
        mock_stream_repository.read_messages.side_effect = _gen_cancel

        results = []
        async for item in streams_use_case.stream_task_events(task_name="my-task"):
            results.append(item)

        mock_task_service.get_task.assert_awaited_once_with(name="my-task")
        # First (and only) item should be the connected event with the resolved ID
        assert len(results) >= 1
        assert '"connected"' in results[0]
        assert '"resolved-id"' in results[0]

    async def test_emits_connected_event_first(
        self, streams_use_case, mock_stream_repository
    ):
        """First yielded SSE payload must be a 'connected' event."""
        mock_stream_repository.read_messages.side_effect = _gen_cancel

        gen = streams_use_case.stream_task_events(task_id="task-42")
        try:
            first = await gen.__anext__()

            assert "data:" in first
            assert '"connected"' in first
            assert '"task-42"' in first
        finally:
            await gen.aclose()

    async def test_yields_message_data_then_stops(
        self, streams_use_case, mock_stream_repository
    ):
        """Messages from read_messages should be forwarded as SSE data lines."""
        call_count = 0

        async def fake_read(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield ("2-0", {"type": "connected", "taskId": "t1"})
            else:
                raise asyncio.CancelledError()

        mock_stream_repository.read_messages.side_effect = fake_read

        results = []
        async for item in streams_use_case.stream_task_events(task_id="t1"):
            results.append(item)

        # First item = connected event, second = the yielded message data
        assert len(results) >= 2
        assert "data:" in results[1]

    async def test_emits_error_event_on_inner_exception(
        self, streams_use_case, mock_stream_repository
    ):
        """Non-CancelledError exceptions inside the loop should yield an error event."""
        call_count = 0

        async def fake_read(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            raise asyncio.CancelledError()
            yield  # noqa: F841

        mock_stream_repository.read_messages.side_effect = fake_read

        results = []
        async for item in streams_use_case.stream_task_events(task_id="t1"):
            results.append(item)

        error_events = [r for r in results if '"error"' in r]
        assert len(error_events) >= 1
        assert "boom" in error_events[0]

    async def test_cleanup_called_on_cancel(
        self, streams_use_case, mock_stream_repository
    ):
        """cleanup_stream should be called when the generator finishes via cancel."""
        mock_stream_repository.read_messages.side_effect = _gen_cancel

        results = []
        async for item in streams_use_case.stream_task_events(task_id="t1"):
            results.append(item)

        mock_stream_repository.cleanup_stream.assert_awaited_once_with("task:t1")

    async def test_snapshots_stream_tail_on_entry(
        self, streams_use_case, mock_stream_repository
    ):
        """get_stream_tail_id should be called once on entry to snapshot the cursor."""
        mock_stream_repository.read_messages.side_effect = _gen_cancel

        results = []
        async for item in streams_use_case.stream_task_events(task_id="t1"):
            results.append(item)

        mock_stream_repository.get_stream_tail_id.assert_awaited_once_with("task:t1")
