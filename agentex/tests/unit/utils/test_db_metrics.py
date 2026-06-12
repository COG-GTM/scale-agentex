"""Unit tests for PostgreSQL database metrics instrumentation.

Covers helper functions, pool metrics, query metrics, and the unified collector.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from src.utils import db_metrics
from src.utils.db_metrics import (
    PostgresMetricsCollector,
    PostgresPoolMetrics,
    PostgresQueryMetrics,
    _format_statsd_tags,
    _parse_db_url,
)

# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_format_statsd_tags_maps_known_keys():
    attrs = {
        "service.name": "agentex",
        "db.system.name": "postgresql",
        "db.client.connection.pool.name": "main",
    }
    tags = _format_statsd_tags(attrs)
    assert "service:agentex" in tags
    assert "db_system:postgresql" in tags
    assert "pool:main" in tags


@pytest.mark.unit
def test_format_statsd_tags_maps_unknown_keys():
    attrs = {"custom.metric.key": "value"}
    tags = _format_statsd_tags(attrs)
    assert "custom_metric_key:value" in tags


@pytest.mark.unit
def test_format_statsd_tags_empty():
    assert _format_statsd_tags({}) == []


@pytest.mark.unit
def test_format_statsd_tags_all_known_mappings():
    attrs = {
        "server.address": "dbhost",
        "db.namespace": "mydb",
        "deployment.environment": "prod",
        "db.client.connection.state": "idle",
        "db.operation.name": "SELECT",
        "db.collection.name": "users",
        "error.type": "OperationalError",
    }
    tags = _format_statsd_tags(attrs)
    assert "server:dbhost" in tags
    assert "db_name:mydb" in tags
    assert "env:prod" in tags
    assert "state:idle" in tags
    assert "operation:SELECT" in tags
    assert "table:users" in tags
    assert "error_type:OperationalError" in tags


@pytest.mark.unit
def test_parse_db_url_full():
    host, port, db_name = _parse_db_url("postgresql://user:pass@dbhost:5433/mydb")
    assert host == "dbhost"
    assert port == 5433
    assert db_name == "mydb"


@pytest.mark.unit
def test_parse_db_url_defaults_no_path():
    host, port, db_name = _parse_db_url("postgresql://user:pass@localhost:5432")
    assert host == "localhost"
    assert port == 5432
    assert db_name == "postgres"


@pytest.mark.unit
def test_parse_db_url_default_port():
    host, port, db_name = _parse_db_url("postgresql://user:pass@host/mydb")
    assert host == "host"
    assert port == 5432
    assert db_name == "mydb"


# ---------------------------------------------------------------------------
# PostgresPoolMetrics tests (event registration patched)
# ---------------------------------------------------------------------------


def _make_mock_engine():
    """Create a mock async engine with pool."""
    mock_pool = MagicMock()
    mock_pool.checkedin.return_value = 5
    mock_pool.checkedout.return_value = 3
    mock_pool.overflow.return_value = 0
    mock_pool.size.return_value = 10
    mock_pool._max_overflow = 5

    mock_sync_engine = MagicMock()
    mock_sync_engine.pool = mock_pool

    mock_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine
    return mock_engine


@pytest.fixture(autouse=True)
def patch_sqlalchemy_events():
    """Patch event.listens_for so SQLAlchemy doesn't try to register on mocks."""
    with patch("src.utils.db_metrics.event") as mock_event:
        # Make listens_for return a no-op decorator
        mock_event.listens_for.return_value = lambda fn: fn
        yield mock_event


@pytest.mark.unit
def test_pool_metrics_init_disabled_without_otel():
    """When OTel meter is None, pool metrics is disabled but does not error."""
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    assert metrics._enabled is False
    assert metrics.base_attributes["db.system.name"] == "postgresql"
    assert metrics.base_attributes["server.address"] == "localhost"
    assert metrics.base_attributes["db.namespace"] == "testdb"


@pytest.mark.unit
def test_pool_metrics_init_enabled_with_otel():
    """When OTel meter is available, pool metrics creates instruments."""
    engine = _make_mock_engine()
    mock_meter = MagicMock()

    with patch.object(db_metrics, "get_meter", return_value=mock_meter):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="main",
            db_url="postgresql://user:pass@dbhost:5433/agentex",
            environment="production",
        )

    assert metrics._enabled is True
    assert mock_meter.create_up_down_counter.call_count == 3
    assert mock_meter.create_counter.call_count == 2
    assert mock_meter.create_histogram.call_count == 1


