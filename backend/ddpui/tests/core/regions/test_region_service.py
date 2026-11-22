import os
from unittest.mock import patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.core.regions.exceptions import RegionConfigError, RegionValidationError
from ddpui.core.regions.region_service import RegionService
from ddpui.models.org import Org, get_default_queue_config
from ddpui.ddpprefect import (
    CONNECTION_SYNC_QUEUE,
    EDR_WORK_QUEUE,
    MANUL_DBT_WORK_QUEUE,
    SCHEDULED_PIPELINE_QUEUE,
)
from ddpui.schemas.data_region_schema import OrgRegionConfig
from ddpui.tests.conftest import (
    REGION_CONFIG_AF,
    TEST_AF_POOL,
    TEST_SECRET_AF,
    TEST_SECRET_IN,
)

pytestmark = pytest.mark.django_db


def test_get_region_config(org_af):
    cfg = RegionService.get_region_config(org_af)
    assert cfg == OrgRegionConfig(**REGION_CONFIG_AF)
    assert RegionService.is_home_region(org_af) is False


def test_null_region_config_is_home_with_warning(test_data_regions):
    org = Org(name="old", slug="old", region_config=None)
    with patch("ddpui.core.regions.region_service.logger") as mock_logger:
        cfg = RegionService.get_region_config(org)
    assert cfg.aws_region == "ap-south-1"
    assert cfg.airbyte_secret_name == TEST_SECRET_IN
    assert cfg.country == "India"
    mock_logger.warning.assert_called_once()
    assert RegionService.is_home_region(org) is True


def test_build_region_config_af(test_data_regions):
    cfg = RegionService.build_region_config("af", "  South Africa ")
    assert cfg.aws_region == "af-south-1"
    assert cfg.country == "South Africa"  # trimmed, case kept
    assert cfg.airbyte_secret_name == TEST_SECRET_AF


def test_build_region_config_home_defaults_country(test_data_regions):
    cfg = RegionService.build_region_config("in", None)
    assert cfg.country == "India"
    assert cfg.aws_region == "ap-south-1"


def test_build_region_config_disabled_region(test_data_regions):
    test_data_regions.ENABLED_DATA_REGIONS = ["in"]
    with pytest.raises(RegionValidationError):
        RegionService.build_region_config("af", "ZA")


def test_build_region_config_unknown_region(test_data_regions):
    test_data_regions.ENABLED_DATA_REGIONS = ["in", "af", "xx"]
    with pytest.raises(RegionValidationError):
        RegionService.build_region_config("xx", "ZA")


@pytest.mark.parametrize("country", [None, "", "   "])
def test_build_region_config_missing_country(country, test_data_regions):
    with pytest.raises(RegionValidationError):
        RegionService.build_region_config("af", country)


def test_build_region_config_bad_country(test_data_regions):
    with pytest.raises(RegionValidationError):
        RegionService.build_region_config("af", "x" * 101)


def test_list_selectable_regions(test_data_regions):
    test_data_regions.ENABLED_DATA_REGIONS = ["in"]
    regions = RegionService.list_selectable_regions()
    assert [r.code for r in regions] == ["in"]
    test_data_regions.ENABLED_DATA_REGIONS = ["in", "af"]
    regions = RegionService.list_selectable_regions()
    assert [(r.code, r.aws_region) for r in regions] == [
        ("in", "ap-south-1"),
        ("af", "af-south-1"),
    ]


def test_region_code_for(test_data_regions):
    assert RegionService.region_code_for(OrgRegionConfig(**REGION_CONFIG_AF)) == "af"
    unknown = OrgRegionConfig(**{**REGION_CONFIG_AF, "aws_region": "eu-west-1"})
    assert RegionService.region_code_for(unknown) is None


def test_airbyte_server_for_org(org_in, org_af, mock_region_secrets):
    server_af = RegionService.airbyte_server_for_org(org_af)
    server_in = RegionService.airbyte_server_for_org(org_in)
    assert server_af.aws_region == "af-south-1"
    assert server_af.base_url == "https://airbyte-af-staging-internal.dalgo.org:443/api/v1"
    assert server_in.aws_region == "ap-south-1"
    assert server_in.base_url == "http://airbyte-in.example.org:8000/api/v1"


def test_home_airbyte_server(mock_region_secrets):
    server = RegionService.home_airbyte_server()
    assert server.secret_name == TEST_SECRET_IN


