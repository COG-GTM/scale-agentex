"""
Unit tests for MessagesUseCase and the MongoDB query conversion helpers.
All services are mocked with AsyncMock.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from src.domain.entities.task_messages import (
    MessageAuthor,
    MessageStyle,
    TaskMessageEntity,
    TaskMessageEntityFilter,
    TextContentEntity,
)
from src.domain.use_cases.messages_use_case import (
    MessagesUseCase,
    _convert_single_filter,
    _flatten_to_dot_notation,
    convert_filters_to_mongodb_query,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_content(text: str = "hello") -> TextContentEntity:
    return TextContentEntity(
        author=MessageAuthor.USER,
        style=MessageStyle.STATIC,
        content=text,
    )


def _make_message_entity(
    task_id: str = "task-1",
    msg_id: str = "msg-1",
    content: TextContentEntity | None = None,
) -> TaskMessageEntity:
    return TaskMessageEntity(
        id=msg_id,
        task_id=task_id,
        content=content or _make_text_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_task_message_service():
    svc = AsyncMock()
    return svc


@pytest.fixture
def messages_use_case(mock_task_message_service):
    return MessagesUseCase(task_message_service=mock_task_message_service)


# ---------------------------------------------------------------------------
# _flatten_to_dot_notation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlattenToDotNotation:
    def test_flat_dict(self):
        assert _flatten_to_dot_notation({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict(self):
        assert _flatten_to_dot_notation({"a": {"b": {"c": 1}}}) == {"a.b.c": 1}

    def test_mixed_dict(self):
        result = _flatten_to_dot_notation({"x": 1, "y": {"z": 2}})
        assert result == {"x": 1, "y.z": 2}

    def test_empty_dict(self):
        assert _flatten_to_dot_notation({}) == {}

    def test_with_prefix(self):
        result = _flatten_to_dot_notation({"k": "v"}, prefix="root")
        assert result == {"root.k": "v"}


# ---------------------------------------------------------------------------
# _convert_single_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConvertSingleFilter:
    def test_excludes_none_and_exclude_field(self):
        f = TaskMessageEntityFilter(
            streaming_status="IN_PROGRESS",
            exclude=True,
        )
        result = _convert_single_filter(f)
        assert "exclude" not in result
        assert result == {"streaming_status": "IN_PROGRESS"}

    def test_empty_filter(self):
        f = TaskMessageEntityFilter()
        result = _convert_single_filter(f)
        assert result == {}


# ---------------------------------------------------------------------------
# convert_filters_to_mongodb_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConvertFiltersToMongodbQuery:
    def test_empty_list(self):
        assert convert_filters_to_mongodb_query([]) == {}

    def test_single_include_filter(self):
        f = TaskMessageEntityFilter(streaming_status="DONE")
        result = convert_filters_to_mongodb_query([f])
        assert result == {"$or": [{"streaming_status": "DONE"}]}

    def test_single_exclude_filter(self):
        f = TaskMessageEntityFilter(streaming_status="IN_PROGRESS", exclude=True)
        result = convert_filters_to_mongodb_query([f])
        assert result == {"$nor": [{"streaming_status": "IN_PROGRESS"}]}

    def test_include_and_exclude_combined(self):
        inc = TaskMessageEntityFilter(streaming_status="DONE")
        exc = TaskMessageEntityFilter(streaming_status="IN_PROGRESS", exclude=True)
        result = convert_filters_to_mongodb_query([inc, exc])
        assert "$and" in result
        assert len(result["$and"]) == 2

    def test_multiple_include_filters_ored(self):
        f1 = TaskMessageEntityFilter(streaming_status="DONE")
        f2 = TaskMessageEntityFilter(streaming_status="IN_PROGRESS")
        result = convert_filters_to_mongodb_query([f1, f2])
        assert "$or" in result
        assert len(result["$or"]) == 2

    def test_multiple_exclude_filters_nored(self):
        f1 = TaskMessageEntityFilter(streaming_status="DONE", exclude=True)
        f2 = TaskMessageEntityFilter(streaming_status="IN_PROGRESS", exclude=True)
        result = convert_filters_to_mongodb_query([f1, f2])
        assert "$nor" in result
        assert len(result["$nor"]) == 2


# ---------------------------------------------------------------------------
# MessagesUseCase.create
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesCreate:
    async def test_delegates_to_service(
        self, messages_use_case, mock_task_message_service
    ):
        content = _make_text_content()
        expected = _make_message_entity()
        mock_task_message_service.append_message.return_value = expected

        result = await messages_use_case.create(
            task_id="task-1",
            content=content,
            streaming_status="DONE",
        )

        mock_task_message_service.append_message.assert_awaited_once_with(
            task_id="task-1",
            content=content,
            streaming_status="DONE",
            created_at=None,
        )
        assert result == expected

    async def test_passes_created_at(
        self, messages_use_case, mock_task_message_service
    ):
        content = _make_text_content()
        ts = datetime(2025, 1, 1, tzinfo=UTC)
        mock_task_message_service.append_message.return_value = _make_message_entity()

        await messages_use_case.create(
            task_id="t",
            content=content,
            streaming_status=None,
            created_at=ts,
        )

        call_kwargs = mock_task_message_service.append_message.call_args.kwargs
        assert call_kwargs["created_at"] == ts


# ---------------------------------------------------------------------------
# MessagesUseCase.update
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesUpdate:
    async def test_delegates_to_service(
        self, messages_use_case, mock_task_message_service
    ):
        content = _make_text_content("updated")
        expected = _make_message_entity()
        mock_task_message_service.update_message.return_value = expected

        result = await messages_use_case.update(
            task_id="task-1",
            message_id="msg-1",
            content=content,
            streaming_status="DONE",
        )

        mock_task_message_service.update_message.assert_awaited_once_with(
            task_id="task-1",
            message_id="msg-1",
            content=content,
            streaming_status="DONE",
        )
        assert result == expected


# ---------------------------------------------------------------------------
# MessagesUseCase.create_batch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesCreateBatch:
    async def test_delegates_to_service(
        self, messages_use_case, mock_task_message_service
    ):
        contents = [_make_text_content("a"), _make_text_content("b")]
        expected = [
            _make_message_entity(msg_id="m1"),
            _make_message_entity(msg_id="m2"),
        ]
        mock_task_message_service.append_messages.return_value = expected

        result = await messages_use_case.create_batch(task_id="t", contents=contents)

        mock_task_message_service.append_messages.assert_awaited_once_with(
            task_id="t",
            contents=contents,
            created_at=None,
        )
        assert result == expected

    async def test_passes_created_at(
        self, messages_use_case, mock_task_message_service
    ):
        ts = datetime(2025, 6, 1, tzinfo=UTC)
        mock_task_message_service.append_messages.return_value = []

        await messages_use_case.create_batch(
            task_id="t",
            contents=[],
            created_at=ts,
        )
        assert (
            mock_task_message_service.append_messages.call_args.kwargs["created_at"]
            == ts
        )


# ---------------------------------------------------------------------------
# MessagesUseCase.update_batch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesUpdateBatch:
    async def test_delegates_to_service(
        self, messages_use_case, mock_task_message_service
    ):
        content = _make_text_content("new")
        updates = {"msg-1": content}
        expected = [_make_message_entity()]
        mock_task_message_service.update_messages.return_value = expected

        result = await messages_use_case.update_batch(task_id="t", updates=updates)

        mock_task_message_service.update_messages.assert_awaited_once_with(
            task_id="t",
            updates=updates,
        )
        assert result == expected


# ---------------------------------------------------------------------------
# MessagesUseCase.get_message
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesGetMessage:
    async def test_delegates_to_service(
        self, messages_use_case, mock_task_message_service
    ):
        expected = _make_message_entity()
        mock_task_message_service.get_message.return_value = expected

        result = await messages_use_case.get_message(message_id="msg-1")

        mock_task_message_service.get_message.assert_awaited_once_with(
            message_id="msg-1"
        )
        assert result == expected


# ---------------------------------------------------------------------------
# MessagesUseCase.list_messages
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagesListMessages:
    async def test_basic_list(self, messages_use_case, mock_task_message_service):
        expected = [_make_message_entity()]
        mock_task_message_service.get_messages.return_value = expected

        result = await messages_use_case.list_messages(
            task_id="t",
            limit=10,
            page_number=1,
        )

        mock_task_message_service.get_messages.assert_awaited_once_with(
            task_id="t",
            limit=10,
            page_number=1,
            order_by=None,
            order_direction="desc",
            before_id=None,
            after_id=None,
            filters=None,
        )
        assert result == expected

    async def test_with_cursor_pagination(
        self, messages_use_case, mock_task_message_service
    ):
        mock_task_message_service.get_messages.return_value = []

        await messages_use_case.list_messages(
            task_id="t",
            limit=5,
            page_number=1,
            before_id="before-cursor",
            after_id="after-cursor",
            order_by="created_at",
            order_direction="asc",
        )

        call_kwargs = mock_task_message_service.get_messages.call_args.kwargs
        assert call_kwargs["before_id"] == "before-cursor"
        assert call_kwargs["after_id"] == "after-cursor"
        assert call_kwargs["order_by"] == "created_at"
        assert call_kwargs["order_direction"] == "asc"

    async def test_converts_filters_to_mongodb_query(
        self, messages_use_case, mock_task_message_service
    ):
        mock_task_message_service.get_messages.return_value = []
        filters = [TaskMessageEntityFilter(streaming_status="DONE")]

        await messages_use_case.list_messages(
            task_id="t",
            limit=10,
            page_number=1,
            filters=filters,
        )

        call_kwargs = mock_task_message_service.get_messages.call_args.kwargs
        assert call_kwargs["filters"] == {"$or": [{"streaming_status": "DONE"}]}

    async def test_none_filters_passed_as_none(
        self, messages_use_case, mock_task_message_service
    ):
        mock_task_message_service.get_messages.return_value = []

        await messages_use_case.list_messages(
            task_id="t",
            limit=10,
            page_number=1,
            filters=None,
        )

        call_kwargs = mock_task_message_service.get_messages.call_args.kwargs
        assert call_kwargs["filters"] is None
