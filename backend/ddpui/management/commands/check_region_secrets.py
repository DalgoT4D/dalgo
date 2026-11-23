"""Health check for the per-region Airbyte secrets. Prints OK/FAIL, never secret values."""

from django.conf import settings
from django.core.management.base import BaseCommand
from ninja.errors import HttpError

from ddpui.core.regions import airbyte_credentials
from ddpui.core.regions.exceptions import RegionConfigError
from ddpui.ddpairbyte import airbyte_service
from ddpui.models.org import Org
from ddpui.schemas.data_region_schema import OrgRegionConfig


class Command(BaseCommand):
    """Reads and validates every region secret in use or enabled, and pings each Airbyte"""

    help = (
        "For every distinct Org.region_config.airbyte_secret_name and every enabled data region: "
        "read the secret from Secrets Manager (no env fallback), validate its shape and call the "
        "Airbyte instance_configuration endpoint. For enabled non-home regions also check that a "
        "prefect_work_pool is set in settings. Prints OK/FAIL per check, never values."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-airbyte",
            action="store_true",
            help="Only check the secrets, do not call Airbyte",
        )

    def secrets_to_check(self) -> dict[str, str]:
        """secret name -> aws region, for the secrets used by orgs + those of enabled regions"""
        secrets: dict[str, str] = {}
        for region_config in Org.objects.filter(region_config__isnull=False).values_list(
            "region_config", flat=True
        ):
            try:
                cfg = OrgRegionConfig(**region_config)
            except ValueError:
                self.stdout.write(f"FAIL  invalid region_config {region_config}")
                continue
            secrets[cfg.airbyte_secret_name] = cfg.aws_region
        for code in settings.ENABLED_DATA_REGIONS:
            spec = settings.AVAILABLE_DATA_REGIONS.get(code)
            if spec is None:
                self.stdout.write(f"FAIL  enabled region '{code}' is not in AVAILABLE_DATA_REGIONS")
                continue
            secrets[spec["airbyte_secret_name"]] = spec["aws_region"]
        return secrets

    def check_secret(self, secret_name: str, aws_region: str, skip_airbyte: bool) -> bool:
        """True if the secret is readable and well-formed (and its Airbyte answers)"""
        try:
            region_secret = airbyte_credentials.read_region_secret_uncached(secret_name)
        except RegionConfigError as err:
            self.stdout.write(f"FAIL  {secret_name}: {err.message}")
            return False
        if not skip_airbyte:
            server = airbyte_credentials.build_server_config(secret_name, aws_region, region_secret)
            try:
                airbyte_service.abreq(
                    "instance_configuration", method="GET", timeout=15, server=server
                )
            except HttpError as err:
                self.stdout.write(
                    f"FAIL  {secret_name}: airbyte unreachable (status {err.status_code})"
                )
                return False
        self.stdout.write(f"OK    {secret_name}")
        return True

    def check_work_pools(self) -> list[bool]:
        """Every enabled non-home region needs its own prefect_work_pool in settings"""
        results = []
        for code in settings.ENABLED_DATA_REGIONS:
            spec = settings.AVAILABLE_DATA_REGIONS.get(code)
            if spec is None or code == settings.HOME_DATA_REGION:
                continue  # unknown regions are reported by secrets_to_check
            if spec.get("prefect_work_pool"):
                self.stdout.write(f"OK    prefect_work_pool of region '{code}'")
                results.append(True)
            else:
                self.stdout.write(f"FAIL  prefect_work_pool of region '{code}' is not set")
                results.append(False)
        return results

    def handle(self, *args, **options):
        results = [
            self.check_secret(name, aws_region, options["skip_airbyte"])
            for name, aws_region in sorted(self.secrets_to_check().items())
        ]
        results += self.check_work_pools()
        if not all(results):
            raise SystemExit(1)
