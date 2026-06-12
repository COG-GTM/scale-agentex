from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.adapters.temporal.adapter_temporal import TemporalAdapter
from src.adapters.temporal.exceptions import (
    TemporalCancelError,
    TemporalConnectionError,
    TemporalError,
    TemporalInvalidArgumentError,
    TemporalQueryError,
    TemporalScheduleAlreadyExistsError,
    TemporalScheduleError,
    TemporalScheduleNotFoundError,
    TemporalSignalError,
    TemporalTerminateError,
    TemporalWorkflowAlreadyExistsError,
    TemporalWorkflowError,
    TemporalWorkflowNotFoundError,
)
from temporalio.client import ScheduleAlreadyRunningError
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

# ── Helpers ──────────────────────────────────────────────────────────


def _adapter(client=None) -> TemporalAdapter:
    return TemporalAdapter(temporal_client=client or MagicMock())


def _adapter_no_client() -> TemporalAdapter:
    return TemporalAdapter(temporal_client=None)


def _mock_handle():
    h = AsyncMock()
    h.signal = AsyncMock()
    h.query = AsyncMock(return_value="query-result")
    h.cancel = AsyncMock()
    h.terminate = AsyncMock()
    h.describe = AsyncMock(return_value="desc")
    h.pause = AsyncMock()
    h.unpause = AsyncMock()
    h.trigger = AsyncMock()
    h.delete = AsyncMock()
    return h


# ══════════════════════════════════════════════════════════════════════
#  Workflow Operations
# ══════════════════════════════════════════════════════════════════════


# ── start_workflow ───────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().start_workflow("wf", workflow_id="w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_success():
    client = MagicMock()
    handle = MagicMock()
    client.start_workflow = AsyncMock(return_value=handle)
    adapter = _adapter(client)

    result = await adapter.start_workflow(
        "MyWorkflow",
        workflow_id="w1",
        args=[{"key": "val"}],
        task_queue="tq",
        execution_timeout=timedelta(seconds=60),
        retry_policy=RetryPolicy(maximum_attempts=3),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        start_delay=timedelta(seconds=5),
    )
    assert result is handle
    client.start_workflow.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_already_exists():
    client = MagicMock()
    client.start_workflow = AsyncMock(
        side_effect=WorkflowAlreadyStartedError("w1", "wf")
    )
    with pytest.raises(TemporalWorkflowAlreadyExistsError):
        await _adapter(client).start_workflow("wf", workflow_id="w1", task_queue="tq")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_value_error():
    client = MagicMock()
    client.start_workflow = AsyncMock(side_effect=ValueError("bad arg"))
    with pytest.raises(TemporalInvalidArgumentError):
        await _adapter(client).start_workflow("wf", workflow_id="w1", task_queue="tq")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_generic_error():
    client = MagicMock()
    client.start_workflow = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(TemporalWorkflowError):
        await _adapter(client).start_workflow("wf", workflow_id="w1", task_queue="tq")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_workflow_no_optional_params():
    client = MagicMock()
    client.start_workflow = AsyncMock(return_value=MagicMock())
    adapter = _adapter(client)
    result = await adapter.start_workflow("wf", workflow_id="w1")
    assert result is not None


# ── get_workflow_handle ──────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_workflow_handle_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().get_workflow_handle("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_workflow_handle_success():
    client = MagicMock()
    handle = MagicMock()
    client.get_workflow_handle.return_value = handle
    result = await _adapter(client).get_workflow_handle(
        "w1", run_id="r1", first_execution_run_id="fe1"
    )
    assert result is handle


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_workflow_handle_raises_not_found():
    client = MagicMock()
    client.get_workflow_handle.side_effect = RuntimeError("something")
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).get_workflow_handle("w1")


# ── signal_workflow ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().signal_workflow("w1", "sig")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_workflow_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    await _adapter(client).signal_workflow("w1", "my-signal", arg={"a": 1})
    handle.signal.assert_awaited_once_with("my-signal", {"a": 1})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_workflow_not_found():
    handle = _mock_handle()
    handle.signal.side_effect = RuntimeError("workflow not found")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).signal_workflow("w1", "sig")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_workflow_generic_error():
    handle = _mock_handle()
    handle.signal.side_effect = RuntimeError("network error")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalSignalError):
        await _adapter(client).signal_workflow("w1", "sig")


