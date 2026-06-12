"""
Unit tests for AgentTaskTrackerUseCase — cursor-based event processing tracker.
All repositories are mocked with AsyncMock.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from src.domain.entities.agent_task_tracker import AgentTaskTrackerEntity
from src.domain.exceptions import ClientError
from src.domain.use_cases.agent_task_tracker_use_case import AgentTaskTrackerUseCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracker(
    id: str = "tracker-1",
    agent_id: str = "agent-1",
    task_id: str = "task-1",
    **overrides,
) -> AgentTaskTrackerEntity:
    defaults = {
        "id": id,
        "agent_id": agent_id,
        "task_id": task_id,
        "status": None,
        "status_reason": None,
        "last_processed_event_id": None,
        "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        "updated_at": None,
    }
    defaults.update(overrides)
    return AgentTaskTrackerEntity(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tracker_repository():
    return AsyncMock()


@pytest.fixture
def tracker_use_case(mock_tracker_repository):
    return AgentTaskTrackerUseCase(tracker_repository=mock_tracker_repository)


# ---------------------------------------------------------------------------
# get_agent_task_tracker
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetAgentTaskTracker:
    async def test_delegates_to_repository(
        self, tracker_use_case, mock_tracker_repository
    ):
        expected = _make_tracker()
        mock_tracker_repository.get.return_value = expected

        result = await tracker_use_case.get_agent_task_tracker(tracker_id="tracker-1")

        mock_tracker_repository.get.assert_awaited_once_with(id="tracker-1")
        assert result == expected


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestList:
    async def test_basic_list_no_filters(
        self, tracker_use_case, mock_tracker_repository
    ):
        expected = [_make_tracker()]
        mock_tracker_repository.list.return_value = expected

        result = await tracker_use_case.list(limit=10, page_number=1)

        mock_tracker_repository.list.assert_awaited_once_with(
            filters=None,
            limit=10,
            page_number=1,
            order_by=None,
            order_direction="desc",
        )
        assert result == expected

    async def test_filters_by_agent_id(self, tracker_use_case, mock_tracker_repository):
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(limit=10, page_number=1, agent_id="a1")

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"agent_id": "a1"}

    async def test_filters_by_task_ids(self, tracker_use_case, mock_tracker_repository):
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(
            limit=10,
            page_number=1,
            task_ids=["t1", "t2"],
        )

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"task_id": ["t1", "t2"]}

    async def test_filters_by_agent_and_task_ids(
        self, tracker_use_case, mock_tracker_repository
    ):
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(
            limit=10,
            page_number=1,
            agent_id="a1",
            task_ids=["t1"],
        )

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"agent_id": "a1", "task_id": ["t1"]}

    async def test_empty_task_ids_treated_as_filter(
        self, tracker_use_case, mock_tracker_repository
    ):
        """task_ids=[] should produce filters with task_id=[] (IN () → zero rows)."""
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(limit=10, page_number=1, task_ids=[])

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"task_id": []}

    async def test_none_task_ids_omits_filter(
        self, tracker_use_case, mock_tracker_repository
    ):
        """task_ids=None should not add task_id to filters."""
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(limit=10, page_number=1, task_ids=None)

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["filters"] is None

    async def test_passes_ordering(self, tracker_use_case, mock_tracker_repository):
        mock_tracker_repository.list.return_value = []

        await tracker_use_case.list(
            limit=5,
            page_number=2,
            order_by="created_at",
            order_direction="asc",
        )

        call_kwargs = mock_tracker_repository.list.call_args.kwargs
        assert call_kwargs["order_by"] == "created_at"
        assert call_kwargs["order_direction"] == "asc"
        assert call_kwargs["limit"] == 5
        assert call_kwargs["page_number"] == 2


# ---------------------------------------------------------------------------
# update_agent_task_tracker
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestUpdateAgentTaskTracker:
    async def test_update_with_cursor(self, tracker_use_case, mock_tracker_repository):
        expected = _make_tracker(last_processed_event_id="evt-5", status="processing")
        mock_tracker_repository.update_agent_task_tracker.return_value = expected

        result = await tracker_use_case.update_agent_task_tracker(
            tracker_id="tracker-1",
            last_processed_event_id="evt-5",
            status="processing",
        )

        mock_tracker_repository.update_agent_task_tracker.assert_awaited_once_with(
            id="tracker-1",
            status="processing",
            status_reason=None,
            last_processed_event_id="evt-5",
        )
        assert result == expected

    async def test_update_without_cursor(
        self, tracker_use_case, mock_tracker_repository
    ):
        expected = _make_tracker(status="idle")
        mock_tracker_repository.update_agent_task_tracker.return_value = expected

        result = await tracker_use_case.update_agent_task_tracker(
            tracker_id="tracker-1",
            status="idle",
            status_reason="paused by user",
        )

        call_kwargs = mock_tracker_repository.update_agent_task_tracker.call_args.kwargs
        assert call_kwargs["last_processed_event_id"] is None
        assert call_kwargs["status_reason"] == "paused by user"
        assert result == expected

    async def test_raises_client_error_on_value_error(
        self, tracker_use_case, mock_tracker_repository
    ):
        """ValueError from repo (e.g. backward cursor) should become ClientError."""
        mock_tracker_repository.update_agent_task_tracker.side_effect = ValueError(
            "Cannot move cursor backwards"
        )

        with pytest.raises(ClientError, match="Cannot move cursor backwards"):
            await tracker_use_case.update_agent_task_tracker(
                tracker_id="tracker-1",
                last_processed_event_id="old-evt",
            )

    async def test_update_with_all_params(
        self, tracker_use_case, mock_tracker_repository
    ):
        expected = _make_tracker(
            status="done",
            status_reason="completed",
            last_processed_event_id="evt-10",
        )
        mock_tracker_repository.update_agent_task_tracker.return_value = expected

        result = await tracker_use_case.update_agent_task_tracker(
            tracker_id="tracker-1",
            last_processed_event_id="evt-10",
            status="done",
            status_reason="completed",
        )

        mock_tracker_repository.update_agent_task_tracker.assert_awaited_once_with(
            id="tracker-1",
            status="done",
            status_reason="completed",
            last_processed_event_id="evt-10",
        )
        assert result.status == "done"
        assert result.status_reason == "completed"
