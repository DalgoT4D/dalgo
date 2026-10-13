"""Flows for interacting with Airbyte."""

from prefect import flow, task

from prefect_airbyte import exceptions as err
from prefect_airbyte.connections import (
    AirbyteConnection,
    AirbyteSyncResult,
    AirbyteSync,
    ResetStream,
)


@flow
async def run_connection_sync(
    airbyte_connection: AirbyteConnection,
) -> AirbyteSyncResult:
    """A flow that triggers a sync of an Airbyte connection and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection to
            trigger and wait for completion of.

    Returns:
        `AirbyteSyncResult`: Model containing metadata for the `AirbyteSync`.

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import run_connection_sync

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def airbyte_sync_flow():
            # do some things

            airbyte_sync_result = run_connection_sync(
                airbyte_connection=connection
            )
            print(airbyte_sync_result.records_synced)

            # do some other things, like trigger DBT based on number of new raw records
        ```
    """

    # TODO: refactor block method calls to avoid using <sync_compatible_method>.aio
    # we currently need to do this because of the deadlock caused by calling
    # a sync task within an async flow
    # see [this issue](https://github.com/PrefectHQ/prefect/issues/7551)

    airbyte_sync = await task(airbyte_connection.trigger.aio)(airbyte_connection)

    await task(airbyte_sync.wait_for_completion.aio)(airbyte_sync)

    return await task(airbyte_sync.fetch_result.aio)(airbyte_sync)


@flow
async def reset_connection(
    airbyte_connection: AirbyteConnection,
) -> AirbyteSyncResult:
    """A flow that triggers a reset of an Airbyte connection and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection to
            trigger and wait for completion of.

    Returns:
        `AirbyteSyncResult`: Model containing metadata for the `AirbyteSync`.

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import reset_connection

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def airbyte_reset_flow():
            # do some things

            result = reset_connection(
                airbyte_connection=connection
            )
            print(result.job_id)

            # do some other things, like trigger DBT based on number of new raw records
        ```
    """

    # TODO: refactor block method calls to avoid using <sync_compatible_method>.aio
    # we currently need to do this because of the deadlock caused by calling
    # a sync task within an async flow
    # see [this issue](https://github.com/PrefectHQ/prefect/issues/7551)

    reset_job: AirbyteSync = await task(airbyte_connection.reset.aio)(
        airbyte_connection
    )

    await task(reset_job.wait_for_completion.aio)(reset_job)

    return await task(reset_job.fetch_result.aio)(reset_job)


@flow
async def clear_connection(
    airbyte_connection: AirbyteConnection,
) -> AirbyteSyncResult:
    """A flow that triggers a clear of an Airbyte connection and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection to
            trigger and wait for completion of.

    Returns:
        `AirbyteSyncResult`: Model containing metadata for the `AirbyteSync`.

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import clear_connection

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def airbyte_clear_flow():
            # do some things

            result = clear_connection(
                airbyte_connection=connection
            )
            print(result.job_id)

            # do some other things, like trigger DBT based on number of new raw records
        ```
    """
    clear_job: AirbyteSync = await task(airbyte_connection.clear.aio)(
        airbyte_connection
    )

    await task(clear_job.wait_for_completion.aio)(clear_job)

    return await task(clear_job.fetch_result.aio)(clear_job)


@flow
async def reset_connection_streams(
    airbyte_connection: AirbyteConnection, streams: list[ResetStream]
) -> None:
    """A flow that triggers a reset for the defined streams of an Airbyte connection and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection.
        streams: list[ResetStream] representing the streams that need to be reset


    Returns:
        None

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import reset_connection_streams

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def airbyte_reset_connection_streams_flow():
            # do some things

            airbyte_sync_result = reset_connection_streams(
                airbyte_connection=connection, streams=streams
            )
            print(airbyte_sync_result.job_id)

        ```
    """

    reset_job: AirbyteSync = await task(airbyte_connection.reset_streams.aio)(
        airbyte_connection, streams
    )

    await task(reset_job.wait_for_completion.aio)(reset_job)

    return await task(reset_job.fetch_result.aio)(reset_job)


