from datetime import UTC, datetime, timedelta
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
        """Compute analytics summary for a given agent's tasks."""
        all_tasks = await self.task_repo.list_with_join(
            agent_id=agent_id,
            order_by="created_at",
            order_direction="desc",
        )

        now = datetime.now(UTC)
        cutoff_24h = now - timedelta(hours=24)

        running = 0
        completed = 0
        failed = 0
        canceled = 0
        completed_durations: list[float] = []
        completed_last_24h = 0
        failed_last_24h = 0
        total_last_24h = 0

        for task in all_tasks:
            status = task.status.value if task.status else None

            if status == "RUNNING":
                running += 1
            elif status == "COMPLETED":
                completed += 1
                if task.created_at and task.updated_at:
                    duration = (task.updated_at - task.created_at).total_seconds()
                    if duration >= 0:
                        completed_durations.append(duration)
            elif status == "FAILED":
                failed += 1
            elif status == "CANCELED":
                canceled += 1

            if task.created_at and task.created_at >= cutoff_24h:
                total_last_24h += 1
                if status == "COMPLETED":
                    completed_last_24h += 1
                elif status == "FAILED":
                    failed_last_24h += 1

        avg_duration = (
            sum(completed_durations) / len(completed_durations)
            if completed_durations
            else None
        )

        error_rate = failed_last_24h / total_last_24h if total_last_24h > 0 else None

        return AgentAnalyticsResponse(
            agent_id=agent_id,
            total_tasks=len(all_tasks),
            tasks_by_status=TaskStatusCounts(
                running=running,
                completed=completed,
                failed=failed,
                canceled=canceled,
            ),
            avg_task_duration_seconds=avg_duration,
            throughput_last_24h=completed_last_24h,
            error_rate_last_24h=error_rate,
        )


DAgentAnalyticsUseCase = Annotated[
    AgentAnalyticsUseCase, Depends(AgentAnalyticsUseCase)
]
