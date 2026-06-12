from typing import Annotated

from fastapi import Depends

from src.api.schemas.agent_analytics import AgentAnalyticsResponse, TaskStatusCounts
from src.domain.repositories.task_repository import DTaskRepository
from src.utils.logging import make_logger

logger = make_logger(__name__)


class AgentAnalyticsUseCase:
    def __init__(self, task_repository: DTaskRepository):
        self.task_repo = task_repository

    async def get_agent_analytics(self, agent_id: str) -> AgentAnalyticsResponse:
        """Compute analytics summary for a given agent's tasks via SQL aggregation."""
        data = await self.task_repo.get_analytics_for_agent(agent_id=agent_id)

        status_counts = data["status_counts"]
        total_last_24h = data["total_last_24h"]
        failed_last_24h = data["failed_last_24h"]

        error_rate = failed_last_24h / total_last_24h if total_last_24h > 0 else None

        return AgentAnalyticsResponse(
            agent_id=agent_id,
            total_tasks=data["total"],
            tasks_by_status=TaskStatusCounts(
                running=status_counts.get("RUNNING", 0),
                completed=status_counts.get("COMPLETED", 0),
                failed=status_counts.get("FAILED", 0),
                canceled=status_counts.get("CANCELED", 0),
                terminated=status_counts.get("TERMINATED", 0),
                timed_out=status_counts.get("TIMED_OUT", 0),
            ),
            avg_task_duration_seconds=data["avg_duration_seconds"],
            throughput_last_24h=data["completed_last_24h"],
            error_rate_last_24h=error_rate,
        )


DAgentAnalyticsUseCase = Annotated[
    AgentAnalyticsUseCase, Depends(AgentAnalyticsUseCase)
]
