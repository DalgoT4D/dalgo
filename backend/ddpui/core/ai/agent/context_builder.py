"""Builds the RunContext for an agent turn.

This is the ONLY place in the agent that reads the ORM or resolves warehouse
credentials. Transports call build_run_context() (sync, so wrap with
database_sync_to_async in async consumers), then pass the context into the run —
tools never touch the database or trust an LLM-supplied org identifier.
"""

import re

from ddpui.core.ai.agent.run_context import RunContext
from ddpui.models.chat_with_data import ChatWithDataOrgConfig
from ddpui.models.org import OrgWarehouse
from ddpui.models.org_user import OrgUser
from ddpui.utils.warehouse.client.warehouse_factory import WarehouseFactory

# Never offered to the agent, regardless of what the warehouse contains
SYSTEM_SCHEMAS = {
    "information_schema",
    "airbyte_internal",
}
# ...and whole families by prefix: pg_* covers pg_catalog/pg_toast/pg_temp_N
# (session temp schemas appear and vanish per connection), _airbyte* covers
# Airbyte's internal and staging scratch schemas.
SYSTEM_SCHEMA_PREFIXES = ("pg_", "_airbyte")

# BigQuery locations are letters, digits and hyphens (US, EU, asia-south1); the
# value is interpolated into SQL, so anything else is refused
_BQ_LOCATION = re.compile(r"[A-Za-z0-9-]+")

DEFAULT_MAX_RESULT_ROWS = 100
DEFAULT_QUERY_TIMEOUT_S = 30


class ChatWithDataNotReady(Exception):
    """Raised when the org has no warehouse to chat with."""


def derive_allowed_schemas(warehouse, dialect: str, bq_location: str | None = None) -> list[str]:
    """Default schema allowlist: every non-system schema in the warehouse.

    Deliberately NOT restricted to the org's dbt output schema (removed
    2026-09-10): real questions often live in staging/intermediate tables the
    dbt schema misses. The agent's prompt steers it to ask the user rather than
    comb every schema; an admin can still pin the list via
    ChatWithDataOrgConfig.allowed_schemas.

    BigQuery's INFORMATION_SCHEMA.SCHEMATA answers for a single region, so it is
    qualified with the warehouse's dataset location — unqualified, an asia-south1
    warehouse lists none of its own datasets. A query job also runs in one
    location, so datasets elsewhere could not be queried anyway."""
    if dialect == "bigquery":
        if bq_location:
            if not _BQ_LOCATION.fullmatch(bq_location):
                raise ValueError(f"unexpected BigQuery location {bq_location!r}")
            sql = (
                f"SELECT schema_name FROM `region-{bq_location.lower()}`"
                ".INFORMATION_SCHEMA.SCHEMATA"
            )
        else:
            sql = "SELECT schema_name FROM INFORMATION_SCHEMA.SCHEMATA"
    else:
        sql = "SELECT schema_name FROM information_schema.schemata"
    existing = {
        name
        for row in warehouse.execute(sql)
        if (name := row["schema_name"]) not in SYSTEM_SCHEMAS
        and not name.startswith(SYSTEM_SCHEMA_PREFIXES)
    }
    return sorted(existing)


def build_run_context(orguser: OrgUser) -> RunContext:
    """Resolve org warehouse + allowlist + limits into a RunContext. Sync (ORM +
    Secrets Manager); call via database_sync_to_async from async code."""
    org = orguser.org
    org_warehouse = OrgWarehouse.objects.filter(org=org).first()
    if org_warehouse is None:
        raise ChatWithDataNotReady("This organization has no warehouse set up yet")

    warehouse = WarehouseFactory.get_warehouse_client(org_warehouse)
    dialect = org_warehouse.wtype

    # per-org knobs + memory; every org works with no config row (all defaults)
    config = ChatWithDataOrgConfig.objects.filter(org=org).first()

    if config and config.allowed_schemas:
        allowed_schemas = config.allowed_schemas
    else:
        allowed_schemas = derive_allowed_schemas(warehouse, dialect, org_warehouse.bq_location)

    return RunContext(
        org_id=org.id,
        org_slug=org.slug,
        dialect=dialect,
        allowed_schemas=allowed_schemas,
        max_result_rows=config.max_result_rows if config else DEFAULT_MAX_RESULT_ROWS,
        query_timeout_s=config.query_timeout_s if config else DEFAULT_QUERY_TIMEOUT_S,
        warehouse=warehouse,
        orguser_id=orguser.id,
        org_memory=config.memory_text if config else "",
    )
