import importlib
import os

import django
import pytest
from django.apps import apps
from django.test import override_settings
from pydantic import ValidationError

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.models.org import Org
from ddpui.schemas.data_region_schema import OrgRegionConfig

pytestmark = pytest.mark.django_db

backfill_migration = importlib.import_module("ddpui.migrations.0194_backfill_org_region_config")

AF_CONFIG = {
    "aws_region": "af-south-1",
    "country": "ZA",
    "airbyte_secret_name": "dalgoAirbyteRegion-staging-af",
}


@override_settings(DATA_REGION_ENV="staging")
def test_backfill_fills_null_and_keeps_existing():
    """NULL region_config gets the home config; an already-set one is untouched"""
    # the settings dict is built at import time, so patch it consistently with the env
    with override_settings(
        AVAILABLE_DATA_REGIONS={
            "in": {
                "label": "India (Mumbai)",
                "aws_region": "ap-south-1",
                "airbyte_secret_name": "dalgoAirbyteRegion-staging-in",
            }
        }
    ):
        org_null_1 = Org.objects.create(name="o1", slug="o1")
        org_null_2 = Org.objects.create(name="o2", slug="o2")
        org_af = Org.objects.create(name="o3", slug="o3", region_config=AF_CONFIG)
        queue_config_before = Org.objects.get(id=org_null_1.id).queue_config

        backfill_migration.backfill(apps, None)
        # idempotent
        backfill_migration.backfill(apps, None)

    expected = {
        "aws_region": "ap-south-1",
        "country": "IN",
        "airbyte_secret_name": "dalgoAirbyteRegion-staging-in",
    }
    org_null_1.refresh_from_db()
    org_null_2.refresh_from_db()
    org_af.refresh_from_db()
    assert org_null_1.region_config == expected
    assert org_null_2.region_config == expected
    assert org_af.region_config == AF_CONFIG
    assert org_null_1.queue_config == queue_config_before


@override_settings(DATA_REGION_ENV="dev")
def test_backfill_refuses_unknown_env_when_rows_need_it():
    Org.objects.create(name="o1", slug="o1")
    with pytest.raises(RuntimeError, match="DATA_REGION_ENV"):
        backfill_migration.backfill(apps, None)


@override_settings(DATA_REGION_ENV="dev")
def test_backfill_noop_with_nothing_to_fill():
    """A fresh database (e.g. the test db) migrates whatever DATA_REGION_ENV is"""
    Org.objects.create(name="o1", slug="o1", region_config=AF_CONFIG)
    backfill_migration.backfill(apps, None)


def test_org_region_config_valid():
    cfg = OrgRegionConfig(**AF_CONFIG)
    assert cfg.aws_region == "af-south-1"


@pytest.mark.parametrize(
    "override",
    [
        {"aws_region": "south-africa"},
        {"aws_region": "AF-SOUTH-1"},
        {"country": "za"},
        {"country": "ZAF"},
        {"airbyte_secret_name": "warehouseCreds-staging-af"},
        {"airbyte_secret_name": "dalgoAirbyteRegion-staging-africa"},
        {"extra_key": "x"},
    ],
)
def test_org_region_config_rejects_bad_values(override):
    with pytest.raises(ValidationError):
        OrgRegionConfig(**{**AF_CONFIG, **override})