# ── query_workflow ───────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().query_workflow("w1", "q")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_workflow_with_arg():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    result = await _adapter(client).query_workflow("w1", "status", arg="extra")
    handle.query.assert_awaited_once_with("status", "extra")
    assert result == "query-result"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_workflow_without_arg():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    await _adapter(client).query_workflow("w1", "status")
    handle.query.assert_awaited_once_with("status")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_workflow_not_found():
    handle = _mock_handle()
    handle.query.side_effect = RuntimeError("workflow not found")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).query_workflow("w1", "q")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_workflow_generic_error():
    handle = _mock_handle()
    handle.query.side_effect = RuntimeError("timeout")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalQueryError):
        await _adapter(client).query_workflow("w1", "q")


# ── cancel_workflow ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().cancel_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_workflow_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    await _adapter(client).cancel_workflow("w1", run_id="r1")
    handle.cancel.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_workflow_not_found():
    handle = _mock_handle()
    handle.cancel.side_effect = RuntimeError("workflow not found")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).cancel_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_workflow_generic_error():
    handle = _mock_handle()
    handle.cancel.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalCancelError):
        await _adapter(client).cancel_workflow("w1")


# ── terminate_workflow ───────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_terminate_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().terminate_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_terminate_workflow_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    await _adapter(client).terminate_workflow("w1", reason="done")
    handle.terminate.assert_awaited_once_with(reason="done")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_terminate_workflow_not_found():
    handle = _mock_handle()
    handle.terminate.side_effect = RuntimeError("workflow not found")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).terminate_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_terminate_workflow_generic_error():
    handle = _mock_handle()
    handle.terminate.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalTerminateError):
        await _adapter(client).terminate_workflow("w1")


# ── describe_workflow ────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_workflow_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().describe_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_workflow_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    result = await _adapter(client).describe_workflow("w1", run_id="r1")
    assert result == "desc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_workflow_not_found():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("workflow not found")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowNotFoundError):
        await _adapter(client).describe_workflow("w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_workflow_generic_error():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_workflow_handle.return_value = handle
    with pytest.raises(TemporalWorkflowError):
        await _adapter(client).describe_workflow("w1")


# ── list_workflows ───────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_workflows_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().list_workflows()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_workflows_success():
    async def fake_list_workflows(query=None, page_size=100):
        for wf in ["wf1", "wf2"]:
            yield wf

    client = MagicMock()
    client.list_workflows = fake_list_workflows
    result = await _adapter(client).list_workflows(query="WorkflowType='Foo'")
    assert result == ["wf1", "wf2"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_workflows_respects_page_size():
    async def fake_list_workflows(query=None, page_size=100):
        for i in range(10):
            yield f"wf{i}"

    client = MagicMock()
    client.list_workflows = fake_list_workflows
    result = await _adapter(client).list_workflows(page_size=3)
    assert len(result) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_workflows_generic_error():
    async def boom(query=None, page_size=100):
        raise RuntimeError("rpc error")
        yield  # noqa: F841 - makes this an async generator

    client = MagicMock()
    client.list_workflows = boom
    with pytest.raises(TemporalError):
        await _adapter(client).list_workflows()


# ── get_client ───────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().get_client()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_returns_client():
    client = MagicMock()
    result = await _adapter(client).get_client()
    assert result is client


# ── is_connected ─────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_connected_no_client():
    assert await _adapter_no_client().is_connected() is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_connected_healthy():
    async def fake_list_workflows(page_size=1):
        yield "wf1"

    client = MagicMock()
    client.list_workflows = fake_list_workflows
    assert await _adapter(client).is_connected() is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_connected_unhealthy():
    async def boom(page_size=1):
        raise RuntimeError("unreachable")
        yield  # noqa: F841

    client = MagicMock()
    client.list_workflows = boom
    assert await _adapter(client).is_connected() is False


# ══════════════════════════════════════════════════════════════════════
#  Schedule Operations
# ══════════════════════════════════════════════════════════════════════


# ── create_schedule ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().create_schedule(
            "s1", "wf", "w1", interval_seconds=60
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_missing_spec():
    with pytest.raises(TemporalInvalidArgumentError):
        await _adapter().create_schedule("s1", "wf", "w1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_with_interval():
    client = MagicMock()
    handle = MagicMock()
    client.create_schedule = AsyncMock(return_value=handle)
    result = await _adapter(client).create_schedule(
        "s1",
        "wf",
        "w1",
        args=[{"key": "val"}],
        task_queue="tq",
        interval_seconds=300,
        execution_timeout=timedelta(minutes=5),
        paused=True,
    )
    assert result is handle
    client.create_schedule.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_with_cron():
    client = MagicMock()
    client.create_schedule = AsyncMock(return_value=MagicMock())
    await _adapter(client).create_schedule(
        "s1", "wf", "w1", cron_expressions=["0 0 * * *"], task_queue="tq"
    )
    client.create_schedule.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_already_exists():
    client = MagicMock()
    client.create_schedule = AsyncMock(side_effect=ScheduleAlreadyRunningError())
    with pytest.raises(TemporalScheduleAlreadyExistsError):
        await _adapter(client).create_schedule(
            "s1", "wf", "w1", interval_seconds=60, task_queue="tq"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_value_error():
    client = MagicMock()
    client.create_schedule = AsyncMock(side_effect=ValueError("bad"))
    with pytest.raises(TemporalInvalidArgumentError):
        await _adapter(client).create_schedule(
            "s1", "wf", "w1", interval_seconds=60, task_queue="tq"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_schedule_generic_error():
    client = MagicMock()
    client.create_schedule = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).create_schedule(
            "s1", "wf", "w1", interval_seconds=60, task_queue="tq"
        )


# ── get_schedule ─────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().get_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_schedule_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    result = await _adapter(client).get_schedule("s1")
    assert result is handle
    handle.describe.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_schedule_not_found():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).get_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_schedule_generic_error():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).get_schedule("s1")


# ── describe_schedule ────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().describe_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_schedule_success():
    handle = _mock_handle()
    handle.describe.return_value = "sched-desc"
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    result = await _adapter(client).describe_schedule("s1")
    assert result == "sched-desc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_schedule_not_found():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).describe_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_describe_schedule_generic_error():
    handle = _mock_handle()
    handle.describe.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).describe_schedule("s1")


# ── list_schedules ───────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_schedules_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().list_schedules()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_schedules_success():
    async def fake_iter():
        for s in ["s1", "s2"]:
            yield s

    client = MagicMock()
    client.list_schedules = AsyncMock(return_value=fake_iter())
    result = await _adapter(client).list_schedules()
    assert result == ["s1", "s2"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_schedules_generic_error():
    client = MagicMock()
    client.list_schedules = AsyncMock(side_effect=RuntimeError("fail"))
    with pytest.raises(TemporalError):
        await _adapter(client).list_schedules()


# ── pause_schedule ───────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pause_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().pause_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pause_schedule_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).pause_schedule("s1", note="maintenance")
    handle.pause.assert_awaited_once_with(note="maintenance")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pause_schedule_default_note():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).pause_schedule("s1")
    handle.pause.assert_awaited_once_with(note="Paused via API")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pause_schedule_not_found():
    handle = _mock_handle()
    handle.pause.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).pause_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pause_schedule_generic_error():
    handle = _mock_handle()
    handle.pause.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).pause_schedule("s1")


