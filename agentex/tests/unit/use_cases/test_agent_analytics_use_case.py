"""Unit tests for AgentAnalyticsUseCase."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.domain.entities.tasks import TaskEntity, TaskStatus
from src.domain.use_cases.agent_analytics_use_case import AgentAnalyticsUseCase


@pytest.fixture
def mock_task_repository():
    repo = AsyncMock()
    return repo


@pytest.fixture
def analytics_use_case(mock_task_repository):
    return AgentAnalyticsUseCase(task_repository=mock_task_repository)


def _make_task(
    status: TaskStatus,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> TaskEntity:
    now = datetime.now(UTC)
    return TaskEntity(
        id=str(uuid4()),
        name=f"task-{uuid4().hex[:8]}",
        status=status,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_tasks(analytics_use_case, mock_task_repository):
    mock_task_repository.list_with_join.return_value = []

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.agent_id == "agent-1"
    assert result.total_tasks == 0
    assert result.tasks_by_status.running == 0
    assert result.tasks_by_status.completed == 0
    assert result.avg_task_duration_seconds is None
    assert result.throughput_last_24h == 0
    assert result.error_rate_last_24h is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mixed_statuses(analytics_use_case, mock_task_repository):
    now = datetime.now(UTC)
    tasks = [
        _make_task(TaskStatus.RUNNING, created_at=now - timedelta(minutes=10)),
        _make_task(
            TaskStatus.COMPLETED,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=30),
        ),
        _make_task(
            TaskStatus.COMPLETED,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1),
        ),
        _make_task(TaskStatus.FAILED, created_at=now - timedelta(minutes=5)),
    ]
    mock_task_repository.list_with_join.return_value = tasks

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.total_tasks == 4
    assert result.tasks_by_status.running == 1
    assert result.tasks_by_status.completed == 2
    assert result.tasks_by_status.failed == 1
    assert result.avg_task_duration_seconds is not None
    assert result.avg_task_duration_seconds > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_throughput_and_error_rate_last_24h(
    analytics_use_case, mock_task_repository
):
    now = datetime.now(UTC)
    tasks = [
        _make_task(TaskStatus.COMPLETED, created_at=now - timedelta(hours=1)),
        _make_task(TaskStatus.COMPLETED, created_at=now - timedelta(hours=2)),
        _make_task(TaskStatus.FAILED, created_at=now - timedelta(hours=3)),
        # This one is older than 24h — should not count
        _make_task(TaskStatus.COMPLETED, created_at=now - timedelta(hours=25)),
    ]
    mock_task_repository.list_with_join.return_value = tasks

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.throughput_last_24h == 2
    # 3 tasks in last 24h, 1 failed → error rate = 1/3
    assert result.error_rate_last_24h == pytest.approx(1 / 3, rel=1e-6)
