import json
import os
from unittest.mock import MagicMock, patch

import django
import pytest
import sentry_sdk
from cachetools import TTLCache

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.core.regions import airbyte_credentials
from ddpui.core.regions.exceptions import RegionConfigError
from ddpui.schemas.data_region_schema import AirbyteRegionSecret
from ddpui.tests.conftest import REGION_SECRET_VALUES, TEST_SECRET_AF, TEST_SECRET_IN

AIRBYTE_ENV = {
    "AIRBYTE_SERVER_HOST": "env-host",
    "AIRBYTE_SERVER_PORT": "8000",
    "AIRBYTE_SERVER_APIVER": "v1",
    "AIRBYTE_API_TOKEN": "env-token-value",
    "AIRBYTE_USE_SSL": "false",
}


def _failing_client():
    client = MagicMock()
    client.get_secret_value.side_effect = Exception("AccessDenied")
    return client


def test_server_config_from_secret(mock_region_secrets):
    server = airbyte_credentials.server_config(TEST_SECRET_AF, "af-south-1")
    assert server.base_url == "https://airbyte-af-staging-internal.dalgo.org:443/api/v1"
    assert server.api_token.get_secret_value() == "af-token-value"
    assert server.secret_name == TEST_SECRET_AF
    assert server.aws_region == "af-south-1"


def test_flow_server_config_from_secret(mock_region_secrets):
    flow = airbyte_credentials.flow_server_config(TEST_SECRET_AF)
    assert flow.server_host == "airbyte-af-staging-internal.dalgo.org"
    assert flow.server_port == "443"
    assert flow.use_ssl is True
    assert flow.api_version == "v1"


def test_secret_is_cached(mock_region_secrets):
    airbyte_credentials.server_config(TEST_SECRET_AF, "af-south-1")
    airbyte_credentials.server_config(TEST_SECRET_AF, "af-south-1")
    airbyte_credentials.flow_server_config(TEST_SECRET_AF)
    assert mock_region_secrets.get_secret_value.call_count == 1


def test_cache_expires_after_ttl(mock_region_secrets):
    now = [0.0]
    cache = TTLCache(maxsize=32, ttl=300, timer=lambda: now[0])
    with patch.object(airbyte_credentials, "_cache", cache):
        airbyte_credentials.get_region_secret(TEST_SECRET_AF)
        now[0] = 299
        airbyte_credentials.get_region_secret(TEST_SECRET_AF)
        assert mock_region_secrets.get_secret_value.call_count == 1
        now[0] = 301
        airbyte_credentials.get_region_secret(TEST_SECRET_AF)
        assert mock_region_secrets.get_secret_value.call_count == 2


def test_invalidate_forces_reload(mock_region_secrets):
    airbyte_credentials.get_region_secret(TEST_SECRET_AF)
    airbyte_credentials.invalidate(TEST_SECRET_AF)
    airbyte_credentials.get_region_secret(TEST_SECRET_AF)
    assert mock_region_secrets.get_secret_value.call_count == 2


def test_numeric_port_is_tolerated(mock_region_secrets):
    values = {**REGION_SECRET_VALUES[TEST_SECRET_AF], "server_port": 443}
    mock_region_secrets.get_secret_value.side_effect = lambda SecretId: {
        "SecretString": json.dumps(values)
    }
    assert airbyte_credentials.get_region_secret(TEST_SECRET_AF).server_port == "443"


def test_malformed_non_home_secret_raises_without_leaking(mock_region_secrets):
    values = {**REGION_SECRET_VALUES[TEST_SECRET_AF], "unexpected_key": "x"}
    mock_region_secrets.get_secret_value.side_effect = lambda SecretId: {
        "SecretString": json.dumps(values)
    }
    with pytest.raises(RegionConfigError) as excinfo:
        airbyte_credentials.get_region_secret(TEST_SECRET_AF)
    assert "af-token-value" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


