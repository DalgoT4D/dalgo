"""create_organization: region-aware org creation (T8)"""

import os
from unittest.mock import Mock, patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.core.orgfunctions import create_organization
from ddpui.ddpprefect import AIRBYTESERVER
from ddpui.models.org import Org, OrgPrefectBlockv1, get_default_queue_config
from ddpui.schemas.org_schema import CreateOrgSchema
from ddpui.tests.conftest import REGION_CONFIG_AF, REGION_CONFIG_IN, TEST_AF_POOL

pytestmark = pytest.mark.django_db


def _payload(**kwargs) -> CreateOrgSchema:
    return CreateOrgSchema(
        name=kwargs.pop("name", "Residency Test"),
        base_plan="Free",
        can_upgrade_plan=False,
        subscription_duration="Yearly",
        superset_included=False,
        **kwargs,
    )


@pytest.fixture
def mock_airbyte_and_prefect():
    """the org's airbyte (workspace) and prefect-proxy (server block)"""
    with patch(
        "ddpui.ddpairbyte.airbytehelpers.airbyte_service.create_workspace",
        return_value={"workspaceId": "ws-new", "name": "ws", "initialSetupComplete": False},
    ) as mock_create_workspace, patch(
        "ddpui.ddpairbyte.airbytehelpers.prefect_service.get_airbyte_server_block_id",
        return_value=None,
    ), patch(
        "ddpui.ddpairbyte.airbytehelpers.prefect_service.create_airbyte_server_block",
        return_value=("block-id", "residency-test-airbyte-server"),
    ) as mock_create_block, patch(
        "ddpui.core.orgfunctions.add_custom_connectors_to_workspace.delay"
    ) as mock_delay:
        yield Mock(
            create_workspace=mock_create_workspace,
            create_block=mock_create_block,
            delay=mock_delay,
        )


def test_create_org_default_is_home_region(
    mock_region_secrets, mock_airbyte_and_prefect, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        org, error = create_organization(_payload())

    assert error is None
    assert org.region_config == REGION_CONFIG_IN
    assert org.queue_config == get_default_queue_config()
    server = mock_airbyte_and_prefect.create_workspace.call_args.kwargs["server"]
    assert server.aws_region == "ap-south-1"
    mock_airbyte_and_prefect.delay.assert_called_once()
    assert mock_airbyte_and_prefect.delay.call_args.kwargs["org_id"] == org.id


def test_create_org_af(
    mock_region_secrets, mock_airbyte_and_prefect, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        org, error = create_organization(_payload(data_region="af", country="ZA"))

    assert error is None
    assert org.region_config == REGION_CONFIG_AF
    assert {queue["workpool"] for queue in org.queue_config.values()} == {TEST_AF_POOL}
    assert all(queue["is_workpool_eks"] for queue in org.queue_config.values())
    assert org.airbyte_workspace_id == "ws-new"
    server = mock_airbyte_and_prefect.create_workspace.call_args.kwargs["server"]
    assert server.aws_region == "af-south-1"
    block_name, flow_server = mock_airbyte_and_prefect.create_block.call_args.args
    assert flow_server.server_host == "airbyte-af-staging-internal.dalgo.org"
    assert flow_server.server_port == "443"
    assert flow_server.use_ssl is True
    assert OrgPrefectBlockv1.objects.filter(org=org, block_type=AIRBYTESERVER).exists()
    assert mock_airbyte_and_prefect.delay.call_args.kwargs["org_id"] == org.id


def test_custom_connectors_enqueued_only_after_commit(
    mock_region_secrets, mock_airbyte_and_prefect, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        create_organization(_payload())
    mock_airbyte_and_prefect.delay.assert_not_called()
    assert len(callbacks) == 1


@pytest.mark.parametrize(
    "kwargs,enabled,message",
    [
        ({"data_region": "af", "country": "ZA"}, ["in"], "not available"),
        ({"data_region": "xx", "country": "ZA"}, ["in", "af", "xx"], "not available"),
        ({"data_region": "af"}, ["in", "af"], "country is required"),
        ({"data_region": "af", "country": "x" * 101}, ["in", "af"], "invalid country"),
    ],
)
def test_create_org_bad_region_creates_nothing(
    kwargs, enabled, message, test_data_regions, mock_region_secrets, mock_airbyte_and_prefect
):
    test_data_regions.ENABLED_DATA_REGIONS = enabled
    org, error = create_organization(_payload(**kwargs))
    assert org is None
    assert message in error
    assert not Org.objects.filter(name="Residency Test").exists()
    mock_airbyte_and_prefect.create_workspace.assert_not_called()


def test_create_org_unreadable_region_secret_creates_nothing(
    test_data_regions, mock_airbyte_and_prefect
):
    with patch(
        "ddpui.core.regions.airbyte_credentials.secretsmanager.get_client",
        side_effect=Exception("AccessDenied"),
    ):
        org, error = create_organization(_payload(data_region="af", country="ZA"))
    assert org is None
    assert "not available" in error
    assert not Org.objects.filter(name="Residency Test").exists()
    mock_airbyte_and_prefect.create_workspace.assert_not_called()


def test_create_org_airbyte_failure_deletes_org(mock_region_secrets, mock_airbyte_and_prefect):
    mock_airbyte_and_prefect.create_workspace.side_effect = Exception("airbyte down")
    org, error = create_organization(_payload(data_region="af", country="ZA"))
    assert org is None
    assert error == "could not create airbyte workspace"
    assert not Org.objects.filter(name="Residency Test").exists()
