"""Schemas for data regions (multi-region Airbyte)"""

from ninja import Schema
from pydantic import ConfigDict, Field, SecretStr


class OrgRegionConfig(Schema):
    """Shape of Org.region_config. Written once at org creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aws_region: str = Field(pattern=r"^[a-z]{2}-[a-z]+-\d$")
    country: str = Field(pattern=r"^[A-Z]{2}$")  # ISO-3166-1 alpha-2
    airbyte_secret_name: str = Field(pattern=r"^dalgoAirbyteRegion-[a-z]+-[a-z]{2}$")


class AirbyteRegionSecret(Schema):
    """Exact shape of a region secret (dalgoAirbyteRegion-<env>-<code>) in Secrets Manager.
    Airbyte connection creds only; non-secret region config (work pool, UI url) is in settings."""

    # coerce_numbers_to_str: tolerate "server_port": 443 written by hand into the secret
    model_config = ConfigDict(extra="forbid", frozen=True, coerce_numbers_to_str=True)

    server_host: str
    server_port: str
    api_version: str = "v1"
    use_ssl: bool = False
    api_token: SecretStr  # may be ""; repr/str/model_dump_json show '**********'


class AirbyteServerConfig(Schema):
    """Backend-side connection to one region's Airbyte. Passed as `server=`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    secret_name: str  # identity: cache key, session key, log field
    aws_region: str
    server_host: str
    server_port: str
    api_version: str
    use_ssl: bool
    api_token: SecretStr

    @property
    def base_url(self) -> str:
        """e.g. https://host:443/api/v1"""
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.server_host}:{self.server_port}/api/{self.api_version}"


class AirbyteFlowServerConfig(Schema):
    """What goes into the Prefect AirbyteServer block: the same host/port/ssl as the backend
    (AirbyteServerConfig) minus the token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    server_host: str
    server_port: str
    api_version: str
    use_ssl: bool


class DataRegionOption(Schema):
    """One entry of the region picker on Create Org."""

    code: str
    label: str
    aws_region: str
