"""
Unit tests for SpanUseCase — OpenTelemetry-style span management.
All repositories are mocked with AsyncMock.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from src.domain.entities.spans import SpanEntity
from src.domain.use_cases.spans_use_case import SpanUseCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_span(
    id: str = "span-1",
    trace_id: str = "trace-1",
    name: str = "test-span",
    **overrides,
) -> SpanEntity:
    defaults = {
        "id": id,
        "trace_id": trace_id,
        "name": name,
        "start_time": datetime(2025, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SpanEntity(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_span_repository():
    return AsyncMock()


@pytest.fixture
def span_use_case(mock_span_repository):
    return SpanUseCase(span_repository=mock_span_repository)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpanCreate:
    async def test_creates_span_with_all_fields(
        self, span_use_case, mock_span_repository
    ):
        expected = _make_span()
        mock_span_repository.create.return_value = expected

        result = await span_use_case.create(
            name="test-span",
            trace_id="trace-1",
            id="span-1",
            task_id="task-1",
            parent_id="parent-1",
            start_time=datetime(2025, 1, 1, tzinfo=UTC),
            end_time=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            input_data={"prompt": "hi"},
            output_data={"response": "hello"},
            data={"custom": "meta"},
        )

        mock_span_repository.create.assert_awaited_once()
        created_span = mock_span_repository.create.call_args[0][0]
        assert created_span.id == "span-1"
        assert created_span.trace_id == "trace-1"
        assert created_span.task_id == "task-1"
        assert created_span.parent_id == "parent-1"
        assert created_span.input == {"prompt": "hi"}
        assert created_span.output == {"response": "hello"}
        assert created_span.data == {"custom": "meta"}
        assert result == expected

    async def test_generates_id_when_none(self, span_use_case, mock_span_repository):
        mock_span_repository.create.return_value = _make_span(id="generated")
        ts = datetime(2025, 1, 1, tzinfo=UTC)

        with patch(
            "src.domain.use_cases.spans_use_case.orm_id", return_value="generated"
        ):
            await span_use_case.create(name="s", trace_id="t", id=None, start_time=ts)

        created_span = mock_span_repository.create.call_args[0][0]
        assert created_span.id == "generated"

    async def test_defaults_optional_fields_to_none(
        self, span_use_case, mock_span_repository
    ):
        mock_span_repository.create.return_value = _make_span()
        ts = datetime(2025, 1, 1, tzinfo=UTC)

        await span_use_case.create(name="s", trace_id="t", id="id-1", start_time=ts)

        created_span = mock_span_repository.create.call_args[0][0]
        assert created_span.task_id is None
        assert created_span.parent_id is None
        assert created_span.end_time is None
        assert created_span.input is None
        assert created_span.output is None
        assert created_span.data is None


# ---------------------------------------------------------------------------
# partial_update
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpanPartialUpdate:
    async def test_updates_only_provided_fields(
        self, span_use_case, mock_span_repository
    ):
        existing = _make_span(name="original", data={"existing": "value"})
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", name="updated")

        mock_span_repository.get.assert_awaited_once_with(id="span-1")
        mock_span_repository.update.assert_awaited_once()
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.name == "updated"
        # Unchanged fields preserved
        assert updated.trace_id == "trace-1"

    async def test_updates_trace_id(self, span_use_case, mock_span_repository):
        existing = _make_span()
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", trace_id="new-trace")
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.trace_id == "new-trace"

    async def test_updates_task_id(self, span_use_case, mock_span_repository):
        existing = _make_span()
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", task_id="new-task")
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.task_id == "new-task"

    async def test_updates_parent_id(self, span_use_case, mock_span_repository):
        existing = _make_span()
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", parent_id="new-parent")
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.parent_id == "new-parent"

    async def test_updates_times(self, span_use_case, mock_span_repository):
        existing = _make_span()
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        new_start = datetime(2025, 6, 1, tzinfo=UTC)
        new_end = datetime(2025, 6, 2, tzinfo=UTC)
        await span_use_case.partial_update(
            id="span-1",
            start_time=new_start,
            end_time=new_end,
        )
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.start_time == new_start
        assert updated.end_time == new_end

    async def test_updates_input_output(self, span_use_case, mock_span_repository):
        existing = _make_span()
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(
            id="span-1",
            input_data={"new": "input"},
            output_data={"new": "output"},
        )
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.input == {"new": "input"}
        assert updated.output == {"new": "output"}

    async def test_merges_data_with_existing(self, span_use_case, mock_span_repository):
        existing = _make_span(data={"a": 1, "b": 2})
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", data={"b": 99, "c": 3})
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.data == {"a": 1, "b": 99, "c": 3}

    async def test_sets_data_when_none(self, span_use_case, mock_span_repository):
        existing = _make_span(data=None)
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1", data={"new": "data"})
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.data == {"new": "data"}

    async def test_no_change_when_all_none(self, span_use_case, mock_span_repository):
        existing = _make_span(name="orig", trace_id="t1")
        mock_span_repository.get.return_value = existing
        mock_span_repository.update.return_value = existing

        await span_use_case.partial_update(id="span-1")
        updated = mock_span_repository.update.call_args[0][0]
        assert updated.name == "orig"
        assert updated.trace_id == "t1"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpanGet:
    async def test_delegates_to_repository(self, span_use_case, mock_span_repository):
        expected = _make_span()
        mock_span_repository.get.return_value = expected

        result = await span_use_case.get(span_id="span-1")

        mock_span_repository.get.assert_awaited_once_with(id="span-1")
        assert result == expected


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpanList:
    async def test_basic_list_no_filters(self, span_use_case, mock_span_repository):
        expected = [_make_span()]
        mock_span_repository.list.return_value = expected

        result = await span_use_case.list(limit=10, page_number=1)

        mock_span_repository.list.assert_awaited_once_with(
            filters=None,
            limit=10,
            page_number=1,
            order_by=None,
            order_direction="desc",
        )
        assert result == expected

    async def test_filters_by_trace_id(self, span_use_case, mock_span_repository):
        mock_span_repository.list.return_value = []

        await span_use_case.list(limit=5, page_number=1, trace_id="t1")

        call_kwargs = mock_span_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"trace_id": "t1"}

    async def test_filters_by_task_id(self, span_use_case, mock_span_repository):
        mock_span_repository.list.return_value = []

        await span_use_case.list(limit=5, page_number=1, task_id="task-1")

        call_kwargs = mock_span_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"task_id": "task-1"}

    async def test_filters_by_both(self, span_use_case, mock_span_repository):
        mock_span_repository.list.return_value = []

        await span_use_case.list(
            limit=5,
            page_number=1,
            trace_id="t1",
            task_id="task-1",
        )

        call_kwargs = mock_span_repository.list.call_args.kwargs
        assert call_kwargs["filters"] == {"trace_id": "t1", "task_id": "task-1"}

    async def test_passes_ordering(self, span_use_case, mock_span_repository):
        mock_span_repository.list.return_value = []

        await span_use_case.list(
            limit=5,
            page_number=1,
            order_by="name",
            order_direction="asc",
        )

        call_kwargs = mock_span_repository.list.call_args.kwargs
        assert call_kwargs["order_by"] == "name"
        assert call_kwargs["order_direction"] == "asc"