def test_non_home_failure_never_falls_back(test_data_regions):
    with patch.dict(os.environ, AIRBYTE_ENV), patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        return_value=_failing_client(),
    ):
        with pytest.raises(RegionConfigError) as excinfo:
            airbyte_credentials.server_config(TEST_SECRET_AF, "af-south-1")
    assert excinfo.value.__cause__ is None


def test_home_failure_uses_env_fallback(test_data_regions):
    with patch.dict(os.environ, AIRBYTE_ENV), patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        return_value=_failing_client(),
    ), patch.object(airbyte_credentials, "logger") as mock_logger:
        server = airbyte_credentials.server_config(TEST_SECRET_IN, "ap-south-1")
        secret = airbyte_credentials.get_region_secret(TEST_SECRET_IN)

    # exactly what abreq builds from the env today
    assert server.base_url == "http://env-host:8000/api/v1"
    assert server.api_token.get_secret_value() == "env-token-value"
    assert secret.server_host == "env-host"
    assert secret.server_port == "8000"
    assert secret.use_ssl is False
    flow = airbyte_credentials.flow_server_config(TEST_SECRET_IN)
    assert (flow.server_host, flow.server_port, flow.use_ssl) == ("env-host", "8000", False)
    mock_logger.warning.assert_called_once()
    assert "env-token-value" not in str(mock_logger.warning.call_args)


def test_home_failure_with_incomplete_env_raises(test_data_regions):
    env = {k: v for k, v in AIRBYTE_ENV.items() if k != "AIRBYTE_SERVER_PORT"}
    with patch.dict(os.environ, env, clear=False), patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        return_value=_failing_client(),
    ):
        os.environ.pop("AIRBYTE_SERVER_PORT", None)
        with pytest.raises(RegionConfigError):
            airbyte_credentials.get_region_secret(TEST_SECRET_IN)


def test_read_uncached_does_not_fall_back(test_data_regions):
    with patch.dict(os.environ, AIRBYTE_ENV), patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        return_value=_failing_client(),
    ):
        with pytest.raises(RegionConfigError):
            airbyte_credentials.read_region_secret_uncached(TEST_SECRET_IN)


def test_credentials_objects_hide_the_token(mock_region_secrets):
    secret = airbyte_credentials.get_region_secret(TEST_SECRET_AF)
    server = airbyte_credentials.server_config(TEST_SECRET_AF, "af-south-1")
    for obj in (secret, server):
        assert "af-token-value" not in repr(obj)
        assert "af-token-value" not in str(obj)
        assert "af-token-value" not in obj.model_dump_json()
        assert "af-token-value" not in f"{obj}"


def test_region_secret_schema_is_airbyte_creds_only():
    """the 5 connection fields; anything else (old flow_*/work pool/ui url keys) is rejected"""
    values = REGION_SECRET_VALUES[TEST_SECRET_AF]
    assert set(values) == {"server_host", "server_port", "api_version", "use_ssl", "api_token"}
    assert AirbyteRegionSecret(**{**values, "api_token": ""}).api_token.get_secret_value() == ""
    with pytest.raises(ValueError):
        AirbyteRegionSecret(**values, prefect_work_pool="pool")


def test_region_secret_schema_rejects_missing_token():
    values = {k: v for k, v in REGION_SECRET_VALUES[TEST_SECRET_AF].items() if k != "api_token"}
    with pytest.raises(ValueError):
        AirbyteRegionSecret(**values)


def test_sentry_scrubber_blanks_nested_secret_keys():
    """settings.py configures a recursive scrubber that also knows the region-secret keys"""
    scrubber = sentry_sdk.get_client().options["event_scrubber"]
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "parsed": {"api_token": "af-token-value", "host": "h"},
                                    "secret": "raw-secret-string",
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    scrubber.scrub_event(event)
    frame_vars = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert "af-token-value" not in str(frame_vars)
    assert "raw-secret-string" not in str(frame_vars)
