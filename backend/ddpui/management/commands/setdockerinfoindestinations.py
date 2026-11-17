from django.core.management.base import BaseCommand

from ddpui.models.org import OrgWarehouse
from ddpui.core.regions.region_service import RegionService
from ddpui.ddpairbyte import airbyte_service


class Command(BaseCommand):
    """Docstring"""

    help = "Updates the airbyte_docker_repository and airbyte_docker_image_tag for all warehouses in the system."

    def handle(self, *args, **options):
        """Docstring"""
        for warehouse in OrgWarehouse.objects.all():
            server = RegionService.airbyte_server_for_org(warehouse.org)
            try:
                destination = airbyte_service.get_destination(
                    warehouse.org.airbyte_workspace_id,
                    warehouse.airbyte_destination_id,
                    server=server,
                )
            except Exception:
                continue
            destination_def_id = destination["destinationDefinitionId"]
            destination_definition = airbyte_service.get_destination_definition(
                warehouse.org.airbyte_workspace_id, destination_def_id, server=server
            )
            warehouse.airbyte_docker_repository = destination_definition["dockerRepository"]
            warehouse.airbyte_docker_image_tag = destination_definition["dockerImageTag"]
            warehouse.save()
