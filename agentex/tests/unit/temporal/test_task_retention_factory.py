from unittest.mock import MagicMock, patch

import pytest
from src.temporal.task_retention_factory import build_task_retention_use_case


@pytest.mark.unit
def test_build_task_retention_use_case_returns_use_case():
    global_deps = MagicMock()
    global_deps.mongodb_database = MagicMock()
    global_deps.temporal_client = MagicMock()

    with (
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_engine"
        ) as mock_rw_engine,
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_session_maker"
        ) as mock_rw_session,
        patch(
            "src.temporal.task_retention_factory.database_async_read_only_session_maker"
        ) as mock_ro_session,
        patch("src.temporal.task_retention_factory.httpx_client") as mock_httpx,
    ):
        mock_rw_engine.return_value = MagicMock()
        mock_rw_session.return_value = MagicMock()
        mock_ro_session.return_value = MagicMock()
        mock_httpx.return_value = MagicMock()

        use_case = build_task_retention_use_case(global_deps)

        from src.domain.use_cases.task_retention_use_case import TaskRetentionUseCase

        assert isinstance(use_case, TaskRetentionUseCase)


@pytest.mark.unit
def test_build_wires_temporal_adapter_with_client():
    global_deps = MagicMock()
    global_deps.mongodb_database = MagicMock()
    global_deps.temporal_client = MagicMock(name="fake-temporal-client")

    with (
        patch("src.temporal.task_retention_factory.database_async_read_write_engine"),
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_session_maker"
        ),
        patch(
            "src.temporal.task_retention_factory.database_async_read_only_session_maker"
        ),
        patch("src.temporal.task_retention_factory.httpx_client"),
        patch(
            "src.temporal.task_retention_factory.TemporalAdapter"
        ) as mock_adapter_cls,
    ):
        build_task_retention_use_case(global_deps)
        mock_adapter_cls.assert_called_once_with(
            temporal_client=global_deps.temporal_client
        )


@pytest.mark.unit
def test_build_creates_repositories_from_session_makers():
    global_deps = MagicMock()
    global_deps.mongodb_database = MagicMock()
    global_deps.temporal_client = None

    with (
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_engine"
        ) as mock_engine_fn,
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_session_maker"
        ) as mock_rw_session_fn,
        patch(
            "src.temporal.task_retention_factory.database_async_read_only_session_maker"
        ) as mock_ro_session_fn,
        patch("src.temporal.task_retention_factory.httpx_client"),
    ):
        engine_sentinel = MagicMock()
        mock_engine_fn.return_value = engine_sentinel

        build_task_retention_use_case(global_deps)

        mock_rw_session_fn.assert_called_once_with(engine_sentinel)
        mock_ro_session_fn.assert_called_once_with(engine_sentinel)


@pytest.mark.unit
def test_build_passes_mongodb_database_to_mongo_repos():
    mongo_db = MagicMock(name="mongo-db")
    global_deps = MagicMock()
    global_deps.mongodb_database = mongo_db
    global_deps.temporal_client = None

    with (
        patch("src.temporal.task_retention_factory.database_async_read_write_engine"),
        patch(
            "src.temporal.task_retention_factory.database_async_read_write_session_maker"
        ),
        patch(
            "src.temporal.task_retention_factory.database_async_read_only_session_maker"
        ),
        patch("src.temporal.task_retention_factory.httpx_client"),
        patch(
            "src.temporal.task_retention_factory.TaskMessageRepository"
        ) as mock_msg_repo,
        patch(
            "src.temporal.task_retention_factory.TaskStateRepository"
        ) as mock_state_repo,
    ):
        build_task_retention_use_case(global_deps)
        mock_msg_repo.assert_called_once_with(mongo_db)
        mock_state_repo.assert_called_once_with(mongo_db)
