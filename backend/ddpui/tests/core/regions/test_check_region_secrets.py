import os
from io import StringIO
from unittest.mock import patch

import django
import pytest
from django.core.management import call_command
from ninja.errors import HttpError

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.models.org import Org
from ddpui.tests.conftest import REGION_CONFIG_AF, TEST_SECRET_AF, TEST_SECRET_IN

pytestmark = pytest.mark.django_db


def test_check_region_secrets_ok(org_in, org_af, mock_region_secrets):
    out = StringIO()
    with patch(
        "ddpui.management.commands.check_region_secrets.airbyte_service.abreq",
        return_value={"version": "1"},
    ) as mock_abreq:
        call_command("check_region_secrets", stdout=out)
    output = out.getvalue()
    regions = sorted(call.kwargs["server"].aws_region for call in mock_abreq.call_args_list)
    assert regions == ["af-south-1", "ap-south-1"]
    assert f"OK    {TEST_SECRET_IN}" in output
    assert f"OK    {TEST_SECRET_AF}" in output
    assert "OK    prefect_work_pool of region 'af'" in output
    assert "prefect_work_pool of region 'in'" not in output  # home region: not checked
    assert "token-value" not in output
    assert "staging_af_eks_work_pool" not in output


def test_check_region_secrets_fail(org_in, mock_region_secrets):
    Org.objects.create(
        name="bad",
        slug="bad",
        region_config={**REGION_CONFIG_AF, "airbyte_secret_name": "dalgoAirbyteRegion-test-xx"},
    )
    out = StringIO()
    with pytest.raises(SystemExit):
        call_command("check_region_secrets", "--skip-airbyte", stdout=out)
    assert "FAIL  dalgoAirbyteRegion-test-xx" in out.getvalue()


def test_check_region_secrets_airbyte_unreachable(org_af, mock_region_secrets):
    out = StringIO()
    with patch(
        "ddpui.management.commands.check_region_secrets.airbyte_service.abreq",
        side_effect=HttpError(500, "connection refused"),
    ):
        with pytest.raises(SystemExit):
            call_command("check_region_secrets", stdout=out)
    assert f"FAIL  {TEST_SECRET_AF}: airbyte unreachable" in out.getvalue()


def test_check_region_secrets_missing_work_pool(org_af, test_data_regions, mock_region_secrets):
    test_data_regions.AVAILABLE_DATA_REGIONS["af"]["prefect_work_pool"] = ""
    out = StringIO()
    with pytest.raises(SystemExit):
        call_command("check_region_secrets", "--skip-airbyte", stdout=out)
    output = out.getvalue()
    assert f"OK    {TEST_SECRET_AF}" in output
    assert "FAIL  prefect_work_pool of region 'af' is not set" in output
