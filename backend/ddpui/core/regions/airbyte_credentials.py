"""
Per-region Airbyte credentials, read from Secrets Manager and cached in-process.

This module must NOT access the ORM: airbyte_service (which promises not to touch the Dalgo
database) uses it to refresh credentials after a 401.

Security: secret values are never logged. Only the secret *name* is. The raw secret string is
held in a local named `secret`, which Sentry's scrubber blanks.
"""

import json
import os
import threading

from cachetools import TTLCache
from django.conf import settings

from ddpui.core.regions.exceptions import RegionConfigError
from ddpui.schemas.data_region_schema import (
    AirbyteFlowServerConfig,
    AirbyteRegionSecret,
    AirbyteServerConfig,
)
from ddpui.utils import secretsmanager
from ddpui.utils.custom_logger import CustomLogger

logger = CustomLogger("ddpui.regions")

CACHE_TTL_SECONDS = 300

# keyed by secret name; cachetools is not thread-safe, hence the lock
_cache: TTLCache = TTLCache(maxsize=32, ttl=CACHE_TTL_SECONDS)
_lock = threading.Lock()


def home_secret_name() -> str:
    """Secret name of the home region (Mumbai)"""
    return settings.AVAILABLE_DATA_REGIONS[settings.HOME_DATA_REGION]["airbyte_secret_name"]


def _env_fallback() -> AirbyteRegionSecret:
    """Home region (Mumbai) only, for ONE release (removed in T13): today's AIRBYTE_* env vars"""
    try:
        return AirbyteRegionSecret(
            server_host=os.getenv("AIRBYTE_SERVER_HOST"),
            server_port=os.getenv("AIRBYTE_SERVER_PORT"),
            api_version=os.getenv("AIRBYTE_SERVER_APIVER"),
            use_ssl=os.getenv("AIRBYTE_USE_SSL", "false").lower() == "true",
            api_token=os.getenv("AIRBYTE_API_TOKEN"),
        )
    except Exception:  # ValidationError could echo the token
        raise RegionConfigError(
            "home region secret unreadable and AIRBYTE_* env fallback is incomplete"
        ) from None


def _fetch(secret_name: str, allow_env_fallback: bool = True) -> AirbyteRegionSecret:
    """Reads and parses the secret. Never falls back to the home region for another region."""
    try:
        secret = secretsmanager.get_client().get_secret_value(SecretId=secret_name)["SecretString"]
        return AirbyteRegionSecret(**json.loads(secret))
    except Exception:  # boto error, missing secret, bad JSON or ValidationError
        if allow_env_fallback and secret_name == home_secret_name():
            logger.warning("could not read %s, using AIRBYTE_* env fallback", secret_name)
            return _env_fallback()
        # never fall back to Mumbai for a non-Mumbai region: that would send its data to India
        # `from None`: the original error may carry the secret string in its message
        raise RegionConfigError(f"could not read airbyte secret {secret_name}") from None


def read_region_secret_uncached(secret_name: str) -> AirbyteRegionSecret:
    """Reads the secret from SM with no cache and no env fallback (for health checks).
    Raises RegionConfigError if it cannot be read or parsed."""
    return _fetch(secret_name, allow_env_fallback=False)


def get_region_secret(secret_name: str) -> AirbyteRegionSecret:
    """Cached read of a region secret"""
    with _lock:
        cached = _cache.get(secret_name)
    if cached is not None:
        return cached
    loaded = _fetch(secret_name)  # network call outside the lock
    with _lock:
        _cache[secret_name] = loaded
    return loaded


def invalidate(secret_name: str) -> None:
    """Drop a cached secret, e.g. after Airbyte answered 401"""
    with _lock:
        _cache.pop(secret_name, None)


def clear_cache() -> None:
    """Drop every cached secret (tests, management commands)"""
    with _lock:
        _cache.clear()


def server_config(secret_name: str, aws_region: str) -> AirbyteServerConfig:
    """Backend-side Airbyte connection for a region"""
    return build_server_config(secret_name, aws_region, get_region_secret(secret_name))


def build_server_config(
    secret_name: str, aws_region: str, region_secret: AirbyteRegionSecret
) -> AirbyteServerConfig:
    """AirbyteServerConfig from an already-loaded region secret"""
    return AirbyteServerConfig(
        secret_name=secret_name,
        aws_region=aws_region,
        server_host=region_secret.server_host,
        server_port=region_secret.server_port,
        api_version=region_secret.api_version,
        use_ssl=region_secret.use_ssl,
        api_token=region_secret.api_token,
    )


def flow_server_config(secret_name: str) -> AirbyteFlowServerConfig:
    """Same host as the backend; used for the Prefect AirbyteServer block of the region's orgs"""
    region_secret = get_region_secret(secret_name)
    return AirbyteFlowServerConfig(
        server_host=region_secret.server_host,
        server_port=region_secret.server_port,
        api_version=region_secret.api_version,
        use_ssl=region_secret.use_ssl,
    )