# ── unpause_schedule ─────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unpause_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().unpause_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unpause_schedule_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).unpause_schedule("s1", note="resumed")
    handle.unpause.assert_awaited_once_with(note="resumed")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unpause_schedule_default_note():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).unpause_schedule("s1")
    handle.unpause.assert_awaited_once_with(note="Unpaused via API")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unpause_schedule_not_found():
    handle = _mock_handle()
    handle.unpause.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).unpause_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unpause_schedule_generic_error():
    handle = _mock_handle()
    handle.unpause.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).unpause_schedule("s1")


# ── trigger_schedule ─────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trigger_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().trigger_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trigger_schedule_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).trigger_schedule("s1")
    handle.trigger.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trigger_schedule_not_found():
    handle = _mock_handle()
    handle.trigger.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).trigger_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trigger_schedule_generic_error():
    handle = _mock_handle()
    handle.trigger.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).trigger_schedule("s1")


# ── delete_schedule ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_schedule_no_client():
    with pytest.raises(TemporalConnectionError):
        await _adapter_no_client().delete_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_schedule_success():
    handle = _mock_handle()
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    await _adapter(client).delete_schedule("s1")
    handle.delete.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_schedule_not_found():
    handle = _mock_handle()
    handle.delete.side_effect = RuntimeError("schedule not found")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleNotFoundError):
        await _adapter(client).delete_schedule("s1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_schedule_generic_error():
    handle = _mock_handle()
    handle.delete.side_effect = RuntimeError("rpc error")
    client = MagicMock()
    client.get_schedule_handle.return_value = handle
    with pytest.raises(TemporalScheduleError):
        await _adapter(client).delete_schedule("s1")
