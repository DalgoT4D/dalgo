"""Dalgo API for data regions (where an org's Airbyte runs)"""

from typing import List

from ninja import Router

from ddpui.auth import has_permission
from ddpui.core.regions.region_service import RegionService
from ddpui.schemas.data_region_schema import DataRegionOption
from ddpui.utils.custom_logger import CustomLogger
from ddpui.utils.response_wrapper import ApiResponse, api_response

logger = CustomLogger("ddpui.region_api")

region_router = Router()


@region_router.get("/", response=ApiResponse[List[DataRegionOption]])
@has_permission(["can_create_org"])
def get_data_regions(request):  # pylint: disable=unused-argument
    """data regions a superadmin can pick when creating an org in this deployment"""
    return api_response(
        success=True,
        data=[region.model_dump() for region in RegionService.list_selectable_regions()],
    )