def test_airbyte_flow_server_for_org(org_af, mock_region_secrets):
    flow = RegionService.airbyte_flow_server_for_org(org_af)
    assert flow.server_host == "airbyte-af-staging-internal.dalgo.org"
    assert flow.server_port == "443"
    assert flow.use_ssl is True


def test_airbyte_flow_server_is_backend_host(org_in, org_af, mock_region_secrets):
    """the prefect block uses the same host/port/ssl/api version as the backend"""
    for org in (org_in, org_af):
        server = RegionService.airbyte_server_for_org(org)
        flow = RegionService.airbyte_flow_server_for_org(org)
        assert flow.model_dump() == server.model_dump(
            include={"server_host", "server_port", "api_version", "use_ssl"}
        )


def test_region_settings_for(test_data_regions):
    regions = test_data_regions.AVAILABLE_DATA_REGIONS
    assert RegionService.region_settings_for(OrgRegionConfig(**REGION_CONFIG_AF)) is regions["af"]
    # matched on the secret name first, then on the aws region
    by_aws_region = OrgRegionConfig(
        **{**REGION_CONFIG_AF, "airbyte_secret_name": "dalgoAirbyteRegion-other-af"}
    )
    assert RegionService.region_settings_for(by_aws_region) is regions["af"]
    unknown = OrgRegionConfig(
        aws_region="eu-west-1", country="IE", airbyte_secret_name="dalgoAirbyteRegion-test-eu"
    )
    with pytest.raises(RegionConfigError):
        RegionService.region_settings_for(unknown)


def test_airbyte_ui_url_for_org(org_in, org_af, test_data_regions):
    assert RegionService.airbyte_ui_url_for_org(org_in) == "https://airbyte-in.example.org"
    # not set in settings -> None (callers omit the link)
    assert RegionService.airbyte_ui_url_for_org(org_af) is None
    test_data_regions.AVAILABLE_DATA_REGIONS["af"]["airbyte_ui_url"] = ""
    assert RegionService.airbyte_ui_url_for_org(org_af) is None


def test_prefect_work_pool_for_org(org_in, org_af, test_data_regions):
    assert RegionService.prefect_work_pool_for_org(org_in) == "staging_eks_work_pool"
    assert RegionService.prefect_work_pool_for_org(org_af) == TEST_AF_POOL


def test_af_org_without_work_pool_fails_loudly(org_af, test_data_regions):
    """T9: never silently fall back to Mumbai's pool"""
    test_data_regions.AVAILABLE_DATA_REGIONS["af"]["prefect_work_pool"] = ""
    with pytest.raises(RegionConfigError, match="no prefect work pool"):
        RegionService.prefect_work_pool_for_org(org_af)
    with pytest.raises(RegionConfigError, match="no prefect work pool"):
        RegionService.queue_config_for_new_org(OrgRegionConfig(**REGION_CONFIG_AF))


def test_queue_config_for_new_org_home(test_data_regions):
    cfg = RegionService.home_region_config()
    assert RegionService.queue_config_for_new_org(cfg) == get_default_queue_config()


def test_queue_config_for_new_org_af(mock_region_secrets):
    cfg = OrgRegionConfig(**REGION_CONFIG_AF)
    queue_config = RegionService.queue_config_for_new_org(cfg)
    assert queue_config == {
        "scheduled_pipeline_queue": {
            "name": SCHEDULED_PIPELINE_QUEUE,
            "workpool": TEST_AF_POOL,
            "is_workpool_eks": True,
        },
        "connection_sync_queue": {
            "name": CONNECTION_SYNC_QUEUE,
            "workpool": TEST_AF_POOL,
            "is_workpool_eks": True,
        },
        "transform_task_queue": {
            "name": MANUL_DBT_WORK_QUEUE,
            "workpool": TEST_AF_POOL,
            "is_workpool_eks": True,
        },
        "edr_queue": {"name": EDR_WORK_QUEUE, "workpool": TEST_AF_POOL, "is_workpool_eks": True},
    }


def test_queue_config_for_new_org_af_does_not_read_the_secret(test_data_regions):
    """the work pool comes from settings: an unreadable secret does not matter here"""
    with patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        side_effect=Exception("AccessDenied"),
    ):
        queue_config = RegionService.queue_config_for_new_org(OrgRegionConfig(**REGION_CONFIG_AF))
    assert {queue["workpool"] for queue in queue_config.values()} == {TEST_AF_POOL}
