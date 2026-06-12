"""Unit tests for AgentAnalyticsUseCase."""

from unittest.mock import AsyncMock

import pytest
from src.domain.use_cases.agent_analytics_use_case import AgentAnalyticsUseCase


@pytest.fixture
def mock_task_repository():
    return AsyncMock()


@pytest.fixture
def analytics_use_case(mock_task_repository):
    return AgentAnalyticsUseCase(task_repository=mock_task_repository)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_tasks(analytics_use_case, mock_task_repository):
    mock_task_repository.get_analytics_for_agent.return_value = {
        "status_counts": {},
        "avg_duration_seconds": None,
        "completed_last_24h": 0,
        "failed_last_24h": 0,
        "total_last_24h": 0,
        "total": 0,
    }

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.agent_id == "agent-1"
    assert result.total_tasks == 0
    assert result.tasks_by_status.running == 0
    assert result.tasks_by_status.completed == 0
    assert result.tasks_by_status.terminated == 0
    assert result.tasks_by_status.timed_out == 0
    assert result.avg_task_duration_seconds is None
    assert result.throughput_last_24h == 0
    assert result.error_rate_last_24h is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mixed_statuses(analytics_use_case, mock_task_repository):
    mock_task_repository.get_analytics_for_agent.return_value = {
        "status_counts": {
            "RUNNING": 1,
            "COMPLETED": 5,
            "FAILED": 2,
            "TERMINATED": 1,
            "TIMED_OUT": 1,
        },
        "avg_duration_seconds": 120.5,
        "completed_last_24h": 3,
        "failed_last_24h": 1,
        "total_last_24h": 5,
        "total": 10,
    }

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.total_tasks == 10
    assert result.tasks_by_status.running == 1
    assert result.tasks_by_status.completed == 5
    assert result.tasks_by_status.failed == 2
    assert result.tasks_by_status.terminated == 1
    assert result.tasks_by_status.timed_out == 1
    assert result.avg_task_duration_seconds == 120.5
    assert result.throughput_last_24h == 3
    assert result.error_rate_last_24h == pytest.approx(1 / 5, rel=1e-6)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_error_rate_zero_when_no_failures(
    analytics_use_case, mock_task_repository
):
    mock_task_repository.get_analytics_for_agent.return_value = {
        "status_counts": {"COMPLETED": 10},
        "avg_duration_seconds": 60.0,
        "completed_last_24h": 4,
        "failed_last_24h": 0,
        "total_last_24h": 4,
        "total": 10,
    }

    result = await analytics_use_case.get_agent_analytics(agent_id="agent-1")

    assert result.error_rate_last_24h == 0.0
    assert result.throughput_last_24h == 4
