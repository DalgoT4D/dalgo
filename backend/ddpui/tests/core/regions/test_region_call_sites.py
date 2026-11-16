"""Region isolation at the call sites that have no request (Celery tasks, loops, cleanup)"""

import os
from unittest.mock import patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.celeryworkers.tasks import (
    add_custom_connectors_to_workspace,
    check_for_long_running_flow_runs,
    get_schema_catalog_task,
)
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from ddpui.core.regions.region_service import RegionService
from ddpui.ddpprefect import AIRBYTESERVER, DBTCORE
from ddpui.models.org import OrgPrefectBlockv1, OrgWarehouse
from ddpui.models.tasks import OrgTask, Task, TaskType
from ddpui.services.org_cleanup_service import OrgCleanupService

pytestmark = pytest.mark.django_db

CUSTOM_SOURCES = [
    {
        "name": "Avni",
        "docker_repository": "tech4dev/source-avni",
        "docker_image_tag": "0.2.1",
        "documentation_url": "",
    }
]


@patch("ddpui.celeryworkers.tasks.airbyte_service.create_custom_source_definition")
def test_add_custom_connectors_uses_org_region(mock_create, org_af, mock_region_secrets):
    add_custom_connectors_to_workspace.apply(
        args=["ws-af", CUSTOM_SOURCES], kwargs={"org_id": org_af.id}
    )
    assert mock_create.call_args.kwargs["server"].aws_region == "af-south-1"


@patch("ddpui.celeryworkers.tasks.airbyte_service.create_custom_source_definition")
def test_add_custom_connectors_without_org_id_uses_home(mock_create, mock_region_secrets):
    """messages queued by old code during a deploy have no org_id"""
    add_custom_connectors_to_workspace.apply(args=["ws-in", CUSTOM_SOURCES])
    assert mock_create.call_args.kwargs["server"] == RegionService.home_airbyte_server()
    assert mock_create.call_args.kwargs["server"].aws_region == "ap-south-1"


@patch("ddpui.celeryworkers.tasks.airbyte_service.get_source_schema_catalog", return_value={})
def test_get_schema_catalog_task_uses_org_region(mock_catalog, org_af, mock_region_secrets):
    get_schema_catalog_task("task-key-af", "ws-af", "src-1", org_id=org_af.id)
    assert mock_catalog.call_args.kwargs["server"].aws_region == "af-south-1"


@patch("ddpui.celeryworkers.tasks.airbyte_service.get_source_schema_catalog", return_value={})
def test_get_schema_catalog_task_without_org_id_uses_home(mock_catalog, mock_region_secrets):
    get_schema_catalog_task("task-key-in", "ws-in", "src-1")
    assert mock_catalog.call_args.kwargs["server"].aws_region == "ap-south-1"


def test_org_cleanup_only_talks_to_org_region(org_af, mock_region_secrets):
    with patch("ddpui.services.org_cleanup_service.airbyte_service") as mock_airbyte_service:
        mock_airbyte_service.get_sources.return_value = {"sources": [{"sourceId": "s1"}]}
        mock_airbyte_service.get_destinations.return_value = {
            "destinations": [{"destinationId": "d1"}]
        }
        OrgCleanupService(org_af, dry_run=False).delete_airbyte_workspace()
    calls = [c for c in mock_airbyte_service.mock_calls if "server" in c.kwargs]
    assert len(calls) == 5  # get_sources, delete_source, get_destinations, delete_destination, ws
    assert all(c.kwargs["server"].aws_region == "af-south-1" for c in calls)


@patch("ddpui.management.commands.setconnectionnamesinmeta.airbyte_service.get_connection")
def test_command_setconnectionnamesinmeta_uses_org_region(
    mock_get_connection, org_in, org_af, mock_region_secrets
):
    task = Task.objects.create(type=TaskType.AIRBYTE, slug="airbyte-sync-t4c", label="sync")
    OrgTask.objects.create(org=org_in, task=task, connection_id="conn-in")
    OrgTask.objects.create(org=org_af, task=task, connection_id="conn-af")
    mock_get_connection.return_value = {"name": "conn"}

    call_command("setconnectionnamesinmeta")

    regions = {
        call.args[1]: call.kwargs["server"].aws_region
        for call in mock_get_connection.call_args_list
    }
    assert regions == {"conn-in": "ap-south-1", "conn-af": "af-south-1"}