@flow
async def clear_connection_streams(
    airbyte_connection: AirbyteConnection, streams: list[ResetStream]
) -> None:
    """A flow that triggers a clear for the defined streams of an Airbyte connection and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection.
        streams: list[ResetStream] representing the streams that need to be reset


    Returns:
        None

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import reset_connection_streams

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def airbyte_reset_connection_streams_flow():
            # do some things

            airbyte_sync_result = reset_connection_streams(
                airbyte_connection=connection, streams=streams
            )
            print(airbyte_sync_result.job_id)

        ```
    """

    clear_job: AirbyteSync = await task(airbyte_connection.clear_streams.aio)(
        airbyte_connection, streams
    )

    await task(clear_job.wait_for_completion.aio)(clear_job)

    return await task(clear_job.fetch_result.aio)(clear_job)


@flow
async def update_connection_schema(
    airbyte_connection: AirbyteConnection, catalog_diff: dict
) -> None:
    """
    A flow that does the following
    1. Update the connection with new catalog

    It will not clear and resync the affected streams. This operation will have to be done manually now

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection.
        catalog_diff: the diff of the changes to be applied at the time when the schema refresh was triggered


    Returns:
        None

    Example:
        Define a flow that runs an Airbyte connection sync:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import update_connection_schema

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        catalog_diff = {
            "transforms": [
                {
                    "transformType": "update_stream",
                    "streamDescriptor": {
                        "name": "some-stream-name"
                    },
                    "updateStream": [
                        {
                            "transformType": "add_field",
                            "fieldName": [
                                "some-new-field"
                            ],
                            "breaking": false,
                            "addField": {
                                "schema": {
                                    "type": "string"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        @flow
        def airbyte_refresh_schema_for_connection():
            # do some things

            update_connection_schema(
                airbyte_connection=connection, catalog_diff=catalog_diff
            )

        ```
    """
    await task(airbyte_connection.update_connection_catalog.aio)(
        airbyte_connection, catalog_diff
    )


@flow
async def cancel_job(
    airbyte_connection: AirbyteConnection, job_id: int
) -> AirbyteSyncResult:
    """A flow that cancels a running Airbyte job and waits for it to complete.

    Args:
        airbyte_connection: `AirbyteConnection` representing the Airbyte connection.
        job_id: The ID of the Airbyte job to cancel.

    Returns:
        `AirbyteSyncResult`: Model containing metadata for the cancelled job.

    Example:
        Define a flow that cancels an Airbyte job:
        ```python
        from prefect import flow
        from prefect_airbyte.server import AirbyteServer
        from prefect_airbyte.connections import AirbyteConnection
        from prefect_airbyte.flows import cancel_job

        airbyte_server = AirbyteServer(
            server_host="localhost",
            server_port=8000
        )

        connection = AirbyteConnection(
            airbyte_server=airbyte_server,
            connection_id="<YOUR-AIRBYTE-CONNECTION-UUID>"
        )

        @flow
        def cancel_airbyte_job_flow():
            # Cancel a running job
            result = cancel_job(
                airbyte_connection=connection,
                job_id=12345
            )
            print(f"Job {result.job_id} status: {result.job_status}")
        ```
    """
    cancel_job_sync: AirbyteSync = await task(airbyte_connection.cancel_job.aio)(
        airbyte_connection, job_id
    )

    try:
        await task(cancel_job_sync.wait_for_completion.aio)(cancel_job_sync)
    except err.AirbyteSyncJobFailed:
        pass  # "cancelled" status from wait_for_completion is expected when cancelling a job

    return await task(cancel_job_sync.fetch_result.aio)(cancel_job_sync)
