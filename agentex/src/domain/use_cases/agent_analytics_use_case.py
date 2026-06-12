from typing import Annotated

from fastapi import Depends

from src.api.schemas.agent_analytics import AgentAnalyticsSummary, TaskStatusCounts
from src.domain.repositories.agent_repository import DAgentRepository
from src.domain.repositories.task_repository import DTaskRepository
from src.utils.logging import make_logger

logger = make_logger(__name__)

HOURS_IN_DAY = 24.0


class AgentAnalyticsUseCase:
    def __init__(
        self,
        task_repository: DTaskRepository,
        agent_repository: DAgentRepository,
    ):
        self.task_repo = task_repository
        self.agent_repo = agent_repository

    async def get_summary(self, agent_id: str) -> AgentAnalyticsSummary:
        await self.agent_repo.get(id=agent_id)
        analytics = await self.task_repo.get_analytics_for_agent(agent_id)

        counts = analytics.status_counts
        total = sum(counts.values())

        status_counts = TaskStatusCounts(
            running=counts.get("RUNNING", 0),
            completed=counts.get("COMPLETED", 0),
            failed=counts.get("FAILED", 0),
            canceled=counts.get("CANCELED", 0),
            terminated=counts.get("TERMINATED", 0),
            timed_out=counts.get("TIMED_OUT", 0),
        )

        total_24h = analytics.completed_last_24h + analytics.failed_last_24h
        error_rate = analytics.failed_last_24h / total_24h if total_24h > 0 else 0.0
        throughput = analytics.completed_last_24h / HOURS_IN_DAY

        return AgentAnalyticsSummary(
            agent_id=agent_id,
            total_tasks=total,
            task_status_counts=status_counts,
            avg_task_duration_seconds=analytics.avg_duration_seconds,
            tasks_completed_last_24h=analytics.completed_last_24h,
            tasks_failed_last_24h=analytics.failed_last_24h,
            throughput_per_hour=round(throughput, 4),
            error_rate=round(error_rate, 4),
        )


DAgentAnalyticsUseCase = Annotated[
    AgentAnalyticsUseCase, Depends(AgentAnalyticsUseCase)
]
