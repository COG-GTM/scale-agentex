"""
Unit tests for CheckpointsUseCase — checkpoint management for LangGraph.
All repositories are mocked with AsyncMock.
"""

from unittest.mock import AsyncMock

import pytest
from src.domain.use_cases.checkpoints_use_case import CheckpointsUseCase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_checkpoint_repository():
    return AsyncMock()


@pytest.fixture
def checkpoints_use_case(mock_checkpoint_repository):
    return CheckpointsUseCase(checkpoint_repository=mock_checkpoint_repository)


# ---------------------------------------------------------------------------
# get_tuple
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetTuple:
    async def test_returns_checkpoint_data(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        expected = {
            "thread_id": "t1",
            "checkpoint_ns": "",
            "checkpoint_id": "cp1",
            "parent_checkpoint_id": None,
            "checkpoint": {"channel_versions": {}},
            "metadata": {},
            "blobs": [],
            "pending_writes": [],
        }
        mock_checkpoint_repository.get_tuple.return_value = expected

        result = await checkpoints_use_case.get_tuple(thread_id="t1")

        mock_checkpoint_repository.get_tuple.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns="",
            checkpoint_id=None,
        )
        assert result == expected

    async def test_returns_none_when_not_found(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        mock_checkpoint_repository.get_tuple.return_value = None

        result = await checkpoints_use_case.get_tuple(thread_id="nonexistent")
        assert result is None

    async def test_passes_checkpoint_ns_and_id(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        mock_checkpoint_repository.get_tuple.return_value = None

        await checkpoints_use_case.get_tuple(
            thread_id="t1",
            checkpoint_ns="ns1",
            checkpoint_id="cp42",
        )

        mock_checkpoint_repository.get_tuple.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns="ns1",
            checkpoint_id="cp42",
        )


# ---------------------------------------------------------------------------
# put
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestPut:
    async def test_delegates_to_repository(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        checkpoint = {"state": "value"}
        metadata = {"step": 1}
        blobs = [{"channel": "ch", "version": "1", "type": "t", "blob": b"data"}]

        await checkpoints_use_case.put(
            thread_id="t1",
            checkpoint_ns="ns",
            checkpoint_id="cp1",
            parent_checkpoint_id="cp0",
            checkpoint=checkpoint,
            metadata=metadata,
            blobs=blobs,
        )

        mock_checkpoint_repository.put.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns="ns",
            checkpoint_id="cp1",
            parent_checkpoint_id="cp0",
            checkpoint=checkpoint,
            metadata=metadata,
            blobs=blobs,
        )

    async def test_with_none_parent(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        await checkpoints_use_case.put(
            thread_id="t1",
            checkpoint_ns="",
            checkpoint_id="cp1",
            parent_checkpoint_id=None,
            checkpoint={},
            metadata={},
            blobs=[],
        )

        call_kwargs = mock_checkpoint_repository.put.call_args.kwargs
        assert call_kwargs["parent_checkpoint_id"] is None


# ---------------------------------------------------------------------------
# put_writes
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestPutWrites:
    async def test_delegates_to_repository(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        writes = [
            {"task_id": "w1", "idx": 0, "channel": "ch", "type": "t", "blob": b"x"}
        ]

        await checkpoints_use_case.put_writes(
            thread_id="t1",
            checkpoint_ns="ns",
            checkpoint_id="cp1",
            writes=writes,
        )

        mock_checkpoint_repository.put_writes.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns="ns",
            checkpoint_id="cp1",
            writes=writes,
            upsert=False,
        )

    async def test_upsert_flag(self, checkpoints_use_case, mock_checkpoint_repository):
        await checkpoints_use_case.put_writes(
            thread_id="t1",
            checkpoint_ns="",
            checkpoint_id="cp1",
            writes=[],
            upsert=True,
        )

        call_kwargs = mock_checkpoint_repository.put_writes.call_args.kwargs
        assert call_kwargs["upsert"] is True


# ---------------------------------------------------------------------------
# list_checkpoints
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestListCheckpoints:
    async def test_basic_list(self, checkpoints_use_case, mock_checkpoint_repository):
        expected = [{"checkpoint_id": "cp1"}, {"checkpoint_id": "cp2"}]
        mock_checkpoint_repository.list_checkpoints.return_value = expected

        result = await checkpoints_use_case.list_checkpoints(thread_id="t1")

        mock_checkpoint_repository.list_checkpoints.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns=None,
            before_checkpoint_id=None,
            filter_metadata=None,
            limit=100,
        )
        assert result == expected

    async def test_with_all_filters(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        mock_checkpoint_repository.list_checkpoints.return_value = []

        await checkpoints_use_case.list_checkpoints(
            thread_id="t1",
            checkpoint_ns="ns",
            before_checkpoint_id="cp5",
            filter_metadata={"step": 3},
            limit=50,
        )

        mock_checkpoint_repository.list_checkpoints.assert_awaited_once_with(
            thread_id="t1",
            checkpoint_ns="ns",
            before_checkpoint_id="cp5",
            filter_metadata={"step": 3},
            limit=50,
        )

    async def test_returns_empty_list(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        mock_checkpoint_repository.list_checkpoints.return_value = []

        result = await checkpoints_use_case.list_checkpoints(thread_id="t1")
        assert result == []


# ---------------------------------------------------------------------------
# delete_thread
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeleteThread:
    async def test_delegates_to_repository(
        self, checkpoints_use_case, mock_checkpoint_repository
    ):
        await checkpoints_use_case.delete_thread(thread_id="t1")
        mock_checkpoint_repository.delete_thread.assert_awaited_once_with(
            thread_id="t1"
        )
