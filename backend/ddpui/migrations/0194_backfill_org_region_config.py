# Data migration for multi-region Airbyte (T1): every existing org is in the home region

from django.conf import settings
from django.db import migrations

ALLOWED_DATA_REGION_ENVS = ("staging", "prod")


def home_region_config() -> dict:
    """The region_config of a home-region (Mumbai) org"""
    home = settings.AVAILABLE_DATA_REGIONS[settings.HOME_DATA_REGION]
    return {
        "aws_region": home["aws_region"],
        "country": "IN",
        "airbyte_secret_name": home["airbyte_secret_name"],
    }


def backfill(apps, schema_editor):
    """Set the home region_config on every org that has none. Idempotent."""
    Org = apps.get_model("ddpui", "Org")
    orgs_without_region = Org.objects.filter(region_config__isnull=True)
    if not orgs_without_region.exists():
        return
    if settings.DATA_REGION_ENV not in ALLOWED_DATA_REGION_ENVS:
        raise RuntimeError(
            f"DATA_REGION_ENV must be one of {ALLOWED_DATA_REGION_ENVS} before backfilling "
            f"Org.region_config, got '{settings.DATA_REGION_ENV}'"
        )
    orgs_without_region.update(region_config=home_region_config())


class Migration(migrations.Migration):
    dependencies = [
        ("ddpui", "0193_org_region_config"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
