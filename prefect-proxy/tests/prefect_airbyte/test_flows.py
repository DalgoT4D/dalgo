import pytest
from prefect import flow

from prefect_airbyte.connections import AirbyteSyncResult
from prefect_airbyte.exceptions import AirbyteSyncJobFailed
from prefect_airbyte.flows import run_connection_sync

expected_airbyte_sync_result = AirbyteSyncResult(
    created_at=None,
    job_status="succeeded",
    job_id=45,
    records_synced=0,
    updated_at=None,
)


async def test_run_connection_sync_standalone_success(
    airbyte_server, airbyte_connection, mock_successful_connection_sync_calls
):

    result = await run_connection_sync(airbyte_connection=airbyte_connection)

    assert result == expected_airbyte_sync_result


async def test_run_connection_sync_standalone_fail(
    airbyte_server, airbyte_connection, mock_failed_connection_sync_calls, caplog
):

    with pytest.raises(AirbyteSyncJobFailed):
        await run_connection_sync(airbyte_connection=airbyte_connection)


async def test_run_connection_sync_standalone_cancel(
    airbyte_server, airbyte_connection, mock_cancelled_connection_sync_calls
):

    with pytest.raises(AirbyteSyncJobFailed):
        await run_connection_sync(airbyte_connection=airbyte_connection)


async def test_run_connection_sync_standalone_status_updates(
    airbyte_server, airbyte_connection, mock_successful_connection_sync_calls, caplog
):
    airbyte_connection.status_updates = True
    await run_connection_sync(airbyte_connection=airbyte_connection)

    assert "Job 45 succeeded" in caplog.text


async def test_run_connection_sync_subflow_synchronously(
    airbyte_server, airbyte_connection, mock_successful_connection_sync_calls
):
    @flow
    def airbyte_sync_sync_flow():
        return run_connection_sync(airbyte_connection=airbyte_connection)

    result = airbyte_sync_sync_flow()

    assert result == expected_airbyte_sync_result


async def test_run_connection_sync_subflow_asynchronously(
    airbyte_server, airbyte_connection, mock_successful_connection_sync_calls
):
    @flow
    async def airbyte_sync_sync_flow():
        return await run_connection_sync(airbyte_connection=airbyte_connection)

    result = await airbyte_sync_sync_flow()

    assert result == expected_airbyte_sync_result


# Add expected result for cancelled job
expected_airbyte_cancel_result = AirbyteSyncResult(
    created_at=None,
    job_status="cancelled",
    job_id=45,
    records_synced=0,
    updated_at=None,
)


async def test_cancel_job_standalone_success(
    airbyte_server, airbyte_connection, mock_successful_job_cancel_calls
):
    from prefect_airbyte.flows import cancel_job

    job_id = 45
    result = await cancel_job(airbyte_connection=airbyte_connection, job_id=job_id)

    assert result == expected_airbyte_cancel_result


async def test_cancel_job_standalone_not_found(
    airbyte_server, airbyte_connection, mock_job_cancel_not_found_calls
):
    from prefect_airbyte.flows import cancel_job
    from prefect_airbyte.exceptions import JobNotFoundException

    job_id = 999

    with pytest.raises(JobNotFoundException):
        await cancel_job(airbyte_connection=airbyte_connection, job_id=job_id)


async def test_cancel_job_standalone_not_running(
    airbyte_server, airbyte_connection, mock_job_cancel_not_running_calls
):
    from prefect_airbyte.flows import cancel_job
    from prefect_airbyte.exceptions import AirbyteSyncJobFailed

    job_id = 45

    with pytest.raises(AirbyteSyncJobFailed):
        await cancel_job(airbyte_connection=airbyte_connection, job_id=job_id)


async def test_cancel_job_subflow_synchronously(
    airbyte_server, airbyte_connection, mock_successful_job_cancel_calls
):
    from prefect_airbyte.flows import cancel_job

    @flow
    def airbyte_cancel_sync_flow():
        return cancel_job(airbyte_connection=airbyte_connection, job_id=45)

    result = airbyte_cancel_sync_flow()

    assert result == expected_airbyte_cancel_result


async def test_cancel_job_subflow_asynchronously(
    airbyte_server, airbyte_connection, mock_successful_job_cancel_calls
):
    from prefect_airbyte.flows import cancel_job

    @flow
    async def airbyte_cancel_sync_flow():
        return await cancel_job(airbyte_connection=airbyte_connection, job_id=45)

    result = await airbyte_cancel_sync_flow()

    assert result == expected_airbyte_cancel_result
