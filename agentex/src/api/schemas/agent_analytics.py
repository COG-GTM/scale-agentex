from pydantic import Field

from src.utils.model_utils import BaseModel


class TaskStatusCounts(BaseModel):
    running: int = Field(0, description="Number of currently running tasks")
    completed: int = Field(0, description="Number of completed tasks")
    failed: int = Field(0, description="Number of failed tasks")
    canceled: int = Field(0, description="Number of canceled tasks")


class AgentAnalyticsResponse(BaseModel):
    agent_id: str = Field(..., description="The agent ID these analytics belong to")
    total_tasks: int = Field(..., description="Total number of tasks for this agent")
    tasks_by_status: TaskStatusCounts = Field(
        ..., description="Task counts broken down by status"
    )
    avg_task_duration_seconds: float | None = Field(
        None,
        description="Average duration in seconds for completed tasks (null if no completed tasks)",
    )
    throughput_last_24h: int = Field(
        ..., description="Number of tasks completed in the last 24 hours"
    )
    error_rate_last_24h: float | None = Field(
        None,
        description="Ratio of failed tasks to total tasks in the last 24 hours (null if no tasks)",
    )
