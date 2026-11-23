from typing import Optional
from datetime import datetime
from pydantic import HttpUrl

from ninja import Schema


class OrgSchema(Schema):
    """Docstring"""

    name: str
    slug: Optional[str] = None
    airbyte_workspace_id: Optional[str] = None
    viz_url: Optional[HttpUrl] = None
    viz_login_type: Optional[str] = None
    tnc_accepted: Optional[bool] = None
    is_demo: bool = False
    logo_url: Optional[str] = None
    logo_filename: Optional[str] = None
    created_at: Optional[datetime] = None
    data_region: Optional[str] = None  # region code, e.g. "in", "af"
    country: Optional[str] = None  # free text, e.g. "India"


class CreateOrgSchema(Schema):
    """payload for org creation"""

    name: str
    slug: Optional[str] = None
    airbyte_workspace_id: Optional[str] = None
    viz_url: Optional[HttpUrl] = None
    viz_login_type: Optional[str] = None
    tnc_accepted: Optional[bool] = None
    is_demo: bool = False
    base_plan: str
    can_upgrade_plan: bool
    subscription_duration: str
    superset_included: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    website: Optional[HttpUrl] = None
    # where the org's Airbyte runs; cannot be changed later. Defaults keep old clients working.
    data_region: str = "in"
    country: Optional[str] = None  # required when data_region is not the home region


class CreateFreeTrialOrgSchema(CreateOrgSchema):
    """payload for org creation specifically for free trial account"""

    email: str
    superset_ec2_machine_id: str
    superset_port: int


class OrgLogoResponse(Schema):
    """Response schema for org logo"""

    logo_url: Optional[str] = None
    logo_filename: Optional[str] = None
    updated_at: datetime

    @classmethod
    def from_model(cls, org) -> "OrgLogoResponse":
        return cls(
            logo_url=org.logo_url,
            logo_filename=org.logo_filename,
            updated_at=org.updated_at,
        )


class OrgLogoUrlPayload(Schema):
    """Payload for uploading a logo via public image URL"""

    image_url: str
