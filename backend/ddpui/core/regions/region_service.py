"""RegionService: the single owner of 'which data region is this org in, and how do I reach it'"""

from django.conf import settings

from ddpui.core.regions import airbyte_credentials
from ddpui.core.regions.exceptions import RegionConfigError, RegionValidationError
from ddpui.models.org import Org, get_default_queue_config, region_queue_config
from ddpui.schemas.data_region_schema import (
    AirbyteFlowServerConfig,
    AirbyteServerConfig,
    DataRegionOption,
    OrgRegionConfig,
)
from ddpui.utils.custom_logger import CustomLogger

logger = CustomLogger("ddpui.regions")

# default country of a home-region (Mumbai) org when none is given
HOME_COUNTRY = "India"


class RegionService:
    """Resolves an org's data region (from the DB, never the JWT) to its Airbyte + Prefect config"""

    @staticmethod
    def home_region_config(country: str = HOME_COUNTRY) -> OrgRegionConfig:
        """region_config of a home-region (Mumbai) org"""
        home = settings.AVAILABLE_DATA_REGIONS[settings.HOME_DATA_REGION]
        return OrgRegionConfig(
            aws_region=home["aws_region"],
            country=country,
            airbyte_secret_name=home["airbyte_secret_name"],
        )

    @staticmethod
    def get_region_config(org: Org) -> OrgRegionConfig:
        """The org's validated region_config; NULL (old rows / rollback) means home region"""
        if org.region_config is None:
            logger.warning("org %s has no region_config, treating as home region", org.slug)
            return RegionService.home_region_config()
        return OrgRegionConfig(**org.region_config)

    @staticmethod
    def is_home_region(org: Org) -> bool:
        """True if the org's Airbyte runs in the home region"""
        return RegionService.get_region_config(org).aws_region == settings.HOME_AWS_REGION

    @staticmethod
    def build_region_config(code: str, country: str | None) -> OrgRegionConfig:
        """region_config for a NEW org. Validates against the enabled regions."""
        if code not in settings.ENABLED_DATA_REGIONS or code not in settings.AVAILABLE_DATA_REGIONS:
            raise RegionValidationError(f"data region '{code}' is not available")
        country = (country or "").strip()
        if code != settings.HOME_DATA_REGION and not country:
            raise RegionValidationError("country is required for this data region")
        spec = settings.AVAILABLE_DATA_REGIONS[code]
        try:
            return OrgRegionConfig(
                aws_region=spec["aws_region"],
                country=country or HOME_COUNTRY,
                airbyte_secret_name=spec["airbyte_secret_name"],
            )
        except ValueError as err:  # pydantic ValidationError, e.g. a too-long country
            raise RegionValidationError(f"invalid country '{country}'") from err

    @staticmethod
    def list_selectable_regions() -> list[DataRegionOption]:
        """Regions a superadmin may pick for a new org in this deployment"""
        return [
            DataRegionOption(code=code, label=spec["label"], aws_region=spec["aws_region"])
            for code, spec in settings.AVAILABLE_DATA_REGIONS.items()
            if code in settings.ENABLED_DATA_REGIONS
        ]

    @staticmethod
    def region_code_for(cfg: OrgRegionConfig) -> str | None:
        """'in', 'af', ... for a region_config; None if the aws_region is unknown"""
        for code, spec in settings.AVAILABLE_DATA_REGIONS.items():
            if spec["aws_region"] == cfg.aws_region:
                return code
        return None

    @staticmethod
    def region_settings_for(cfg: OrgRegionConfig) -> dict:
        """The AVAILABLE_DATA_REGIONS entry of a region_config: matched on airbyte_secret_name,
        else aws_region. Raises RegionConfigError if neither matches."""
        regions = settings.AVAILABLE_DATA_REGIONS.values()
        for spec in regions:
            if spec["airbyte_secret_name"] == cfg.airbyte_secret_name:
                return spec
        for spec in regions:
            if spec["aws_region"] == cfg.aws_region:
                return spec
        raise RegionConfigError(f"no data region configured for {cfg.airbyte_secret_name}")

    # ---- Airbyte ----
    @staticmethod
    def airbyte_server_for_config(cfg: OrgRegionConfig) -> AirbyteServerConfig:
        """Backend-side Airbyte connection for a region_config"""
        return airbyte_credentials.server_config(cfg.airbyte_secret_name, cfg.aws_region)

    @staticmethod
    def airbyte_server_for_org(org: Org) -> AirbyteServerConfig:
        """Backend-side Airbyte connection for the org's region. Pass it as `server=`."""
        return RegionService.airbyte_server_for_config(RegionService.get_region_config(org))

    @staticmethod
    def airbyte_server_for_org_id(org_id: int | None) -> AirbyteServerConfig:
        """For Celery tasks that get an org_id kwarg. None = message queued by code that did not
        send org_id yet (during a deploy): the home region, which is correct for every org until
        a non-home org exists."""
        if org_id is None:
            logger.warning("no org_id given, using the home region airbyte server")
            return RegionService.home_airbyte_server()
        return RegionService.airbyte_server_for_org(Org.objects.get(id=org_id))

    @staticmethod
    def home_airbyte_server() -> AirbyteServerConfig:
        """Only for callers with no org at all (the unused Airbyte webhook, old Celery messages)"""
        return RegionService.airbyte_server_for_config(RegionService.home_region_config())

    @staticmethod
    def airbyte_flow_server_for_org(org: Org) -> AirbyteFlowServerConfig:
        """Same host as the backend (airbyte_server_for_org); used for the Prefect AirbyteServer
        block of the org"""
        cfg = RegionService.get_region_config(org)
        return airbyte_credentials.flow_server_config(cfg.airbyte_secret_name)

    @staticmethod
    def airbyte_ui_url_for_org(org: Org) -> str | None:
        """Base URL of the org's Airbyte UI for admin links; None/empty means omit the link"""
        cfg = RegionService.get_region_config(org)
        return RegionService.region_settings_for(cfg).get("airbyte_ui_url") or None

    # ---- Prefect ----
    @staticmethod
    def prefect_work_pool_for_config(cfg: OrgRegionConfig) -> str:
        """The Prefect work pool of a region (from settings). Raises RegionConfigError if unset:
        never fall back to the home region's pool, that would run the org's flows in Mumbai."""
        pool = RegionService.region_settings_for(cfg).get("prefect_work_pool")
        if not pool:
            raise RegionConfigError(
                f"no prefect work pool configured for {cfg.airbyte_secret_name}"
            )
        return pool

    @staticmethod
    def prefect_work_pool_for_org(org: Org) -> str:
        """The Prefect work pool of the org's region"""
        return RegionService.prefect_work_pool_for_config(RegionService.get_region_config(org))

    @staticmethod
    def queue_config_for_new_org(cfg: OrgRegionConfig) -> dict:
        """queue_config for a NEW org. Home region: unchanged env-based default."""
        if cfg.aws_region == settings.HOME_AWS_REGION:
            return get_default_queue_config()
        return region_queue_config(RegionService.prefect_work_pool_for_config(cfg))