@pytest.mark.unit
def test_pool_metrics_base_attributes():
    """Base attributes should include pool name, service, host info."""
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="primary",
            db_url="postgresql://user:pass@db.internal:5432/app",
            environment="staging",
            service_name="my-service",
        )

    assert metrics.base_attributes["service.name"] == "my-service"
    assert metrics.base_attributes["db.client.connection.pool.name"] == "primary"
    assert metrics.base_attributes["server.address"] == "db.internal"
    assert metrics.base_attributes["server.port"] == 5432
    assert metrics.base_attributes["db.namespace"] == "app"
    assert metrics.base_attributes["deployment.environment"] == "staging"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_debounces():
    """collect_pool_metrics should not collect more than once per interval."""
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    # First call should collect
    metrics._last_metrics_time = 0.0
    await metrics.collect_pool_metrics()
    assert metrics._last_metrics_time > 0

    # Immediate second call should be skipped (debounced)
    saved_time = metrics._last_metrics_time
    await metrics.collect_pool_metrics()
    assert metrics._last_metrics_time == saved_time


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_statsd_disabled():
    """When StatsD is disabled, pool metrics should still run without error."""
    engine = _make_mock_engine()

    with (
        patch.object(db_metrics, "get_meter", return_value=None),
        patch.object(db_metrics, "_STATSD_ENABLED", False),
    ):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )
        metrics._last_metrics_time = 0.0
        await metrics.collect_pool_metrics()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_statsd_enabled():
    """When StatsD is enabled, pool metrics emits gauge calls."""
    engine = _make_mock_engine()

    with (
        patch.object(db_metrics, "get_meter", return_value=None),
        patch.object(db_metrics, "_STATSD_ENABLED", True),
        patch.object(db_metrics, "statsd") as mock_statsd,
    ):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )
        metrics._last_metrics_time = 0.0
        await metrics.collect_pool_metrics()

    assert mock_statsd.gauge.call_count == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_otel_deltas():
    """OTel metrics should emit deltas from last collected values."""
    engine = _make_mock_engine()
    mock_meter = MagicMock()
    # Ensure each create_up_down_counter call returns a distinct mock
    mock_meter.create_up_down_counter.side_effect = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    with (
        patch.object(db_metrics, "get_meter", return_value=mock_meter),
        patch.object(db_metrics, "_STATSD_ENABLED", False),
    ):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    # Simulate first collection
    metrics._last_metrics_time = 0.0
    await metrics.collect_pool_metrics()

    # _connection_count should have been called with idle delta (5) and used delta (3)
    assert metrics._connection_count.add.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_otel_no_delta_no_emit():
    """If pool state unchanged, no OTel deltas should be emitted."""
    engine = _make_mock_engine()
    mock_meter = MagicMock()

    with (
        patch.object(db_metrics, "get_meter", return_value=mock_meter),
        patch.object(db_metrics, "_STATSD_ENABLED", False),
    ):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    # First collection sets baseline
    metrics._last_metrics_time = 0.0
    await metrics.collect_pool_metrics()

    # Reset call counts
    metrics._connection_count.add.reset_mock()
    metrics._connection_overflow.add.reset_mock()
    metrics._connection_max.add.reset_mock()

    # Second collection with same values => no deltas
    metrics._last_metrics_time = 0.0
    await metrics.collect_pool_metrics()

    metrics._connection_count.add.assert_not_called()
    metrics._connection_overflow.add.assert_not_called()
    metrics._connection_max.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_metrics_collect_handles_errors():
    """Errors during collection should be caught and logged, not raised."""
    engine = _make_mock_engine()
    engine.sync_engine.pool.checkedin.side_effect = RuntimeError("pool broken")

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresPoolMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    metrics._last_metrics_time = 0.0
    # Should not raise
    await metrics.collect_pool_metrics()


# ---------------------------------------------------------------------------
# PostgresQueryMetrics tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_query_metrics_init_disabled_without_otel():
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="test",
            db_url="postgresql://user:pass@localhost:5432/testdb",
            environment="test",
        )

    assert metrics._enabled is False


@pytest.mark.unit
def test_query_metrics_init_enabled_with_otel():
    engine = _make_mock_engine()
    mock_meter = MagicMock()

    with patch.object(db_metrics, "get_meter", return_value=mock_meter):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="main",
            db_url="postgresql://user:pass@dbhost:5432/agentex",
            environment="production",
        )

    assert metrics._enabled is True
    assert mock_meter.create_histogram.call_count == 2
    assert mock_meter.create_counter.call_count == 2