@patch("ddpui.management.commands.setdockerinfoindestinations.airbyte_service")
def test_command_setdockerinfoindestinations_uses_org_region(
    mock_airbyte_service, org_af, mock_region_secrets
):
    OrgWarehouse.objects.create(org=org_af, wtype="postgres", airbyte_destination_id="dest-af")
    mock_airbyte_service.get_destination.return_value = {"destinationDefinitionId": "def"}
    mock_airbyte_service.get_destination_definition.return_value = {
        "dockerRepository": "airbyte/destination-postgres",
        "dockerImageTag": "1.0",
    }

    call_command("setdockerinfoindestinations")

    for call in (
        mock_airbyte_service.get_destination.call_args,
        mock_airbyte_service.get_destination_definition.call_args,
    ):
        assert call.kwargs["server"].aws_region == "af-south-1"


@patch("ddpui.management.commands.update_airbyte_server_blocks.prefect_service")
def test_command_update_airbyte_server_blocks(
    mock_prefect_service, org_in, org_af, mock_region_secrets
):
    """filters on block_type (an org's other blocks are not touched) and pushes each org's
    region airbyte host"""
    OrgPrefectBlockv1.objects.create(
        org=org_af, block_type=DBTCORE, block_id="dbt", block_name="org-af-dbt"
    )
    OrgPrefectBlockv1.objects.create(
        org=org_af, block_type=AIRBYTESERVER, block_id="ab", block_name="org-af-airbyte-server"
    )
    OrgPrefectBlockv1.objects.create(
        org=org_in, block_type=AIRBYTESERVER, block_id="ab-in", block_name="org-in-airbyte-server"
    )

    call_command("update_airbyte_server_blocks", "all", "--aws-region", "af-south-1")

    mock_prefect_service.update_airbyte_server_block.assert_called_once()
    block_name, flow_server = mock_prefect_service.update_airbyte_server_block.call_args.args
    assert block_name == "org-af-airbyte-server"
    assert flow_server.server_port == "443"


def test_command_migrate_org_queue_refuses_foreign_pool_for_af_org(org_af, mock_region_secrets):
    with pytest.raises(CommandError, match="not the work pool"):
        call_command(
            "migrate_org_queue",
            "--org-slug",
            org_af.slug,
            "--queue-type",
            "connection_sync_queue",
            "--new-workpool",
            "prod_eks_work_pool",
            "--is-workpool-eks",
            "--dry-run",
        )


def test_command_migrate_org_queue_allows_region_pool_or_force(org_af, mock_region_secrets):
    for extra in ([], ["--force"]):
        pool = "staging_af_eks_work_pool" if not extra else "prod_eks_work_pool"
        call_command(
            "migrate_org_queue",
            "--org-slug",
            org_af.slug,
            "--queue-type",
            "connection_sync_queue",
            "--new-workpool",
            pool,
            "--is-workpool-eks",
            "--dry-run",
            *extra,
            stdout=StringIO(),
        )


@patch("ddpui.celeryworkers.tasks.awsses.send_text_message")
@patch("ddpui.celeryworkers.tasks.get_long_running_flow_runs")
def test_long_running_flow_runs_link_per_org_region(
    mock_get_long_running, mock_send, org_in, org_af, mock_region_secrets
):
    task = Task.objects.create(type=TaskType.AIRBYTE, slug="airbyte-sync-t10", label="sync")
    OrgTask.objects.create(org=org_in, task=task, connection_id="conn-in")
    OrgTask.objects.create(org=org_af, task=task, connection_id="conn-af")
    mock_get_long_running.return_value = [
        {"id": "fr-in", "parameters": {"connection_id": "conn-in"}},
        {"id": "fr-af", "parameters": {"connection_id": "conn-af"}},
    ]

    check_for_long_running_flow_runs()

    body = mock_send.call_args.args[2]
    assert (
        "Connection URL: https://airbyte-in.example.org/workspaces/ws-in/connections/conn-in"
        in body
    )
    # no airbyte ui for the af region: the id only, never a Mumbai url
    assert "Connection ID: conn-af" in body
    assert "connections/conn-af" not in body
