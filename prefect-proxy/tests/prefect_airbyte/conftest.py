import pytest
import respx
from httpx import Response
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture
def respx_mock():
    """Override respx_mock: pass through Prefect's local API calls, don't require all routes called."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        mock.route(host="127.0.0.1").pass_through()
        yield mock


from prefect_airbyte.connections import AirbyteConnection
from prefect_airbyte.server import AirbyteServer


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture
def airbyte_server():
    return AirbyteServer()


@pytest.fixture
def connection_id():
    return "e1b2078f-882a-4f50-9942-cfe34b2d825b"


@pytest.fixture
def airbyte_connection(airbyte_server, connection_id):
    return AirbyteConnection(airbyte_server=airbyte_server, connection_id=connection_id)


@pytest.fixture
def airbyte_trigger_sync_response(connection_id) -> dict:
    return {
        "connectionId": connection_id,
        "status": "active",
        "job": {"id": 45, "createdAt": 1650311569, "updatedAt": 1650311585},
    }


@pytest.fixture
def airbyte_good_health_check_response() -> dict:
    return {"available": True}


@pytest.fixture
def airbyte_bad_health_check_response() -> dict:
    return {"available": False}


@pytest.fixture
def airbyte_get_connection_response_json(connection_id) -> dict:
    return {
        "connectionId": connection_id,
        "name": "File <> Snowflake Demo",
        "namespaceDefinition": "destination",
        "namespaceFormat": "${SOURCE_NAMESPACE}",
        "prefix": "",
        "sourceId": "6054b03b-a9bd-4090-96a7-08076f066975",
        "destinationId": "c5ad053e-5741-4774-a60c-f976fe95c4dd",
        "operationIds": [],
        "syncCatalog": {
            "streams": [
                {
                    "stream": {
                        "name": "epidemic_stats",
                        "jsonSchema": {
                            "type": "object",
                            "$schema": "http://json-schema.org/draft-07/schema#",
                            "properties": {
                                "key": {"type": ["string", "null"]},
                                "date": {"type": ["string", "null"]},
                                "new_tested": {"type": ["number", "null"]},
                                "new_deceased": {"type": ["number", "null"]},
                                "total_tested": {"type": ["number", "null"]},
                                "new_confirmed": {"type": ["number", "null"]},
                                "new_recovered": {"type": ["number", "null"]},
                                "total_deceased": {"type": ["number", "null"]},
                                "total_confirmed": {"type": ["number", "null"]},
                                "total_recovered": {"type": ["number", "null"]},
                            },
                        },
                        "supportedSyncModes": ["full_refresh"],
                        "sourceDefinedCursor": None,
                        "defaultCursorField": [],
                        "sourceDefinedPrimaryKey": [],
                        "namespace": None,
                    },
                    "config": {
                        "syncMode": "full_refresh",
                        "cursorField": [],
                        "destinationSyncMode": "overwrite",
                        "primaryKey": [],
                        "aliasName": "epidemic_stats",
                        "selected": True,
                    },
                }
            ]
        },
        "schedule": None,
        "status": "active",
        "resourceRequirements": None,
    }


@pytest.fixture
def airbyte_get_inactive_connection_response(
    airbyte_get_connection_response_json,
) -> dict:
    airbyte_get_connection_response_json["status"] = "inactive"
    return airbyte_get_connection_response_json


@pytest.fixture
def airbyte_get_connection_not_found():
    return {
        "id": "string",
        "message": "string",
        "exceptionClassName": "string",
        "exceptionStack": ["string"],
        "rootCauseExceptionClassName": "string",
        "rootCauseExceptionStack": ["string"],
    }


@pytest.fixture
def airbyte_base_job_status_response(connection_id) -> dict:
    return {
        "job": {
            "id": 45,
            "configType": "sync",
            "configId": connection_id,
            "createdAt": 1650644844,
            "updatedAt": 1650644844,
            "status": None,
        },
        "attempts": [],
    }


@pytest.fixture
def airbyte_get_good_job_status_response(airbyte_base_job_status_response) -> dict:
    airbyte_base_job_status_response["job"]["status"] = "succeeded"
    airbyte_base_job_status_response["attempts"].append(
        {
            "attempt": {
                "id": 0,
                "status": "succeeded",
                "createdAt": 0,
                "updatedAt": 0,
                "endedAt": 0,
                "bytesSynced": 0,
                "recordsSynced": 0,
            }
        }
    )
    return airbyte_base_job_status_response


@pytest.fixture
def airbyte_get_pending_job_status_response(airbyte_base_job_status_response) -> dict:
    airbyte_base_job_status_response["job"]["status"] = "pending"
    airbyte_base_job_status_response["attempts"].append(
        {
            "attempt": {
                "id": 0,
                "status": "pending",
                "createdAt": 0,
                "updatedAt": 0,
                "endedAt": 0,
                "bytesSynced": 0,
                "recordsSynced": 0,
            }
        }
    )
    return airbyte_base_job_status_response


@pytest.fixture
def airbyte_get_failed_job_status_response(airbyte_base_job_status_response) -> dict:
    airbyte_base_job_status_response["job"]["status"] = "failed"
    airbyte_base_job_status_response["attempts"].append(
        {
            "attempt": {
                "id": 0,
                "status": "failed",
                "createdAt": 0,
                "updatedAt": 0,
                "endedAt": 0,
                "bytesSynced": 0,
                "recordsSynced": 0,
            }
        }
    )
    return airbyte_base_job_status_response


@pytest.fixture
def airbyte_get_cancelled_job_status_response(airbyte_base_job_status_response) -> dict:
    airbyte_base_job_status_response["job"]["status"] = "cancelled"
    airbyte_base_job_status_response["attempts"].append(
        {
            "attempt": {
                "id": 0,
                "status": "cancelled",
                "createdAt": 0,
                "updatedAt": 0,
                "endedAt": 0,
                "bytesSynced": 0,
                "recordsSynced": 0,
            }
        }
    )
    return airbyte_base_job_status_response


@pytest.fixture
def airbyte_cancel_job_response() -> dict:
    return {
        "job": {"id": 45, "status": "cancelled", "createdAt": 1650644844, "updatedAt": 1650644844}
    }


@pytest.fixture
def airbyte_job_status_not_found_response():
    return {
        "id": "string",
        "message": "string",
        "exceptionClassName": "string",
        "exceptionStack": ["string"],
        "rootCauseExceptionClassName": "string",
        "rootCauseExceptionStack": ["string"],
    }


@pytest.fixture
def base_airbyte_url():
    return "http://localhost:8000/api/v1"


@pytest.fixture
def base_airbyte_public_url():
    return "http://localhost:8000/api/public/v1"


# New public API job responses (flat structure, no nested "job" key)
@pytest.fixture
def airbyte_public_api_trigger_sync_response() -> dict:
    return {"jobId": 45}


@pytest.fixture
def airbyte_public_api_good_job_response() -> dict:
    return {"jobId": 45, "status": "succeeded"}


@pytest.fixture
def airbyte_public_api_failed_job_response() -> dict:
    return {"jobId": 45, "status": "failed"}


@pytest.fixture
def airbyte_public_api_pending_job_response() -> dict:
    return {"jobId": 45, "status": "pending"}


@pytest.fixture
def airbyte_public_api_running_job_response() -> dict:
    return {"jobId": 45, "status": "running"}


@pytest.fixture
def airbyte_public_api_cancelled_job_response() -> dict:
    return {"jobId": 45, "status": "cancelled"}


@pytest.fixture
def mock_successful_connection_sync_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_public_api_trigger_sync_response,
    airbyte_public_api_good_job_response,
    airbyte_get_good_job_status_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    # new public API trigger
    respx_mock.post(url=f"{base_airbyte_public_url}/jobs").mock(
        return_value=Response(200, json=airbyte_public_api_trigger_sync_response)
    )
    # new public API job poll (used by AirbyteSync.wait_for_completion / fetch_result)
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        return_value=Response(200, json=airbyte_public_api_good_job_response)
    )
    # old job status endpoint (used by deprecated trigger_sync task)
    respx_mock.post(
        url=f"{base_airbyte_url}/jobs/get/",
        json={"id": job_id},
    ).mock(return_value=Response(200, json=airbyte_get_good_job_status_response))


@pytest.fixture
def mock_failed_connection_sync_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_public_api_trigger_sync_response,
    airbyte_public_api_failed_job_response,
    airbyte_get_failed_job_status_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    respx_mock.post(url=f"{base_airbyte_public_url}/jobs").mock(
        return_value=Response(200, json=airbyte_public_api_trigger_sync_response)
    )
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        return_value=Response(200, json=airbyte_public_api_failed_job_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/jobs/get/",
        json={"id": job_id},
    ).mock(return_value=Response(200, json=airbyte_get_failed_job_status_response))


@pytest.fixture
def mock_failed_health_check_calls(respx_mock, base_airbyte_url, airbyte_bad_health_check_response):
    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_bad_health_check_response)
    )


@pytest.fixture
def mock_bad_connection_id_calls(
    respx_mock,
    base_airbyte_url,
    airbyte_get_connection_response_json,
    airbyte_get_connection_not_found,
    airbyte_good_health_check_response,
):
    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": airbyte_get_connection_response_json["connectionId"]},
    ).mock(return_value=Response(404, json=airbyte_get_connection_not_found))


@pytest.fixture
def mock_invalid_job_status_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_public_api_trigger_sync_response,
    airbyte_job_status_not_found_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    respx_mock.post(url=f"{base_airbyte_public_url}/jobs").mock(
        return_value=Response(200, json=airbyte_public_api_trigger_sync_response)
    )
    # new public API returns 404 for unknown job
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        return_value=Response(404, json=airbyte_job_status_not_found_response)
    )
    # old endpoint also returns 404 (used by trigger_sync task)
    respx_mock.post(
        url=f"{base_airbyte_url}/jobs/get/",
        json={"id": job_id},
    ).mock(return_value=Response(404, json=airbyte_job_status_not_found_response))


@pytest.fixture
def mock_cancelled_connection_sync_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_public_api_trigger_sync_response,
    airbyte_public_api_pending_job_response,
    airbyte_public_api_failed_job_response,
    airbyte_get_pending_job_status_response,
    airbyte_get_failed_job_status_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    respx_mock.post(url=f"{base_airbyte_public_url}/jobs").mock(
        return_value=Response(200, json=airbyte_public_api_trigger_sync_response)
    )
    # new public API: pending then failed
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        side_effect=[
            Response(200, json=airbyte_public_api_pending_job_response),
            Response(200, json=airbyte_public_api_failed_job_response),
        ]
    )
    # old endpoint: pending then failed (used by trigger_sync task)
    respx_mock.post(
        url=f"{base_airbyte_url}/jobs/get/",
        json={"id": job_id},
    ).mock(
        side_effect=[
            Response(200, json=airbyte_get_pending_job_status_response),
            Response(200, json=airbyte_get_failed_job_status_response),
        ]
    )


@pytest.fixture
def mock_inactive_sync_calls(
    respx_mock,
    base_airbyte_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
):
    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    airbyte_get_connection_response_json["status"] = "inactive"
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": airbyte_get_connection_response_json["connectionId"]},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))


@pytest.fixture
def airbyte_good_export_configuration_response() -> bytes:
    return b""


@pytest.fixture
def mock_successful_config_export_calls(
    respx_mock,
    base_airbyte_url,
    airbyte_good_health_check_response,
    airbyte_good_export_configuration_response,
):
    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(url=f"{base_airbyte_url}/deployment/export/").mock(
        return_value=Response(200, content=airbyte_good_export_configuration_response)
    )


@pytest.fixture
def airbyte_get_running_job_status_response(airbyte_base_job_status_response) -> dict:
    airbyte_base_job_status_response["job"]["status"] = "running"
    airbyte_base_job_status_response["attempts"].append(
        {
            "attempt": {
                "id": 0,
                "status": "running",
                "createdAt": 0,
                "updatedAt": 0,
                "endedAt": 0,
                "bytesSynced": 0,
                "recordsSynced": 0,
            }
        }
    )
    return airbyte_base_job_status_response


@pytest.fixture
def mock_successful_job_cancel_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_cancel_job_response,
    airbyte_public_api_running_job_response,
    airbyte_public_api_cancelled_job_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    # get_job_info: running → then cancelled (wait_for_completion + fetch_result)
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        side_effect=[
            Response(200, json=airbyte_public_api_running_job_response),
            Response(200, json=airbyte_public_api_cancelled_job_response),
            Response(200, json=airbyte_public_api_cancelled_job_response),
        ]
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/jobs/cancel/",
        json={"id": str(job_id)},
    ).mock(return_value=Response(200, json=airbyte_cancel_job_response))


@pytest.fixture
def mock_job_cancel_not_running_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_public_api_good_job_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 45

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    # job is succeeded (not running) — cancel_job raises AirbyteSyncJobFailed
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        return_value=Response(200, json=airbyte_public_api_good_job_response)
    )


@pytest.fixture
def mock_job_cancel_not_found_calls(
    respx_mock,
    base_airbyte_url,
    base_airbyte_public_url,
    airbyte_good_health_check_response,
    airbyte_get_connection_response_json,
    airbyte_job_status_not_found_response,
):
    connection_id = airbyte_get_connection_response_json["connectionId"]
    job_id = 999

    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(
        url=f"{base_airbyte_url}/connections/get/",
        json={"connectionId": connection_id},
    ).mock(return_value=Response(200, json=airbyte_get_connection_response_json))
    respx_mock.get(url=f"{base_airbyte_public_url}/jobs/{job_id}").mock(
        return_value=Response(404, json=airbyte_job_status_not_found_response)
    )


@pytest.fixture
def mock_config_endpoint_not_found(
    respx_mock,
    base_airbyte_url,
    airbyte_good_health_check_response,
    airbyte_good_export_configuration_response,
):
    respx_mock.get(url=f"{base_airbyte_url}/health/").mock(
        return_value=Response(200, json=airbyte_good_health_check_response)
    )
    respx_mock.post(url=f"{base_airbyte_url}/deployment/export/").mock(return_value=Response(404))