@pytest.mark.unit
def test_query_metrics_base_attributes():
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="replica",
            db_url="postgresql://user:pass@replica-host:5432/app",
            environment="production",
            service_name="my-app",
        )

    assert metrics.base_attributes["service.name"] == "my-app"
    assert metrics.base_attributes["db.client.connection.pool.name"] == "replica"
    assert metrics.base_attributes["server.address"] == "replica-host"


@pytest.mark.unit
def test_extract_operation_select():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_operation("SELECT * FROM users") == "SELECT"
    assert metrics._extract_operation("  select id from tasks") == "SELECT"


@pytest.mark.unit
def test_extract_operation_insert():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert (
        metrics._extract_operation("INSERT INTO users (name) VALUES ('x')") == "INSERT"
    )


@pytest.mark.unit
def test_extract_operation_update():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_operation("UPDATE users SET name = 'y'") == "UPDATE"


@pytest.mark.unit
def test_extract_operation_delete():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_operation("DELETE FROM users WHERE id = 1") == "DELETE"


@pytest.mark.unit
def test_extract_operation_transaction_commands():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_operation("BEGIN") == "BEGIN"
    assert metrics._extract_operation("COMMIT") == "COMMIT"
    assert metrics._extract_operation("ROLLBACK") == "ROLLBACK"


@pytest.mark.unit
def test_extract_operation_other():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_operation("CREATE TABLE foo (id int)") == "OTHER"
    assert metrics._extract_operation("ALTER TABLE foo ADD col text") == "OTHER"


@pytest.mark.unit
def test_extract_table_from_select():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_table("SELECT * FROM users WHERE id = 1") == "users"


@pytest.mark.unit
def test_extract_table_from_insert():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_table("INSERT INTO tasks (name) VALUES ('x')") == "tasks"


@pytest.mark.unit
def test_extract_table_from_update():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_table("UPDATE agents SET status = 'active'") == "agents"


@pytest.mark.unit
def test_extract_table_from_join():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert (
        metrics._extract_table(
            "SELECT * FROM tasks JOIN agents ON tasks.agent_id = agents.id"
        )
        == "tasks"
    )


@pytest.mark.unit
def test_extract_table_returns_none_for_no_match():
    engine = _make_mock_engine()
    with patch.object(db_metrics, "get_meter", return_value=None):
        metrics = PostgresQueryMetrics(
            engine=engine,
            pool_name="t",
            db_url="postgresql://u:p@h:5432/d",
            environment="t",
        )

    assert metrics._extract_table("BEGIN") is None
    assert metrics._extract_table("COMMIT") is None


# ---------------------------------------------------------------------------
# PostgresMetricsCollector tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_collector_register_engine():
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        collector = PostgresMetricsCollector()
        collector.register_engine(
            engine=engine,
            pool_name="main",
            db_url="postgresql://u:p@h:5432/d",
            environment="test",
        )

    assert "main" in collector._pool_metrics
    assert "main" in collector._query_metrics


@pytest.mark.unit
def test_collector_register_multiple_engines():
    engine1 = _make_mock_engine()
    engine2 = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        collector = PostgresMetricsCollector()
        collector.register_engine(
            engine=engine1,
            pool_name="main",
            db_url="postgresql://u:p@h:5432/d1",
            environment="test",
        )
        collector.register_engine(
            engine=engine2,
            pool_name="temporal",
            db_url="postgresql://u:p@h:5432/d2",
            environment="test",
        )

    assert len(collector._pool_metrics) == 2
    assert len(collector._query_metrics) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collector_collect_all_metrics():
    engine = _make_mock_engine()

    with patch.object(db_metrics, "get_meter", return_value=None):
        collector = PostgresMetricsCollector()
        collector.register_engine(
            engine=engine,
            pool_name="main",
            db_url="postgresql://u:p@h:5432/d",
            environment="test",
        )

    # Force collection by resetting debounce
    collector._pool_metrics["main"]._last_metrics_time = 0.0
    await collector.collect_all_metrics()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collector_start_and_stop_collection():
    collector = PostgresMetricsCollector()

    assert collector._collection_task is None

    await collector.start_collection()
    assert collector._collection_task is not None
    assert not collector._collection_task.done()

    await collector.stop_collection()
    assert collector._collection_task is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collector_stop_when_not_started():
    """stop_collection should be safe when no task is running."""
    collector = PostgresMetricsCollector()
    await collector.stop_collection()
    assert collector._collection_task is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collector_start_is_idempotent():
    """Calling start_collection twice should not create a second task."""
    collector = PostgresMetricsCollector()

    await collector.start_collection()
    task1 = collector._collection_task

    await collector.start_collection()
    task2 = collector._collection_task

    assert task1 is task2

    await collector.stop_collection()
