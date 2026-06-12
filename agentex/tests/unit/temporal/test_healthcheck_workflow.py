import uuid

import pytest
from src.temporal.activities.healthcheck_activities import (
    CHECK_STATUS_ACTIVITY,
    UPDATE_AGENT_STATUS_ACTIVITY,
)
from src.temporal.workflows.healthcheck_workflow import HealthCheckWorkflow
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

TASK_QUEUE = "test-healthcheck"


def _workflow_id() -> str:
    return f"hc-{uuid.uuid4()}"


# ── Unhealthy agent gets marked after 5 failures ────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_marked_unhealthy_after_five_failures():
    update_calls = []

    @activity.defn(name=CHECK_STATUS_ACTIVITY)
    async def fake_check(agent_id: str, acp_url: str) -> bool:
        return False

    @activity.defn(name=UPDATE_AGENT_STATUS_ACTIVITY)
    async def fake_update(agent_id: str, status: str) -> None:
        update_calls.append((agent_id, status))

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HealthCheckWorkflow],
            activities=[fake_check, fake_update],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            await env.client.execute_workflow(
                HealthCheckWorkflow.run,
                {"agent_id": "a1", "acp_url": "http://agent:8080"},
                id=_workflow_id(),
                task_queue=TASK_QUEUE,
            )

    assert len(update_calls) == 1
    assert update_calls[0] == ("a1", "Unhealthy")


# ── Exception in check_status treated as failure ─────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_status_exception_counts_as_failure():
    update_calls = []

    @activity.defn(name=CHECK_STATUS_ACTIVITY)
    async def fake_check(agent_id: str, acp_url: str) -> bool:
        raise RuntimeError("connection refused")

    @activity.defn(name=UPDATE_AGENT_STATUS_ACTIVITY)
    async def fake_update(agent_id: str, status: str) -> None:
        update_calls.append(status)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HealthCheckWorkflow],
            activities=[fake_check, fake_update],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            await env.client.execute_workflow(
                HealthCheckWorkflow.run,
                {"agent_id": "a1", "acp_url": "http://agent:8080"},
                id=_workflow_id(),
                task_queue=TASK_QUEUE,
            )

    assert "Unhealthy" in update_calls


# ── Successful check resets failure counter ──────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_success_resets_failure_counter():
    call_num = 0
    update_calls = []

    @activity.defn(name=CHECK_STATUS_ACTIVITY)
    async def fake_check(agent_id: str, acp_url: str) -> bool:
        nonlocal call_num
        call_num += 1
        # Fail 4 times, succeed once, then fail 5 more → total 10 checks
        if call_num <= 4:
            return False
        if call_num == 5:
            return True
        return False

    @activity.defn(name=UPDATE_AGENT_STATUS_ACTIVITY)
    async def fake_update(agent_id: str, status: str) -> None:
        update_calls.append(status)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HealthCheckWorkflow],
            activities=[fake_check, fake_update],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            await env.client.execute_workflow(
                HealthCheckWorkflow.run,
                {"agent_id": "a1", "acp_url": "http://agent:8080"},
                id=_workflow_id(),
                task_queue=TASK_QUEUE,
            )

    # Counter resets at check 5, so 5 more failures (checks 6-10) trigger unhealthy
    assert "Unhealthy" in update_calls
    assert call_num == 10


# ── failure_counter preserved from workflow_args ─────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initial_failure_counter_from_args():
    check_count = 0
    update_calls = []

    @activity.defn(name=CHECK_STATUS_ACTIVITY)
    async def fake_check(agent_id: str, acp_url: str) -> bool:
        nonlocal check_count
        check_count += 1
        return False

    @activity.defn(name=UPDATE_AGENT_STATUS_ACTIVITY)
    async def fake_update(agent_id: str, status: str) -> None:
        update_calls.append(status)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HealthCheckWorkflow],
            activities=[fake_check, fake_update],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            # Start with failure_counter=4 so one more failure triggers unhealthy
            await env.client.execute_workflow(
                HealthCheckWorkflow.run,
                {
                    "agent_id": "a1",
                    "acp_url": "http://agent:8080",
                    "failure_counter": 4,
                },
                id=_workflow_id(),
                task_queue=TASK_QUEUE,
            )

    assert "Unhealthy" in update_calls
    assert check_count == 1
