"""Suite-wide test guards."""

import copy
import json
import os
from unittest.mock import MagicMock, patch

import django
import pytest

# Set to a file path to record every test that reaches an email path (debugging aid only).
_SES_PROBE = os.getenv("DDPUI_TEST_SES_PROBE")


@pytest.fixture(autouse=True)
def _never_send_real_email(monkeypatch, request):
    """Stub the SES client for EVERY test, always.

    Real credentials (SES_ACCESS_KEY_ID / SES_SECRET_ACCESS_KEY / SES_SENDER_EMAIL) are present
    in a normal .env, and `awsses.send_text_message` calls `_get_ses_client()` unconditionally —
    so any test reaching an email path actually delivers mail to real people. That has happened:
    the trial welcome email and the teardown/cleanup ops alerts both fire from paths several
    tests exercise, and `send_trial_ops_alert` swallows its own errors, so nothing even failed
    to reveal it.

    Autouse and suite-wide on purpose — an opt-in guard is one forgotten @patch away from mailing
    someone. Tests that assert on email content should still patch the specific `awsses.send_*`
    function; this only guarantees the floor.
    """

    def _stub():
        if _SES_PROBE:
            with open(_SES_PROBE, "a", encoding="utf-8") as fh:
                fh.write(request.node.nodeid + "\n")
        return MagicMock()

    monkeypatch.setattr("ddpui.utils.awsses._get_ses_client", _stub)
    yield


# ---------------------------------------------------------------------------------------------
# data regions (multi-region Airbyte)
# ---------------------------------------------------------------------------------------------
# region modules touch Django models at import time, so set Django up before importing them
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
django.setup()

from ddpui.core.regions import airbyte_credentials  # noqa: E402
from ddpui.ddpairbyte import airbyte_service  # noqa: E402
from ddpui.models.org import Org, region_queue_config  # noqa: E402
from ddpui.schemas.data_region_schema import AirbyteServerConfig  # noqa: E402

TEST_SECRET_IN = "dalgoAirbyteRegion-test-in"
TEST_SECRET_AF = "dalgoAirbyteRegion-test-af"
TEST_AF_POOL = "staging_af_eks_work_pool"

REGION_CONFIG_IN = {
    "aws_region": "ap-south-1",
    "country": "India",
    "airbyte_secret_name": TEST_SECRET_IN,
}
REGION_CONFIG_AF = {
    "aws_region": "af-south-1",
    "country": "ZA",
    "airbyte_secret_name": TEST_SECRET_AF,
}

REGION_SECRET_VALUES = {
    TEST_SECRET_IN: {
        "server_host": "airbyte-in.example.org",
        "server_port": "8000",
        "api_version": "v1",
        "use_ssl": False,
        "api_token": "in-token-value",
    },
    TEST_SECRET_AF: {
        "server_host": "airbyte-af-staging-internal.dalgo.org",
        "server_port": "443",
        "api_version": "v1",
        "use_ssl": True,
        "api_token": "af-token-value",
    },
}

TEST_AVAILABLE_DATA_REGIONS = {
    "in": {
        "label": "India (Mumbai)",
        "aws_region": "ap-south-1",
        "airbyte_secret_name": TEST_SECRET_IN,
        "prefect_work_pool": "staging_eks_work_pool",
        "airbyte_ui_url": "https://airbyte-in.example.org",
    },
    "af": {
        "label": "Africa (Cape Town)",
        "aws_region": "af-south-1",
        "airbyte_secret_name": TEST_SECRET_AF,
        "prefect_work_pool": TEST_AF_POOL,
        "airbyte_ui_url": None,
    },
}


@pytest.fixture(autouse=True)
def _reset_region_caches():
    """Region secrets and HTTP sessions are cached per process; never leak them across tests"""
    airbyte_credentials.clear_cache()
    airbyte_service.clear_sessions()
    yield
    airbyte_credentials.clear_cache()
    airbyte_service.clear_sessions()


@pytest.fixture
def test_data_regions(settings):
    """AVAILABLE_DATA_REGIONS pointing at the test secret names, both regions enabled"""
    # a copy per test: tests may blank a region's prefect_work_pool
    settings.AVAILABLE_DATA_REGIONS = copy.deepcopy(TEST_AVAILABLE_DATA_REGIONS)
    settings.ENABLED_DATA_REGIONS = ["in", "af"]
    return settings


@pytest.fixture
def mock_region_secrets(test_data_regions):
    """Serves both test region secrets from a fake Secrets Manager client"""

    def get_secret_value(SecretId):  # pylint: disable=invalid-name
        if SecretId not in REGION_SECRET_VALUES:
            raise Exception(f"ResourceNotFoundException: {SecretId}")
        return {"SecretString": json.dumps(REGION_SECRET_VALUES[SecretId])}

    client = MagicMock()
    client.get_secret_value.side_effect = get_secret_value
    with patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client", return_value=client
    ):
        yield client


def _server(secret_name: str, aws_region: str) -> AirbyteServerConfig:
    values = REGION_SECRET_VALUES[secret_name]
    return AirbyteServerConfig(
        secret_name=secret_name,
        aws_region=aws_region,
        server_host=values["server_host"],
        server_port=values["server_port"],
        api_version=values["api_version"],
        use_ssl=values["use_ssl"],
        api_token=values["api_token"],
    )


@pytest.fixture
def airbyte_server_in() -> AirbyteServerConfig:
    """Backend-side Airbyte connection of the home region"""
    return _server(TEST_SECRET_IN, "ap-south-1")


@pytest.fixture
def airbyte_server_af() -> AirbyteServerConfig:
    """Backend-side Airbyte connection of the Africa region"""
    return _server(TEST_SECRET_AF, "af-south-1")


@pytest.fixture
def org_in(db):
    """An org in the home region"""
    return Org.objects.create(
        name="Org In", slug="org-in", airbyte_workspace_id="ws-in", region_config=REGION_CONFIG_IN
    )


@pytest.fixture
def org_af(db):
    """An org in the Africa region, on the Africa work pool"""
    return Org.objects.create(
        name="Org Af",
        slug="org-af",
        airbyte_workspace_id="ws-af",
        region_config=REGION_CONFIG_AF,
        queue_config=region_queue_config(TEST_AF_POOL),
    )
