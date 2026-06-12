from pydantic import Field

from src.utils.model_utils import BaseModel


class TaskStatusCounts(BaseModel):
    running: int = Field(0, description="Number of tasks currently running")
    completed: int = Field(0, description="Number of completed tasks")
    failed: int = Field(0, description="Number of failed tasks")
    canceled: int = Field(0, description="Number of canceled tasks")
    terminated: int = Field(0, description="Number of terminated tasks")
    timed_out: int = Field(0, description="Number of timed-out tasks")


class AgentAnalyticsSummary(BaseModel):
    agent_id: str = Field(..., description="The agent ID these analytics are for")
    total_tasks: int = Field(0, description="Total number of non-deleted tasks")
    task_status_counts: TaskStatusCounts = Field(
        default_factory=TaskStatusCounts,
        description="Task counts broken down by status",
    )
    avg_task_duration_seconds: float | None = Field(
        None,
        description="Average duration in seconds for completed tasks (null if no completed tasks)",
    )
    tasks_completed_last_24h: int = Field(
        0,
        description="Number of tasks completed in the last 24 hours",
    )
    tasks_failed_last_24h: int = Field(
        0,
        description="Number of tasks that failed in the last 24 hours",
    )
    throughput_per_hour: float = Field(
        0.0,
        description="Tasks completed per hour over the last 24 hours",
    )
    error_rate: float = Field(
        0.0,
        description="Ratio of failed tasks to total tasks in the last 24 hours (0.0 - 1.0)",
    )
