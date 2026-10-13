"""Client for interacting with Airbyte instance"""

import logging
from typing import Any, Dict, Tuple
from warnings import warn

import httpx
from tenacity import (
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    retry,
    RetryCallState,
)

from prefect_airbyte import exceptions as err


def log_before_retry(retry_state: RetryCallState):
    """Log before each retry attempt"""
    client_instance = retry_state.args[0]
    client_instance.logger.info(
        "Starting tenacity lib attempt %s",
        retry_state.attempt_number,
    )


def log_after_retry(retry_state: RetryCallState):
    """Log the exception after a failed attempt"""
    client_instance = retry_state.args[0]
    
    # Get the actual exception from the outcome
    exception = None
    if retry_state.outcome is not None and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
    
    client_instance.logger.info(
        "Attempt %s failed with exception: %s. Retrying...",
        retry_state.attempt_number,
        exception,
    )

class AirbyteClient:
    """
    Client class used to call API endpoints on an Airbyte server.

    This client currently supports username/password authentication as set in `auth`.

    For more info, see the [Airbyte docs](https://docs.airbyte.io/api-documentation).

    Attributes:
        airbyte_base_url str: Base API endpoint URL for Airbyte.
        auth: Username and password for Airbyte API.
        logger: A logger instance used by the client to log messages related to
            API calls.
        timeout: The number of seconds to wait before an API call times out.
    """

    def __init__(
        self,
        logger: logging.Logger,
        airbyte_base_url: str = "http://localhost:8000/api/v1",
        airbyte_public_api_base_url: str = "http://localhost:8000/api/public/v1",
        auth: Tuple[str, str] = ("airbyte", "password"),
        timeout: int = 5,
    ):
        self._closed = False
        self._started = False

        self.airbyte_base_url = airbyte_base_url
        self.airbyte_public_api_base_url = airbyte_public_api_base_url
        self.auth = auth
        self.logger = logger
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.airbyte_base_url, auth=self.auth, timeout=self.timeout
        )
        self._public_client = httpx.AsyncClient(
            base_url=self.airbyte_public_api_base_url,
            auth=self.auth,
            timeout=self.timeout
        )

    async def check_health_status(self, client: httpx.AsyncClient) -> bool:
        """
        Checks the health status of an Airbyte instance.

        Args:
            client: `httpx.AsyncClient` used to interact with the Airbyte API.

        Returns:
            True if the server is healthy. False otherwise.
        """
        get_connection_url = self.airbyte_base_url + "/health/"
        try:
            response = await client.get(get_connection_url)
            response.raise_for_status()

            self.logger.debug("Health check response: %s", response.json())
            key = "available" if "available" in response.json() else "db"
            health_status = response.json()[key]
            if not health_status:
                raise err.AirbyteServerNotHealthyException(
                    f"Airbyte Server health status: {health_status}"
                )
            return True
        except httpx.HTTPStatusError as e:
            raise err.AirbyteServerNotHealthyException() from e

    async def export_configuration(
        self,
    ) -> bytes:
        """
        Triggers an export of Airbyte configuration.

        **Note**: As of Airbyte v0.40.7-alpha, this endpoint no longer exists.

        Returns:
            Gzipped Airbyte configuration data.
        """
        warn(
            "As of Airbyte v0.40.7-alpha, the Airbyte API no longer supports "
            "exporting configurations. See the Octavia CLI docs for more info.",
            DeprecationWarning,
            stacklevel=2,
        )

        get_connection_url = self.airbyte_base_url + "/deployment/export/"

        try:
            response = await self._client.post(get_connection_url)
            response.raise_for_status()

            self.logger.debug("Export configuration response: %s", response)

            export_config = response.content
            return export_config
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.error(
                    "If you are using Airbyte v0.40.7-alpha, there is no longer "
                    "an API endpoint for exporting configurations."
                )
                raise err.AirbyteExportConfigurationFailed() from e

    async def get_connection_status(self, connection_id: str) -> str:
        """
        Gets the status of a defined Airbyte connection.

        Args:
            connection_id: ID of an existing Airbyte connection.

        Returns:
            The status of the defined Airbyte connection.
        """
        get_connection_url = self.airbyte_base_url + "/connections/get/"

        try:
            response = await self._client.post(
                get_connection_url, json={"connectionId": connection_id}
            )

            response.raise_for_status()

            connection_status = response.json()["status"]
            return connection_status
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException() from e
            else:
                raise err.AirbyteServerNotHealthyException() from e

    @retry(
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, err.AirbyteServerNotHealthyException, Exception)
        ),
        wait=wait_exponential(multiplier=2, min=10, max=120),
        stop=stop_after_attempt(3),
        before=log_before_retry,
        after=log_after_retry,
    )
    async def trigger_manual_sync_connection(
        self, connection_id: str
    ) -> str:
        """
        Triggers a manual sync of the connection.

        Args:
            connection_id: ID of connection to sync.

        Returns:
            job_id: ID of the job that was triggered.
            created_at: Datetime string of when the job was created

        """
        jobs_url = self.airbyte_public_api_base_url + "/jobs"

        try:
            response = await self._public_client.post(
                jobs_url, json={"jobType": "sync", "connectionId": connection_id}
            )
            response.raise_for_status()
            job = response.json()
            job_id = job["jobId"]
            return job_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found."
                    f"Exited with error: {e.response.text}"
                ) from e
            
            elif e.response.status_code == 409:
                raise err.AirbyteSyncJobConflictException(
                    f"Connection {connection_id} has already a sync running. "
                    f"Exited with error: {e.response.text}"
                ) from e
            
            elif e.response.status_code < 500 and e.response.status_code >= 400:
                raise Exception(
                    f"Client error {e.response.status_code} when triggering sync for "
                    f"connection {connection_id}: {e.response.text}"
                ) from e

            raise err.AirbyteServerNotHealthyException(
                f"Server error {e.response.status_code} when triggering sync for "
                f"connection {connection_id}: {e.response.text}"
            ) from e
        except Exception as e:
            self.logger.error(e)
            raise Exception(
                f"Something went wrong while triggering sync for connection {connection_id}: {e}"
            ) from e

    async def trigger_reset_connection(self, connection_id: str) -> Tuple[str, str]:
        """
        Triggers a reset of the airbyte connection.

        Args:
            connection_id: ID of connection to sync.

        Returns:
            job_id: ID of the job that was triggered.
            created_at: Datetime string of when the job was created.

        """
        get_connection_url = self.airbyte_base_url + "/connections/reset/"

        try:
            response = await self._client.post(
                get_connection_url, json={"connectionId": connection_id}
            )
            response.raise_for_status()
            job = response.json()["job"]
            job_id = job["id"]
            job_created_at = job["createdAt"]
            return job_id, job_created_at
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double "
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def trigger_clear_connection(self, connection_id: str) -> Tuple[str, str]:
        """
        Triggers a clear of the airbyte connection.
        This will only clear the data in the destination.

        Args:
            connection_id: ID of connection to sync.

        Returns:
            job_id: ID of the job that was triggered.
            created_at: Datetime string of when the job was created.

        """
        get_connection_url = self.airbyte_base_url + "/connections/clear/"

        try:
            response = await self._client.post(
                get_connection_url, json={"connectionId": connection_id}
            )
            response.raise_for_status()
            job = response.json()["job"]
            job_id = job["id"]
            job_created_at = job["createdAt"]
            return job_id, job_created_at
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double "
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def trigger_reset_streams_for_connection(
        self, connection_id: str, streams: list[dict]
    ) -> Tuple[str, str]:
        """
        Triggers a reset of the airbyte connection for the streams provided.

        Args:
            connection_id: ID of connection to sync.

        Returns:
            job_id: ID of the job that was triggered.
            created_at: Datetime string of when the job was created.

        """
        get_connection_url = self.airbyte_base_url + "/connections/reset/stream"

        try:
            response = await self._client.post(
                get_connection_url,
                json={
                    "connectionId": connection_id,
                    "streams": streams,
                },
            )
            response.raise_for_status()
            job = response.json()["job"]
            job_id = job["id"]
            job_created_at = job["createdAt"]
            return job_id, job_created_at
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double "
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def trigger_clear_streams_for_connection(
        self, connection_id: str, streams: list[dict]
    ) -> Tuple[str, str]:
        """
        Triggers a clear of the airbyte connection for the streams provided.

        Args:
            connection_id: ID of connection to sync.

        Returns:
            job_id: ID of the job that was triggered.
            created_at: Datetime string of when the job was created.

        """
        get_connection_url = self.airbyte_base_url + "/connections/clear/stream"

        try:
            response = await self._client.post(
                get_connection_url,
                json={
                    "connectionId": connection_id,
                    "streams": streams,
                },
            )
            response.raise_for_status()
            job = response.json()["job"]
            job_id = job["id"]
            job_created_at = job["createdAt"]
            return job_id, job_created_at
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double "
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def get_job_status(self, job_id: str) -> Tuple[str, int, int]:
        """
        Gets the status of an Airbyte connection sync job.

        **Note**: Deprecated in favor of `AirbyteClient.get_job_info`.

        Args:
            job_id: ID of the Airbyte job to check.

        Returns:
            job_status: The current status of the job.
            job_created_at: Datetime string of when the job was created.
            job_updated_at: Datetime string of the when the job was last updated.
        """
        warn(
            "`AirbyteClient.get_job_status` is deprecated and will be removed in "
            "a future release. If you are using this client method directly, please "
            "use the `AirbyteClient.get_job_info` method instead. If you are"
            "seeing this warning while using the `trigger_sync` task, please "
            "define an `AirbyteConnection` and use `run_connection_sync` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        get_connection_url = self.airbyte_base_url + "/jobs/get/"
        try:
            response = await self._client.post(get_connection_url, json={"id": job_id})
            response.raise_for_status()

            job = response.json()["job"]
            job_status = job["status"]
            job_created_at = job["createdAt"]
            job_updated_at = job["updatedAt"]
            return job_status, job_created_at, job_updated_at
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.JobNotFoundException(f"Job {job_id} not found.") from e
            raise err.AirbyteServerNotHealthyException() from e

    @retry(
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, err.AirbyteServerNotHealthyException)
        ),
        wait=wait_exponential(multiplier=2, max=120),
        stop=stop_after_attempt(8),
        before=log_before_retry,
        after=log_after_retry,
        reraise=True,
    )
    async def get_job_info(self, job_id: str) -> Dict[str, Any]:
        """
        Gets the full API response for a given Airbyte Job ID.

        Args:
            job_id: The ID of the Airbyte job to retrieve information on.

        Returns:
            Dict of the full API response for the given job ID.
        """
        try:
            get_job_url = self.airbyte_public_api_base_url + f"/jobs/{job_id}"
            self.logger.info(f"Fetching airbyte job info for job ID: {job_id}")

            response = await self._public_client.get(get_job_url)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(e)
            
            if e.response.status_code == 404:
                raise err.JobNotFoundException(
                    f"Job {job_id} not found."

                ) from e
            
            elif e.response.status_code < 500 and e.response.status_code >= 400:
                raise Exception(
                    f"Client error {e.response.status_code} when fetching job info "
                    f"for job ID {job_id}: {e.response.text}"
                ) from e
            
            raise err.AirbyteServerNotHealthyException(
                f"Failed to fetch job info for job ID {job_id}."
                f" Exited with error: {e.response.text} and status code {e.response.status_code}"
            ) from e
        except Exception as e:
            self.logger.error(e)
            raise Exception(
                f"Something went wrong while fetching job info for job ID {job_id}: {e}"
            ) from e

    async def trigger_cancel_job(self, job_id: str) -> Tuple[str, str]:
        """
        Triggers a cancel of a running Airbyte job.

        Args:
            job_id: The ID of the Airbyte job to cancel.

        Returns:
            job_id: ID of the job that was triggered for cancellation.
            created_at: Datetime string of when the job was created.
        """
        cancel_job_url = self.airbyte_base_url + f"/jobs/cancel/"
        self.logger.info(f"Triggering cancel for airbyte job with ID: {job_id}")
        try:
            response = await self._client.post(cancel_job_url, json={"id": job_id})
            response.raise_for_status()

            job_response = response.json()
            job = job_response["job"]
            job_id = job["id"]
            job_created_at = job["createdAt"]
            return job_id, job_created_at

        except httpx.HTTPStatusError as e:
            self.logger.error(e)
            if e.response.status_code == 404:
                raise err.JobNotFoundException(f"Job {job_id} not found.") from e
            raise err.AirbyteServerNotHealthyException() from e
        except Exception as e:
            self.logger.error(e)
            raise Exception("Something went wrong while canceling job") from e

    async def get_webbackend_connection(
        self, connection_id: str, refresh_catalog: bool
    ) -> Dict[str, Any]:
        """
        Get connection with catalog diff
        """
        get_connection_url = self.airbyte_base_url + "/web_backend/connections/get"

        try:
            response = await self._client.post(
                get_connection_url,
                json={
                    "connectionId": connection_id,
                    "withRefreshedCatalog": refresh_catalog,
                },
            )
            response.raise_for_status()
            self.logger.info(
                "Fetched webbackend connection info for connection ID: %s",
                connection_id,
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double "
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def update_webbackend_connection(
        self, connection_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Patch style update of the connection
        connectionId is in the payload
        """
        get_connection_url = self.airbyte_base_url + "/web_backend/connections/update"

        try:
            payload["connectionId"] = connection_id
            response = await self._client.post(
                get_connection_url,
                json=payload,
            )
            response.raise_for_status()
            self.logger.info(
                "Updated connection ; ID: %s",
                payload["connectionId"],
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise err.ConnectionNotFoundException(
                    f"Connection {payload['connectionId']} not found, please double"
                    f"check the connection_id."
                ) from e

            raise err.AirbyteServerNotHealthyException() from e

    async def create_client(self) -> httpx.AsyncClient:
        """Convencience method to create a new httpx.AsyncClient.

        To be removed in favor of using the entire `AirbyteClient` class
        as a context manager.
        """
        warn(
            "Use of this method will be removed in a future release - "
            "please use the `AirbyteClient` class as a context manager.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._client

    async def __aenter__(self):
        """Context manager entry point."""
        if self._closed:
            raise RuntimeError(
                "The client cannot be started again after it has been closed."
            )
        if self._started:
            raise RuntimeError("The client cannot be started more than once.")

        self._started = True

        await self.check_health_status(self._client)

        return self

    async def __aexit__(self, *exc):
        """Context manager exit point."""

        self._closed = True
        await self._client.__aexit__()
