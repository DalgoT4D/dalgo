import os
from unittest.mock import Mock

import django
import pytest
from ninja.errors import HttpError

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.api.region_api import get_data_regions

pytestmark = pytest.mark.django_db


def _request(permissions: list[str]):
    request = Mock()
    request.orguser = Mock()
    request.permissions = permissions
    return request


def test_get_data_regions_lists_only_enabled(test_data_regions):
    test_data_regions.ENABLED_DATA_REGIONS = ["in"]
    response = get_data_regions(_request(["can_create_org"]))
    assert response["success"] is True
    assert response["data"] == [
        {"code": "in", "label": "India (Mumbai)", "aws_region": "ap-south-1"}
    ]

    test_data_regions.ENABLED_DATA_REGIONS = ["in", "af"]
    response = get_data_regions(_request(["can_create_org"]))
    assert [region["code"] for region in response["data"]] == ["in", "af"]


def test_get_data_regions_never_exposes_secret_names(test_data_regions):
    response = get_data_regions(_request(["can_create_org"]))
    assert "dalgoAirbyteRegion" not in str(response)


def test_get_data_regions_requires_can_create_org(test_data_regions):
    with pytest.raises(HttpError) as excinfo:
        get_data_regions(_request(["can_view_dashboards"]))
    assert str(excinfo.value) == "unauthorized"
