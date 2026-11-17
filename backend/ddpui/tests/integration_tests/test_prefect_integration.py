"""Tests for the Prefect Service"""

import os
from uuid import uuid4
from ddpui.ddpprefect import prefect_service, schema
from ddpui.schemas.data_region_schema import AirbyteFlowServerConfig
import pytest

FLOW_SERVER = AirbyteFlowServerConfig(
    server_host=os.getenv("AIRBYTE_SERVER_HOST", "localhost"),
    server_port=os.getenv("AIRBYTE_SERVER_PORT", "8000"),
    api_version=os.getenv("AIRBYTE_SERVER_APIVER", "v1"),
    use_ssl=os.getenv("AIRBYTE_USE_SSL", "false").lower() == "true",
)


@pytest.mark.skip(reason="Skipping this test as airbyte integraion needs to be done")
class TestAirbyteServer:
    """tests creation and retrieval of an airbyte server block"""

    @staticmethod
    def test_create_serverblock():
        """creates a server block"""
        TestAirbyteServer.BLOCK_NAME = "test-" + str(uuid4())
        block_id, block_name = prefect_service.create_airbyte_server_block(
            TestAirbyteServer.BLOCK_NAME, FLOW_SERVER
        )
        assert block_id is not None
        assert block_name is not None
        TestAirbyteServer.block_id = block_id

    @staticmethod
    def test_fetch_serverblock():
        """fetches the id of the block we just created, verifies that it is what we saved"""
        block_id = prefect_service.get_airbyte_server_block_id(TestAirbyteServer.BLOCK_NAME)
        assert block_id == TestAirbyteServer.block_id

    @staticmethod
    def test_delete_serverblock():
        """cleans up"""
        prefect_service.delete_airbyte_server_block(TestAirbyteServer.block_id)


@pytest.mark.skip(reason="Skipping this test as airbyte integraion needs to be done")
class TestAirbyteConnection:
    """tests the creation and retrieval of airbyte connection blocks"""

    @staticmethod
    def test_start():
        """sets up an airbyte server block"""
        TestAirbyteConnection.server_block_name = "test-srvr-" + str(uuid4())
        TestAirbyteConnection.airbyte_connection_id = str(uuid4())
        TestAirbyteConnection.connection_block_name = "test-conn-" + str(uuid4())
        TestAirbyteConnection.connection_block_id = None
        TestAirbyteConnection.server_block_id = prefect_service.create_airbyte_server_block(
            TestAirbyteConnection.server_block_name, FLOW_SERVER
        )[0]

    @staticmethod
    def test_end():
        """cleans up"""
        prefect_service.delete_airbyte_server_block(TestAirbyteConnection.server_block_id)
