from django.core.management.base import BaseCommand
from ddpui.models.org import Org, OrgPrefectBlockv1
from ddpui.ddpprefect import prefect_service, AIRBYTESERVER
from ddpui.core.regions.region_service import RegionService


class Command(BaseCommand):
    """Re-point the orgs' airbyte server blocks in prefect at their region's flow-side host"""

    help = (
        "Update airbyte server blocks in prefect with the flow-side airbyte host of each org's "
        "data region (from the region secret). Use after a region's airbyte host changes."
    )

    def add_arguments(self, parser):
        """adds command line arguments"""
        parser.add_argument("org", type=str, help="Org slug, use 'all' to update for all orgs")
        parser.add_argument(
            "--aws-region",
            type=str,
            default=None,
            help="Only orgs whose region_config.aws_region is this, e.g. af-south-1",
        )

    def handle(self, *args, **options):
        orgs = Org.objects.all()
        if options["org"] != "all":
            orgs = orgs.filter(slug=options["org"])
        if options["aws_region"]:
            orgs = [
                org
                for org in orgs
                if RegionService.get_region_config(org).aws_region == options["aws_region"]
            ]

        print(f"Updating airbyte server blocks in prefect for {len(orgs)} orgs")

        for org in orgs:
            server_block = OrgPrefectBlockv1.objects.filter(
                org=org, block_type=AIRBYTESERVER
            ).first()

            if not server_block:
                print(f"Org {org.slug} does not have a server block")
                continue

            # update host and port
            try:
                prefect_service.update_airbyte_server_block(
                    server_block.block_name, RegionService.airbyte_flow_server_for_org(org)
                )
                print(f"Updated airbyte server block for org {org.slug}")
            except Exception as e:
                print(f"Error updating airbyte server block for org {org.slug}: {e}")
                continue
