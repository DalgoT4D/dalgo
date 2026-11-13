# Plan: Row Level Access Control + Members View-Only — v1

**Spec:** [Final Spec: Row Level Access Control for dashboards](https://docs.google.com/document/d/10TCh8IRTnkQDaUC4FHkml_Kov2h1fWANebqtGaXc1iM/edit) — tab "Spec v3 (11 Nov)", dated 12 Nov 2026, Abhishek Nair. Section numbers below ("spec §5") point at that tab.
**Plan status:** Ready for review, 13 Nov 2026.
**Services:** `backend` (major), `webapp` (major). `prefect-proxy` and `ai-llm-service` are not touched.

**Terms used in this plan**

| Term                                      | Meaning                                                                                                                                              |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| RLS (row-level security) / **row access** | Showing each person only the warehouse rows they are allowed to see. "Row access" is the product name.                                               |
| **Access list**                           | The CSV the org uploads: one row per person, one column per scope.                                                                                   |
| **Scope column**                          | A column on the access list (e.g. `district`) whose name matches a column in the data.                                                               |
| **Filtered table**                        | A warehouse table that has at least one scope column. Members see only their rows from it.                                                           |
| **Row scope**                             | What one person may see, worked out from their access-list rows.                                                                                     |
| `AggQueryBuilder`                         | The shared SQLAlchemy query builder in `ddpui/core/datainsights/query_builder.py`. Charts, KPIs, maps, filters and alerts all build queries with it. |
| **Member floor**                          | `OrgPreferences.default_member_level`: the access a Member gets to non-private dashboards, charts, KPIs and reports.                                 |
| HLD / LLD                                 | High-Level Design / Low-Level Design.                                                                                                                |

---

## 1. Overview

### 1.1 Row access

One dashboard, and each person sees only their own rows — down to a single school or dam.

> **Example:** Rahul (an ATECF official, `rahul@mh.gov.in`) opens "Silt progress". His access-list row says district = Solapur, taluka = Pandharpur. Every chart, "view data" table and CSV shows Pandharpur rows only. Priya (an ATECF Admin) opens the same dashboard and sees every district.

Today Dalgo has no row filtering, so the only option is a separate dashboard per audience. ATECF says only its internal team can use Dalgo until this exists (spec §1).

### 1.2 Members view-only

Members can view everything in the org but cannot create or edit anything, in every org (spec §7, decision 6).

> **Why:** Creating or editing a chart lets a Member pick any table, which goes around row access. Members don't use it: since 14 July 2026, 17 active Members created or edited no charts, and one created an empty dashboard (PostHog).

### 1.3 Who needs it

| Org      | Who sees a scoped view                                | Scope columns                  | Users      | When                                     |
| -------- | ----------------------------------------------------- | ------------------------------ | ---------- | ---------------------------------------- |
| ATECF    | Internal and external teams (officials, partner NGOs) | `district`, `taluka`, `dam_id` | ~40        | Testing first week of Dec, then training |
| Bhumi    | Fellows, PMs, city leads                              | `school_id`, `fellow`          | ~30        | Pilot alongside ATECF                    |
| Antarang | Similar request                                       | To confirm                     | To confirm | After ATECF and Bhumi adopt              |

### 1.4 Scope (spec §8)

**In v1**

- CSV upload of the access list, with a template download.
- Review (blocking errors, warnings, info) and preview (as one person, and "everyone at once").
- Rule enforced on every route a Member can reach: charts, KPIs, maps, filter values, "view data", CSV, **reports and alerts**.
- Members view-only, with the ownership migration.
- The two missing access checks (`/charts/{id}/data/`, `/kpis/{id}/data/`), shipped first and on their own.

**Out of v1:** choosing AND/OR between columns; Dalgo guessing scope columns from values; hiding columns; filtering Analysts; Superset (existing Superset setups stay as they are); mapping differently named columns (names must match — differences are fixed in dbt).

**Phase 2:** warehouse table as the source with "Sync now"; groups on the access list; bulk invite by CSV; editing the list inside Dalgo; hand-written rules; AI chat for Members with row access.

### 1.5 Timeline (spec §10)

| #   | Milestone                                                                                           | Target                                                  |
| --- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 1   | Spec final                                                                                          | Thu 12 Nov ✅                                           |
| 2   | Designs final (Row access page, review flow, preview)                                               | Mon 16 Nov                                              |
| 3   | Dev — access-check fixes first; backend starts before designs are final; includes Members view-only | 16 Nov – 2 Dec                                          |
| 4   | Flagged release for pilots: Bhumi, then ATECF. Orgs told about the Member change before it ships    | Thu 3 Dec                                               |
| 5   | Updates from pilot feedback                                                                         | 7 – 18 Dec                                              |
| 6   | General access                                                                                      | Early Jan 2027, after ATECF's training, before Antarang |

**Cut order if late (spec §10):** first the "everyone at once" preview table, then the "did you mean" suggestions. Nothing else is cuttable — reports and alerts are part of the launch gate.

---

## 2. How row access works (product rules)

These are the rules the code must implement. Each one is from spec §2 unless marked.

**The rule:** The access list has one row per person and one column per scope. The first column is `email`; every other column is a scope column.
**Example:** ATECF's list has columns `email, district, taluka, dam_id`.
**Why it matters:** The header row _is_ the configuration. There is no separate "pick columns" setting that can drift from the file.

**The rule:** Scope column names match the data's column names exactly. There is no mapping step.
**Example:** ATECF's data calls it `state_name`; the list says `state`. Consulting adds a `state` column in dbt. Dalgo does not map one name to the other.
**Why it matters:** A mapping layer was cut in v3 (spec §8 "Out").

**The rule:** A cell can hold several values separated by `;`. `*` means every value. A blank cell means none.
**Example:** Priya's `district` cell is `Ahilyanagar; Pune` → she sees both districts. New User's `taluka` cell is blank → they see nothing from tables with a `taluka` column.
**Why it matters:** Blank must mean "nothing", never "everything", so a forgotten cell fails safe.

**The rule:** Within one row, columns AND together. A person's separate rows add up (OR).
**Example:** Sunil has two rows: `Pune, *, *` and `Nashik, Sinnar, *`. He sees all of Pune plus only Sinnar in Nashik.
**Why it matters:** This is the only way to express mixed scopes; there is no AND/OR toggle.

**The rule:** A table is filtered on the scope columns it has. Tables with no scope column show in full.
**Example:** `silt_daily` has `district` and `taluka` → filtered on both. `state_summary` has only `district` → Rahul sees all of Solapur there (a "partial scope", flagged as info in review). `national_totals` has none → everyone sees national totals.
**Why it matters:** No table picking. A new table with a scope column is filtered the moment it appears.

**The rule:** Only Members are filtered. Super-admins, Admins and Analysts see everything.
**Example:** Rahul is promoted to Analyst → he sees all districts on his next request.
**Why it matters:** Admins and Analysts build and check dashboards. External users must stay Members.

**The rule:** A dashboard filter on a scope column is fixed to the person's values. Other filters work as normal and can only narrow.
**Example:** On "Silt progress", Rahul's District filter is locked to Solapur. The Year filter works normally.
**Why it matters:** The filter UI must never offer values the server would refuse anyway.

**The rule:** Logic lives in the data, not the rule. Anything the list can't express is solved in dbt.
**Example:** A Bhumi PM needs to see her Fellows' schools. Bhumi adds her Fellows' emails to her `fellow` cell, or adds a `pm` column in dbt.
**Why it matters:** Dalgo writes the rule itself; nobody writes SQL.

### 2.1 The ATECF example (spec §2) — used in tests

| email              | district          | taluka        | dam_id | Sees                                                           |
| ------------------ | ----------------- | ------------- | ------ | -------------------------------------------------------------- |
| priya@atecf.org    | Ahilyanagar; Pune | \*            | \*     | All of Ahilyanagar and Pune                                    |
| rahul@mh.gov.in    | Solapur           | Pandharpur    | \*     | Pandharpur only                                                |
| anita@atecf.org    | Ahilyanagar; Beed | Parner; Ashti | \*     | Parner and Ashti only                                          |
| sunil@atecf.org    | Pune              | \*            | \*     | All of Pune …                                                  |
| sunil@atecf.org    | Nashik            | Sinnar        | \*     | … plus only Sinnar in Nashik                                   |
| sunita@partner.org | Beed              | Ashti         | D-104  | One dam                                                        |
| new.user@atecf.org | Solapur           | _(blank)_     | \*     | Nothing from tables with a `taluka` column (flagged on upload) |
| lead@atecf.org     | \*                | \*            | \*     | Everything                                                     |

At Bhumi, a Fellow's row sets `fellow` to her own email and `school_id` to her schools; a PM's row lists her Fellows.

> **Note on `email`:** `email` is the key column of the list, so it can never be a scope column. If a Bhumi table needs scoping by the Fellow's email, the data column must be called `fellow` (as in the spec), not `email`.

---

## 3. Blast radius

Every code path that reads warehouse rows for a Member is affected. Admins and Analysts are unaffected except for the Row access page, preview, and the chart-builder note.

| Surface                       | Where                                                                                                                                                       | Change                                                                                                                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Query builder**             | `ddpui/core/datainsights/query_builder.py` → `AggQueryBuilder.fetch_from()`                                                                                 | Adds the row-access condition for the current row scope. One choke point for charts, pivots, maps, KPIs, filter values, report data and alerts.                          |
| **Request auth**              | `ddpui/auth.py` → `CustomJwtAuthMiddleware.authenticate()`                                                                                                  | Sets the row scope for the request (lazily resolved). Reads the preview header for Admins/Analysts.                                                                      |
| **Scope reset**               | New Django middleware in `ddpui/settings.py` `MIDDLEWARE`                                                                                                   | Clears the row scope at the start and end of every request so nothing leaks between requests on one thread.                                                              |
| **Chart routes**              | `ddpui/api/charts_api.py`: `chart-data`, `chart-data-preview`, `chart-data-preview/total-rows`, `map-data`, `map-data-overlay`, `download-csv`, `{id}/data` | Filtered automatically via the builder. Payload routes get a **table guard** for Members (§5.9). `{id}/data` gets its missing access check (§5.10).                      |
| **KPI routes**                | `ddpui/api/kpi_api.py` → `{kpi_id}/data/`                                                                                                                   | Filtered automatically. Gets its missing access check.                                                                                                                   |
| **Filter values**             | `ddpui/api/filter_api.py` → `/preview/` → `dashboard_service.get_value_filter_options_with_fallback()`                                                      | Filtered automatically (a Member only sees their own values in the dropdown). Table guard for Members.                                                                   |
| **Raw warehouse routes**      | `ddpui/api/warehouse_api.py` (`table_data`, `column-values`, `download`, `table_count`, `insights`, `ask`), `filter_api` schema/table/column lists          | **Blocked for Members** by removing `can_view_warehouse_data` and `can_view_warehouses` from the Member role. Not filtered (spec §7).                                    |
| **Reports**                   | `ddpui/api/report_api.py` data routes; `ddpui/core/reports/pdf_export_service.py`; report email task                                                        | Data routes filtered automatically (snapshots freeze config, not data). **PDF export renders through the public share route**, so it needs a signed scope token (§5.11). |
| **Alerts**                    | `ddpui/celeryworkers/alert_tasks.py` → `evaluate_alert()`; `ddpui/core/alerts/*`                                                                            | Evaluate once per distinct recipient scope; send each recipient only their result (§5.12).                                                                               |
| **Public routes**             | `ddpui/api/public_api.py`                                                                                                                                   | No row scope → unfiltered, by decision 1. Sharing modal warns first (§5.14).                                                                                             |
| **Access control**            | `ddpui/core/access/access_control.py`                                                                                                                       | Members capped at View everywhere (§6.2).                                                                                                                                |
| **Sharing**                   | `ddpui/api/access_api.py`, `ddpui/core/access/resource_share.py`                                                                                            | Edit grants to Members rejected; Members can't change sharing (follows from the cap).                                                                                    |
| **Roles**                     | `seed/003_role_permissions.json` + data migration                                                                                                           | Member loses create/edit/delete and raw-warehouse permissions (§6.1).                                                                                                    |
| **Member floor**              | `ddpui/models/org_preferences.py`, `webapp/components/settings/access/RolesTab.tsx`                                                                         | Fixed at View; not editable (§6.3).                                                                                                                                      |
| **Row access settings (new)** | `ddpui/api/rls_api.py`, `ddpui/core/rls/*`, `ddpui/models/rls.py`; `webapp/components/settings/access/RowAccessTab.tsx`                                     | New page: template, upload, review, preview, save.                                                                                                                       |
| **Webapp dashboards**         | Dashboard view, filters, chart builder, share modal, nav                                                                                                    | Preview mode banner; locked scope filters; "Members will see this in full" note; hide create/edit for Members.                                                           |
| **Superset**                  | `superset_service.py`                                                                                                                                       | No change (out of scope).                                                                                                                                                |
| **AI chat**                   | `chat-with-data`                                                                                                                                            | No change — Members don't have it, and it stays that way until it applies row access (phase 2).                                                                          |

---

## 4. High-Level Design

### 4.1 Where row access sits

```
request ─► JWT auth (CustomJwtAuthMiddleware) ── sets row scope for this request (lazy)
              │
              ▼
          @has_permission  ── role permissions (Members: view-only)
              │
              ▼
          @has_access / access_control  ── can this person open this dashboard/chart?
              │                              (Members capped at View)
              ▼
          service code ─► AggQueryBuilder.fetch_from(schema, table)
                                  │
                                  ▼
                       row_access.condition_for(schema, table)
                         • no scope / Admin / Analyst  → no condition
                         • table not filtered          → no condition
                         • otherwise                   → (row1) OR (row2) …  or FALSE
                                  │
                                  ▼
                           warehouse returns only the person's rows
```

Row access is the last layer. If someone can't open a dashboard, row access never runs.

### 4.2 Design decisions

**D1 — Apply the condition inside `AggQueryBuilder.fetch_from()`, using a per-request row scope.**
**Example:** `build_chart_query()` paginates by building an inner query with `LIMIT` and wrapping it ([charts_service.py:516](../../../../../backend/ddpui/core/charts/charts_service.py)). Because the condition is added in `fetch_from()`, it lands on the **inner** query, before `LIMIT`. Page 2 of Rahul's "view data" is page 2 of Pandharpur rows, and `total-rows` counts Pandharpur rows.
**Why it matters:** There are 32 `fetch_from()` calls across charts, pivots, maps, KPIs, filters, metrics and alerts. Passing `orguser` through every service signature is a large diff and one missed call is a leak. One hook covers all of them, including future ones.

The row scope lives in a `ContextVar` (Python's per-request/per-task variable). It is set by auth for HTTP requests and by an explicit `with row_scope.use(...)` block in Celery tasks and the PDF render.

**D2 — Fail closed everywhere.**

| Situation                                                                          | Result for a Member with values (not `*`)                         |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Table not seen before (created after the last save)                                | Look up its columns live. If it has a scope column, filter it.    |
| A scope column filtered at the last save is now missing                            | No rows from that table; Admins emailed once (spec §4 journey 6). |
| Column lookup fails (warehouse error)                                              | No rows from that table.                                          |
| Person not on the list                                                             | No rows from filtered tables.                                     |
| Value can't be converted to the column's type (e.g. `D-104` for an integer column) | That value matches nothing.                                       |

**Why it matters:** The spec says row access "never falls back to showing more". Treating any of these cases as "no filter" would show a Member every row.

**D3 — Upload creates a draft; review and preview run on the draft; Save commits it.**
**Example:** Consulting uploads ATECF's CSV. Dalgo stores it as a draft and shows the review. They preview Rahul and Sunita against the draft. Only when they press Save does the live list change.
**Why it matters:** Spec §5 says blocking errors stop the save, and spec §6 says a first setup can't be saved until it has been previewed. Writing rows on upload would make an unreviewed list live immediately.

**D4 — Clean values on upload, store the data's exact spelling.**
**Example:** The CSV says `pune ` (lowercase, trailing space). The data has `Pune`. Dalgo stores `Pune`. At query time the comparison is a plain `district IN ('Pune')`, which can use an index.
**Why it matters:** Spec §5 says "case and extra spaces are cleaned automatically, not flagged". Doing it once at upload keeps queries fast and exact.

**D5 — One grouped query per filtered table powers both review and preview.**
**Example:** For `silt_daily`, Dalgo runs `SELECT district, taluka, COUNT(*) FROM silt_daily GROUP BY district, taluka` once. From that it gets: every real value (for "value not found" and "did you mean"), values no one is assigned (e.g. new district Jalna), and row counts per person for the "everyone at once" table.
**Why it matters:** 40 people × 18 tables would be 720 count queries. This is 18.

**D6 — Members view-only is enforced in `access_control`, not by deleting shares.**
**Example:** Anjali (Member) created "Field visits" in August and has an Edit share on "Monthly review". After release, `get_user_access()` returns View for both. Her Edit share becomes View; she does not lose access to the private "Monthly review".
**Why it matters:** The creator rule and group shares can both grant Edit today. A single cap covers every path. Deleting Edit shares instead would remove Members' only access to private dashboards shared with them.

**D7 — No Redis cache for access-list rows.**
**Example:** Rahul's rows are read with one indexed query on `(org, email)` — about a millisecond — once per request, only when a query touches a filtered table.
**Why it matters:** Spec §3: changes "apply at once". A cache would have to be cleared for everyone on both the old and the new list on every save; if it missed someone removed from the list, they would keep their old scope until the cache expired.

---

## 5. Low-Level Design — row access (backend)

### 5.1 Models

File: `ddpui/models/rls.py` (new). Two models, one migration. Both have an `org` FK (foreign key), so every org's setup and list live in the same tables, kept apart by `org`.

```python
class OrgRLSConfig(models.Model):
    """The org's row-access setup, its pending upload and any broken scope columns."""
    org = models.OneToOneField(Org, on_delete=models.CASCADE, related_name="rls_config")

    # Saved setup
    scope_columns = models.JSONField(default=list)        # ["district", "taluka", "dam_id"]
    # {"prod.silt_daily": ["district", "taluka"], ...} — filtered tables at the last save
    filtered_tables = models.JSONField(default=dict)
    first_saved_at = models.DateTimeField(null=True)      # null = first setup not done yet
    saved_by = models.ForeignKey(OrgUser, null=True, on_delete=models.SET_NULL, related_name="+")

    # Upload waiting for review, preview and save; null = no draft
    # {"scope_columns": [...], "rows": [...], "review": {...},
    #  "has_blocking_errors": false, "previewed": false, "uploaded_by": 12, "uploaded_at": "..."}
    draft = models.JSONField(null=True)

    # Scope columns that vanished from a filtered table
    # {"prod.silt_daily": {"columns": ["district"], "emailed_at": "2026-12-08T09:12:00Z"}}
    missing_columns = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)


class OrgAccessListRow(models.Model):
    """One saved access-list row. Several rows per email add up."""
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="access_list_rows")
    email = models.EmailField()          # lowercased; not an FK — people can be listed before they're invited
    # "*" = every value, [] = none, ["Pune", "Nashik"] = those values (data's spelling)
    scope_values = models.JSONField()    # {"district": ["Solapur"], "taluka": ["Pandharpur"], "dam_id": "*"}
    position = models.PositiveIntegerField()   # row order in the uploaded file, for the next download

    class Meta:
        indexes = [models.Index(fields=["org", "email"])]
```

| Model              | Holds                                                                               | Rows per org                    |
| ------------------ | ----------------------------------------------------------------------------------- | ------------------------------- |
| `OrgRLSConfig`     | Saved setup, the pending upload (`draft`), broken scope columns (`missing_columns`) | 1 (created on the first upload) |
| `OrgAccessListRow` | The saved access list, one CSV row each                                             | One per CSV row (~40 for ATECF) |

**Why the access list has its own table:** it is read on every Member query, so it needs the `(org, email)` index. It also grows with the org, while everything else is one small record.

#### Rules for writing `OrgRLSConfig`

`OrgRLSConfig` holds three things that change at different times: Save changes the setup, upload changes `draft`, and a Member's query can add to `missing_columns`. Because they share one database row, two writes at the same moment could overwrite each other. These rules prevent that.

**Rule 1 — every write saves only the fields it changed.**
**Example:** At 10:00:00 consulting presses Save, and Dalgo loads the row with `missing_columns = {}`. At 10:00:01 Rahul's query finds `district` gone from `silt_daily` and records it. At 10:00:02 Save writes back. If Save wrote the **whole** row, it would put back `missing_columns = {}`: the warning would vanish from the page and Admins would be emailed again on the next query.
**How:** Save, upload and discard each lock the row (`select_for_update()` inside `transaction.atomic()`) and write with `save(update_fields=[...])`, listing only their own fields plus `updated_at`.

**Rule 2 — "email only once" is checked while holding the row lock.**
**Example:** Rahul and Sunita load dashboards at the same moment and both see `district` missing from `silt_daily`. Without a lock, both read an empty `missing_columns` and two emails go out. With the lock, Rahul's request adds the entry and queues the email; Sunita's request waits, then sees the entry and does nothing.
**How:** `rls_service.record_missing_columns(org, table_key, columns)`:

```python
def record_missing_columns(org, table_key, columns):
    """Add a missing-column entry and queue one Admin email; no-op if already recorded."""
    with transaction.atomic():
        config = OrgRLSConfig.objects.select_for_update().get(org=org)
        if table_key in config.missing_columns:
            return
        config.missing_columns[table_key] = {"columns": columns, "emailed_at": timezone.now().isoformat()}
        config.save(update_fields=["missing_columns", "updated_at"])
    transaction.on_commit(lambda: send_missing_column_email.delay(org.id, table_key))
```

The lock is taken only the first time a problem is found. Afterwards, queries read `missing_columns` from the scope they already loaded, see the entry and skip, so dashboards don't slow down.

**Rule 3 — Member requests don't load the draft.**
Building a row scope reads the config with `.defer("draft")`. The draft (rows + review) is only needed by the Row access page and preview. Forgetting this changes nothing a person sees; it only makes every request slower.

**A same-named column that means something else is fixed in dbt.**
**Example:** `prod.applications` has a `state` column holding application status ("approved", "pending"). Dalgo filters it like any other `state` column, so Members see no rows from it. Review check 7 flags it; consulting renames the column in dbt (`application_status`) and the table stops being filtered.
**Why it matters:** A wrong match only hides rows, never shows extra ones, and fixing names in dbt is the spec's rule for every naming problem (spec §8: "Names must match; differences are fixed in dbt").

### 5.2 Row scope

File: `ddpui/core/rls/row_scope.py` (new).

```python
@dataclass(frozen=True)
class RowScope:
    org_id: int
    unrestricted: bool                       # Admin / Analyst / super-admin
    scope_columns: tuple[str, ...]
    rows: tuple[dict, ...]                   # the person's rows; empty = not on the list
    filtered_tables: dict[str, list[str]]    # snapshot from OrgRLSConfig
    reported_missing: frozenset[str]         # tables already in OrgRLSConfig.missing_columns

_current: ContextVar[Optional["LazyScope"]] = ContextVar("row_scope", default=None)
```

- `set_for_request(orguser, preview_email, use_draft)` — called from `CustomJwtAuthMiddleware.authenticate()` right after `request.orguser` is set. Stores a `LazyScope`; nothing is read from the database until a query touches the warehouse.
- `resolve_for_orguser(orguser)` — unrestricted if role is super-admin, admin or analyst, or the org has no saved row access (`first_saved_at` is null). Otherwise reads `OrgRLSConfig` with `.defer("draft")` and loads the Member's rows by lowercased email.
- `resolve_for_email(org, email, use_draft)` — used by preview and alerts. Reads rows from `OrgRLSConfig.draft["rows"]` (preview of an unsaved upload) or from `OrgAccessListRow`. Treats the person as a Member.
- `use(scope)` — a context manager for Celery tasks and the PDF render.
- `RowScopeResetMiddleware` — resets `_current` before and after each request.

**When there is no row scope at all** (public routes, Admin-only background jobs), the builder adds no condition. That is correct for public links (decision 1) and for jobs that run as the org. Every Member-reachable path is covered by the launch-gate tests in §8, including a test that fails if a new Member-reachable route appears without being reviewed.

**Feature flag:** `ROW_ACCESS` in `ddpui/utils/feature_flags.py`. If the flag is off for an org, `resolve_for_orguser` returns unrestricted and the settings page is hidden. That is how the 3 Dec release reaches Bhumi and ATECF only.

### 5.3 Building the condition

File: `ddpui/core/rls/row_filter.py` (new). Called from `AggQueryBuilder.fetch_from()`.

```python
def fetch_from(self, db_table: str, db_schema: str):
    self.select_from = table(db_table, schema=db_schema)
    condition = row_filter.condition_for(db_schema, db_table)
    if condition is not None:
        self.where_clauses.append(condition)
    return self
```

```python
def build_condition(scope: RowScope, table_key: str, live_columns: dict[str, str]):
    """None = no filter; false() = no rows."""
    if scope.unrestricted:
        return None
    present = [c for c in scope.scope_columns if c in live_columns]
    missing = [c for c in scope.filtered_tables.get(table_key, []) if c not in live_columns]
    if not present and not missing:
        return None                                  # table has no scope column → shown in full

    row_clauses = []
    for row in scope.rows:
        if any(row[c] != "*" for c in missing):
            continue                                 # column vanished → this row sees nothing here
        parts, blank = [], False
        for c in present:
            value = row[c]
            if value == "*":
                continue
            if not value:
                blank = True                         # blank cell = none
                break
            parts.append(column(c).in_(coerce(value, live_columns[c])))
        if blank:
            continue
        if not parts:
            return None                              # this row allows everything in this table
        row_clauses.append(and_(*parts))
    return or_(*row_clauses) if row_clauses else false()
```

Worked through for Sunil on `silt_daily (district, taluka)`:

```
row 1: Pune, *, *        → district IN ('Pune')
row 2: Nashik, Sinnar, * → district IN ('Nashik') AND taluka IN ('Sinnar')
WHERE (district IN ('Pune')) OR (district IN ('Nashik') AND taluka IN ('Sinnar'))
```

Rules this code must keep (each has a unit test in §10):

- Values go in through SQLAlchemy `in_()`, never string formatting (spec §7).
- A row with `*` on every column the table has means "no filter" — it must **not** be dropped. Otherwise Sunil's "all of Pune" row would disappear on a table that only has `taluka`.
- `coerce()` converts values to the column's type (integer columns get ints). A value that can't convert is dropped, so it matches nothing.
- When `missing` is not empty and the table isn't in `scope.reported_missing`, `condition_for()` calls `record_missing_columns()` (§5.1 rule 2) so Admins are emailed once.

**How `live_columns` is found:** `ddpui/core/rls/schema_cache.py`.

- One `information_schema.columns` query per schema, cached in Redis for 10 minutes, key `rls_cols:{org_id}:{schema}`. Returns `{table: {column: type}}`.
- If a table isn't in the cached result (created since), fetch that one table's columns with `Warehouse.get_table_columns()` and add it to the cache.
- If the lookup fails, Members get `false()` for that table.
- New warehouse client method: `get_schema_columns(db_schema) -> dict[str, dict[str, str]]` in `warehouse_interface.py`, `postgres.py` and `bigquery.py` (BigQuery uses the dataset's `INFORMATION_SCHEMA.COLUMNS`).

**Executor note:** `charts_service.execute_query()` compiles with `literal_binds=True`, so SQLAlchemy renders bound values into the SQL text using the dialect's own escaping. That is the same path every existing dashboard filter uses. Switching the executor to server-side parameters is a wider change; see open question Q6.

### 5.4 Upload: parse and clean

File: `ddpui/core/rls/access_list_service.py` (new).

1. **Parse** with `csv.DictReader`. Lowercase and trim emails. Trim cell values. Split on `;`, drop empty parts.
   `"Pune; Nashik"` → `["Pune", "Nashik"]`; `"*"` → `"*"`; `""` → `[]`.
2. **Scope columns** = header minus `email`, lowercased and trimmed. Duplicate headers are a blocking error.
3. **Find filtered tables** from the schema cache: every `schema.table` that has at least one scope column.
4. **Fetch real values** (D5): for each filtered table, one grouped count over the scope columns it has. Results are capped at 50,000 groups per table. Above that, Dalgo falls back to `SELECT DISTINCT` per column (also capped), and the "everyone at once" counts for that table show "too many to count". These run on the warehouse in a Celery task with progress, so a slow warehouse doesn't time out the upload request.
5. **Clean values** (D4): match each value case- and space-insensitively against the real values for that column. Store the data's spelling. Unmatched values are kept as typed and flagged "value not found", with the closest match from `difflib.get_close_matches` ("Ahmednagar" → did you mean "Ahilyanagar"?).
6. **Save as draft:** write `OrgRLSConfig.draft` (creating the config row on an org's first upload), replacing any earlier draft, with the review result from §5.5. Lock the row and write only `draft` (§5.1 rule 1).

### 5.5 Review checks

All checks from spec §5. They run on upload only — no daily job. The Row access page shows the latest result.

| #   | Check                                                               | Example                                                                       | Type                                                   | How                                                                                                                                                 |
| --- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | File is malformed: no `email` column, duplicate headers, not a CSV  | `email` column missing                                                        | **Blocking**                                           | Parse step                                                                                                                                          |
| 2   | A scope column exists in no table                                   | `ngo` vs the data's `ngo_name`                                                | **Blocking**                                           | Schema cache                                                                                                                                        |
| 3   | Member has no row, so sees nothing                                  | `new.user@atecf.org`                                                          | Warning                                                | Members (role = member) not on the list                                                                                                             |
| 4   | Email on the list isn't a Dalgo user                                | Typo, or not invited yet                                                      | Warning                                                | Not an `OrgUser` in this org. Shown with an **Invite** button                                                                                       |
| 5   | Value not found in the data, with the closest match                 | "Ahmednagar": did you mean "Ahilyanagar"?                                     | Warning                                                | §5.4 step 5                                                                                                                                         |
| 6   | Blank cell, so sees nothing on tables with that column              | `dam_id` left empty                                                           | Warning                                                | Cell is `[]`                                                                                                                                        |
| 7   | Same-named column whose values never match the list                 | `state` holding application status                                            | Warning: "rename it in dbt if it means something else" | No listed value for that column is found in that table, while it is found in other tables                                                           |
| 8   | Partial scope: scoped to a taluka, but a table only has district    | Sees the whole district on that table                                         | Info                                                   | Person has a non-`*` value on a column the table lacks                                                                                              |
| 9   | `*` on every column                                                 | Confirm `lead@atecf.org` should see everything                                | Info                                                   |                                                                                                                                                     |
| 10  | A value in the data no one is assigned                              | New district Jalna                                                            | Info                                                   | Real values minus all listed values                                                                                                                 |
| 11  | Tables affected                                                     | `silt_daily: district, taluka`. `farmer_list`: not filtered (no scope column) | Info, shown before saving                              | Schema cache                                                                                                                                        |
| 12  | Dashboards Members can open that use unfiltered tables              | Listed by dashboard                                                           | Warning                                                | Dashboards that are not private, or private but shared with a Member or a group containing one, whose charts/KPIs read a table with no scope column |
| 13  | A scope column is missing from a table it filtered at the last save | `district` renamed in `silt_daily`                                            | Warning                                                | `OrgRLSConfig.filtered_tables` vs schema cache                                                                                                      |

Also, from spec §4 journey 5: a saved row whose email is no longer a Dalgo user is shown as "no Dalgo user" (check 4 covers it).

**Repeated emails are allowed** — they are how a person gets two scopes. They are not an error.

**How it's shown** (spec §5, design to mock): one step at a time, counts first, details only where action is needed.

```
1. What changes   — dashboards affected, each: N charts filtered, M shown in full → open for tables + columns
2. Must fix       — blocking errors only; Save stays off until none
3. People         — grouped counts side by side:
                      will see their data | will see nothing | sees everything | not in Dalgo yet
                    only groups needing action start open
4. Worth a look   — collapsed: same-named columns, partial scopes, unassigned values
5. Preview, then save
```

"Will see nothing" collects three reasons: no row (check 3), blank cell (check 6), value not found (check 5).

### 5.6 Preview

Spec §6: pick a person and see any dashboard exactly as they would, including empty charts and fixed filters, without logging in as them. For Admins, Analysts and consulting.

**How it works**

- The webapp's dashboard view takes `?previewAs=rahul@mh.gov.in&draft=1`. In preview mode, every data request carries two headers: `X-Row-Access-Preview: <email>` and `X-Row-Access-Draft: 1`.
- `authenticate()` honours these headers **only** for super-admins, Admins and Analysts in an org with the flag on. For anyone else they are ignored. The scope becomes `resolve_for_email(org, email, use_draft)`.
- `GET /api/rls/preview/dashboards/{id}/?email=` answers "can this person open this dashboard?" using `access_control` for that person's `OrgUser` (role Member assumed if they aren't a user yet). If they can't, the page shows "Rahul can't open this dashboard" instead of charts.
- A banner shows "Previewing as rahul@mh.gov.in · Draft list · Exit preview".
- Starting a preview calls `POST /api/rls/draft/previewed/`, which sets `draft["previewed"] = True` (row locked, only `draft` written — §5.1 rule 1).

**Example:** Before the first save, consulting picks Sunita in preview. On "Silt progress" every chart shows dam D-104 only; the District filter is locked to Beed; a national-totals chart shows national totals.

**Everyone at once** (cut first if late): `GET /api/rls/preview/everyone/` returns one row per person on the list, built from the grouped counts in §5.4 — no extra warehouse queries.

| email              | district   | taluka     | dam_id | silt_daily rows | dams rows | Status                    |
| ------------------ | ---------- | ---------- | ------ | --------------- | --------- | ------------------------- |
| rahul@mh.gov.in    | Solapur    | Pandharpur | \*     | 1,234           | 89        | Has access                |
| new.user@atecf.org | Solapur    | _(blank)_  | \*     | 0               | 12        | No row on `taluka` tables |
| anita@atecf.org    | Ahmednagar | Parner     | \*     | 0               | 0         | Value not found           |

Status values (spec §6): has access, no row, value not found.

### 5.7 Save

`POST /api/rls/draft/save/` in one transaction, holding the `OrgRLSConfig` row lock (`select_for_update()`) from start to finish:

1. Refuse if there is no draft, or `draft["has_blocking_errors"]` is true.
2. Refuse if this is the first setup (`first_saved_at` is null) and `draft["previewed"]` is false.
3. Replace all `OrgAccessListRow` rows for the org with `draft["rows"]`.
4. Set `scope_columns`, `filtered_tables` (snapshot of the current schema), `first_saved_at` if empty, `saved_by`.
5. Remove `missing_columns` entries whose columns are back or are no longer scope columns. A table that breaks again later gets a fresh entry and a fresh email.
6. Set `draft` to null.
7. Write with `save(update_fields=[...])` naming only the fields above plus `updated_at` (§5.1 rule 1). Because the row is locked, a missing column found by a Member query during the save waits and is recorded after it, not lost.

Takes effect on the next request. There is nothing to invalidate (D7).

### 5.8 Template download

`GET /api/rls/template/` (spec §3 step 1)

| Situation                  | Download contains                                                                                                                                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First time (nothing saved) | Header `email` + the scope columns the Admin types in (`?columns=district,taluka,dam_id`, with autocomplete from warehouse column names). One row per current Member, scope cells blank. Admins and Analysts are left out. |
| After a save               | The current saved list in its saved order, then a row for each Member not yet on it, scope cells blank.                                                                                                                    |

Values are written back joined with `; `, and `*` as `*`. There are no reference-value rows; spec v3 doesn't ask for them, and they would break re-upload.

### 5.9 Member route hardening: the table guard

Several chart routes take the table name from the request body (`chart-data`, `chart-data-preview`, `total-rows`, `map-data`, `map-data-overlay`, `download-csv`, filter `/preview/`). Row access filters these automatically, but a Member could still name **any unfiltered table**.

**Example:** `farmer_list` has phone numbers and no scope column. Without a guard, Rahul could POST `{"schema_name": "prod", "table_name": "farmer_list"}` to `/chart-data/` and read it in full, even though no dashboard he can open uses it.

**The rule:** For Members, a payload route accepts only a `(schema, table)` used by a chart, KPI or dashboard filter on a dashboard or report the Member can view. Otherwise it returns 403.
**Where:** `ddpui/core/rls/table_guard.py` → `require_viewable_table(orguser, schema, table)`, called at the top of each payload route. Admins and Analysts skip it.

### 5.10 The two missing access checks (ship first, on their own)

Spec §7: Trust work for Pradeep, not billed. One PR, before the row-access PRs.

| Route                                                                                                    | Today                                                       | Fix                                                                                                                           |
| -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/charts/{chart_id}/data/` ([charts_api.py:994](../../../../../backend/ddpui/api/charts_api.py)) | Loads any chart in the org by ID; no per-chart access check | `@has_access(ResourceType.CHART, AccessLevel.VIEW, ...)`. A chart reached through a dashboard is visible if the dashboard is. |
| `GET /api/kpis/{kpi_id}/data/` ([kpi_api.py:228](../../../../../backend/ddpui/api/kpi_api.py))           | Same                                                        | `@has_access(ResourceType.KPI, AccessLevel.VIEW, ...)`                                                                        |

**Example:** Today Anjali (Member) can read the private "Funding by donor" chart by guessing `/api/charts/412/data/`. After the fix she gets 404.

Tests: Member without access → 404; Member with access → 200; Admin → 200.

### 5.11 Reports

Spec §7: a Member opening a report on filtered tables sees only their rows.

- **Data routes** (`/reports/{id}/charts/{chart_id}/data/`, `/kpis/{kpi_id}/data/`, `/map-data/`, `/table-data/`, `/table-data/total-rows/`): `ReportSnapshot` freezes config but queries data live ([report.py:8](../../../../../backend/ddpui/models/report.py)). These routes go through `AggQueryBuilder`, so they're filtered by the request's row scope with no extra code.
- **PDF export** (`POST /reports/{id}/export/pdf/`) renders `/share/report/{public_share_token}?print=true` in headless Chromium. That page calls **public** routes, which have no row scope, so **a Member's PDF would contain every row**.
  - **Fix:** `pdf_export_service.generate_pdf()` takes the requesting `OrgUser`. It already injects a render secret into the page's requests; it also adds a signed, 5-minute scope token (`django.core.signing`, containing `orguser_id`). Public report data routes that see a valid render secret **and** scope token wrap the query in `row_scope.use(resolve_for_orguser(...))`.
- **Share via email** (`send_report_email_task`) renders the PDF as the sender (`orguser_id` is already passed). Recipients get exactly what the sender sees.
  **Example:** Rahul emails the monthly report to his deputy. The PDF holds Pandharpur rows only.

### 5.12 Alerts

Spec §7: an alert on a filtered table checks its condition and sends its data per recipient, by that person's scope. Engineering to confirm the effort.

`Alert.recipients` is JSON: `{"type": "orguser", "orguser_id": …}` or `{"type": "external", "email": …}` ([alert.py:83](../../../../../backend/ddpui/models/alert.py)). Delivery also has a Slack channel.

**Flow in `evaluate_alert()`** (`ddpui/celeryworkers/alert_tasks.py`):

```
alert's table filtered for this org?
  no  → today's flow, unchanged
  yes → group recipients by scope:
          Admin / Analyst orguser  → "unrestricted"
          Member orguser           → their saved rows
          external email           → saved rows for that email (none → sees nothing)
        for each distinct scope:
          with row_scope.use(scope): compute value
          condition met? → render + deliver to that group only
        Slack (if enabled) → evaluated as unrestricted (see Q3)
        write one AlertLog per scope evaluated
```

**Example:** "Notify when silt removed < 100 tonnes this week." Rahul (Pandharpur, 80 t) gets an alert showing 80 t. Sunita (D-104, 140 t) gets nothing. Priya (Admin, 2,300 t org-wide) gets nothing.

- People with identical rows share one evaluation (fewer warehouse queries).
- An external email not on the list gets nothing from a filtered table — it fails closed.
- `AlertLog` stays one row per evaluation. A new nullable `scope_label` column ("unrestricted", or the recipient emails) tells them apart. `alert_snapshot.recipients` records who that evaluation was for.
- KPI-RAG alerts go through `kpi_service`, which uses `AggQueryBuilder`, so they're covered the same way.
- `AlertService.dry_run()` (the "Test" button) runs as the alert's author: unrestricted, since only Admins and Analysts can create alerts once Members are view-only.

### 5.13 When things are added or change (spec §4 journey 6)

| Event                                                                      | Behaviour                                                                                                                                                                                                                              | Code                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New table with a scope column                                              | Filtered on the next query (live column lookup). Shown on the Row access page as **newly filtered**.                                                                                                                                   | Page compares the schema cache with `OrgRLSConfig.filtered_tables`                                                                                                                                                                           |
| New chart on a table with no scope column, on a dashboard Members can open | The builder (Admin/Analyst) sees a short, non-blocking note: "Members will see this table in full."                                                                                                                                    | `GET /api/rls/table-status/?schema=&table=` → `{filtered, scope_columns}`; shown in the chart builder and when adding a chart to a dashboard                                                                                                 |
| New value in the data (a new dam)                                          | Visible only to people with `*` in that column                                                                                                                                                                                         | Falls out of §5.3                                                                                                                                                                                                                            |
| Scope column renamed or dropped                                            | Members with `*` in that column: unaffected; the other columns keep working. Members with values: no data from that table, shown as "No data for your access, contact your admin". Admins emailed once per table; flagged on the page. | §5.3 `missing` handling. On the first query that sees it, `record_missing_columns()` adds an entry to `OrgRLSConfig.missing_columns` under the row lock and queues one email via Celery (§5.1 rule 2). The Row access page lists the entries |

**Empty-state message.** When a Member's chart returns no rows **because of** row access, the chart shows "No data for your access, contact your admin" rather than a generic empty chart. The data response carries `row_access: "no_rows"` when the condition was `false()`. Where the condition was a real filter that simply matched nothing, the normal empty state shows.

### 5.14 Public links (decision 1)

**The rule:** Warn, then public viewers see all rows. Only Admins and Analysts can make public links.
**Example:** Priya turns on the public link for "Silt progress". The sharing modal shows: "This dashboard uses filtered tables (silt_daily, dams). Anyone with the link will see **all** rows, not just their own." She confirms; the link works unfiltered.
**Code:** `GET /api/access/{rtype}/{id}` (sharing modal data) adds `uses_filtered_tables: [...]`. The frontend shows the warning before the toggle takes effect. Public routes need no change — they have no row scope.

### 5.15 API endpoints

Router: `ddpui/api/rls_api.py`, mounted at `/api/rls/`. New permission `can_manage_row_access` (super-admin, Admin, Analyst). All responses use `api_response(...)`.

| Method | Path                               | What it does                                                                                                                 |
| ------ | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/status/`                         | Saved setup: scope columns, counts, filtered tables (incl. newly filtered), missing columns, latest review, `first_saved_at` |
| GET    | `/template/`                       | CSV download (§5.8)                                                                                                          |
| POST   | `/draft/`                          | Upload CSV (multipart) → starts the review task, returns `task_id`                                                           |
| GET    | `/draft/`                          | Current draft + review result                                                                                                |
| DELETE | `/draft/`                          | Discard draft (sets `draft` to null, row locked)                                                                             |
| POST   | `/draft/previewed/`                | Record that the draft has been previewed (§5.6)                                                                              |
| POST   | `/draft/save/`                     | Commit (§5.7)                                                                                                                |
| GET    | `/preview/people/`                 | People on the draft/saved list, for the "Preview as" picker                                                                  |
| GET    | `/preview/dashboards/{id}/?email=` | Can this person open this dashboard?                                                                                         |
| GET    | `/preview/everyone/`               | "Everyone at once" table                                                                                                     |
| GET    | `/table-status/`                   | Filtered or not, for the chart-builder note                                                                                  |
| GET    | `/me/`                             | For the current Member: `{filtered: bool, scope: {column: values}}` — used to lock dashboard filters                         |

Invites use the existing `POST /api/v1/organizations/users/invite/` one at a time, role Member (bulk invite is phase 2).

---

## 6. Low-Level Design — Members view-only (backend)

Spec §7: Members view everything in the org (charts, dashboards, KPIs, reports) and can't create or edit. Admins can't change this. The rest of the Member role stays as it is.

### 6.1 Role permissions

Remove from Member in `seed/003_role_permissions.json`, plus a data migration that removes the same `RolePermission` rows in existing databases:

| Removed                                                                 | Why                                                                                  |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `can_create_charts`, `can_edit_charts`, `can_delete_charts`             | View-only                                                                            |
| `can_create_dashboards`, `can_edit_dashboards`, `can_delete_dashboards` | View-only (also covers creating reports, which uses `can_create_dashboards`)         |
| `can_create_kpis`, `can_edit_kpis`, `can_delete_kpis`                   | View-only                                                                            |
| `can_view_warehouse_data`, `can_view_warehouses`                        | Raw table views, downloads, column values and Ask stay blocked for Members (spec §7) |

Kept: `can_view_*`, `can_share_dashboards` (needed to open the sharing modal and copy a public link), `can_create_invitation`, `can_view_orgusers`, `can_view_alerts`, `can_view_metrics`, `can_view_flags`, `can_request_llm_analysis_feature`, `public`.

> **Side effect to confirm (Q1):** report comments (`create_comment`, `update_comment`, `delete_comment` in `report_api.py`) use `can_edit_dashboards`. Removing it stops Members commenting on reports. Recommendation: move those three routes to a new `can_comment_reports` permission that Members keep, since commenting isn't editing content.

### 6.2 Cap Members at View

In `ddpui/core/access/access_control.py`, after computing the level in `get_user_access()`, `get_user_access_map()` and `accessible_filter()`:

```python
if _is_member(orguser) and level == AccessLevel.EDIT:
    level = AccessLevel.VIEW
```

This covers the creator rule, user grants, group grants and the floor in one place. Every route guarded by `_require_edit_or_admin` (sharing, general access, transfer ownership) then refuses Members automatically.

### 6.3 Member floor fixed at View

- `OrgPreferences.default_member_level` is forced to `view`. The update endpoint ignores any other value for this field.
- Data migration sets it to `view` for every org.
- `webapp/components/settings/access/RolesTab.tsx`: the Members row becomes read-only: "View (fixed)".

> **Spec gap to raise (Q2):** orgs whose Member floor is **No access** today will suddenly let Members see every non-private dashboard. The spec only says to tell orgs whose floor is _above_ View. Recommendation: tell both groups, and tell No-access orgs to mark sensitive dashboards Private before 3 Dec.

### 6.4 Sharing

| Action                                   | Rule                                                                        | Code                                                                                                 |
| ---------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Edit share to a Member (user principal)  | Blocked with a clear error                                                  | `resource_share.add_grants()` / `update_grant()`: reject `level=edit` when the principal is a Member |
| Edit share to a group with Members in it | Allowed; Members in it get View (cap)                                       | Nothing extra                                                                                        |
| Member opens the sharing modal           | Read-only view; can copy the public link if the dashboard is already public | Frontend; backend already refuses changes via the cap                                                |
| Member makes a public link               | Blocked                                                                     | Cap → `_require_edit_or_admin` fails                                                                 |

### 6.5 Migration of existing content

Management command `uv run python manage.py migrate_member_content [--dry-run] [--org <slug>]`, run once on release day. It's a command, not a Django migration, so it doesn't run in tests or on every environment by accident, and it can be dry-run first.

For each org:

1. Pick the receiving Admin: the org's earliest-joined Admin (logged in the output so support can answer "where did my chart go?").
2. Move `created_by` to that Admin for Member-owned dashboards, charts, KPIs, reports (`ReportSnapshot`) and alerts.
3. Give the previous Member owner a **View** grant on each moved item that is private, so nobody loses sight of their own work.
4. Downgrade existing Edit grants to Members to View. Don't delete them.
5. Print a per-org summary. Orgs with Member-owned content but no Admin are listed for manual handling and skipped.

**Before release:** `--dry-run` produces the list of orgs to email:

- floor above View (Edit), or
- floor No access (see Q2), or
- Members own content.

Spec §10: orgs are told before it ships. The access docs (`docs/`) are updated in the same release.

**Email text (draft):**

> **Subject:** From 3 December, Members in Dalgo will be view-only
>
> From 3 December, Members can view all dashboards, charts, KPIs and reports in your org, but can't create or edit them. Anything a Member owns today will move to {admin_name}. {n_items} items are affected in {org_name}.
>
> If someone needs to keep building, make them an Analyst before 3 December (Settings → Access → People). If a dashboard should not be seen by every Member, mark it Private and share it with the right people.
>
> Why: we're adding row-level access so each person sees only their own rows. Letting Members build charts would let them go around it. Since 14 July, Members have created almost no content.

---

## 7. Frontend (webapp)

### 7.1 Row access page

Location: a fourth tab, **Row access**, on Settings → Access (`components/settings/access/AccessPage.tsx`), next to People, Groups and Roles. Shown only with the `ROW_ACCESS` flag and `can_manage_row_access`. Exact layout follows the designs due 16 Nov.

New components in `webapp/components/settings/access/row-access/`:

| Component                  | Shows                                                                                                                                                    |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RowAccessTab.tsx`         | Status: scope columns, people count, filtered tables (newly filtered marked), missing-column warnings, latest review. Buttons: Download template, Upload |
| `TemplateDialog.tsx`       | First time only: type scope column names (autocomplete from warehouse columns)                                                                           |
| `UploadReview.tsx`         | The 5-step review (§5.5): What changes → Must fix → People → Worth a look → Preview, then save                                                           |
| `PeopleGroups.tsx`         | Grouped counts; "not in Dalgo yet" rows have an **Invite** button                                                                                        |
| `EveryonePreviewTable.tsx` | "Everyone at once" table (cut first if late)                                                                                                             |

Save stays disabled while there are blocking errors, and on first setup until a preview has been opened.

### 7.2 Preview mode

- "Preview as" picker on the Row access page and on any dashboard (Admins/Analysts only).
- Adds `?previewAs=<email>&draft=1` to the dashboard URL. An API client wrapper adds the two headers to every request while those params are present.
- Banner: "Previewing as rahul@mh.gov.in · Draft list · Exit preview".
- If the person can't open the dashboard, show that instead of charts.

### 7.3 Dashboard filters for Members

- On dashboard load, a filtered Member calls `/api/rls/me/`.
- A filter whose column is a scope column:
  - with one value → shown locked ("District: Solapur 🔒")
  - with several → a dropdown of just those values.
- The dropdown values already come back filtered from `/filters/preview/` (§3). The lock is UX only; the server enforces the rule either way.

### 7.4 Other UI

| Where                                             | Change                                                                                                                   |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Chart builder / add chart to dashboard            | Non-blocking note when `table-status` says not filtered and row access is set up: "Members will see this table in full." |
| Chart empty state                                 | "No data for your access, contact your admin" when `row_access: "no_rows"`                                               |
| Sharing modal                                     | Members: read-only, copy public link only. Admins/Analysts: filtered-tables warning before going public                  |
| Nav, list pages, dashboard/chart/KPI/report pages | Hide create/edit/delete for Members (driven by the removed permissions via `lib/rbac.tsx`)                               |
| Roles tab                                         | Member floor shown as "View (fixed)"                                                                                     |

---

## 8. Launch gate

Spec §7: nothing goes live until every route a Member can reach is covered. Each route gets an automated test that logs in as a scoped Member (Rahul, from §2.1) and checks that only Pandharpur rows come back.

| Route                                                                                                                            | Covered by                     | Test asserts                                   |
| -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ---------------------------------------------- |
| `GET /api/charts/{id}/data/`                                                                                                     | Builder + access check (§5.10) | Pandharpur only; 404 for a chart he can't view |
| `POST /api/charts/chart-data/`                                                                                                   | Builder + table guard          | Pandharpur only; 403 on `farmer_list`          |
| `POST /api/charts/chart-data-preview/` ("view data")                                                                             | Builder + table guard          | Page 1 and page 2 both Pandharpur only         |
| `POST /api/charts/chart-data-preview/total-rows/`                                                                                | Builder + table guard          | Count = Pandharpur count                       |
| `POST /api/charts/download-csv/`                                                                                                 | Builder + table guard          | CSV has Pandharpur only                        |
| `POST /api/charts/map-data/`, `/map-data-overlay/`                                                                               | Builder + table guard          | Only Pandharpur regions have values            |
| `GET /api/kpis/{id}/data/`                                                                                                       | Builder + access check         | KPI value = Pandharpur value                   |
| `GET /api/filters/preview/`                                                                                                      | Builder + table guard          | Only `Solapur` in the district list            |
| `GET /api/reports/{id}/charts/{chart_id}/data/`, `/kpis/{kpi_id}/data/`, `/map-data/`, `/table-data/`, `/table-data/total-rows/` | Builder                        | Pandharpur only                                |
| `POST /api/reports/{id}/export/pdf/`, report email                                                                               | Scope token (§5.11)            | Render calls are scoped to Rahul               |
| Alerts                                                                                                                           | Per-scope evaluation (§5.12)   | Rahul's email holds Pandharpur value only      |
| `warehouse_api` raw routes, `filter_api` schema/table/column lists                                                               | Permission removed             | 403/404 for Members                            |
| Public routes                                                                                                                    | —                              | Unfiltered (decision 1)                        |
| Preview headers sent by a Member                                                                                                 | `authenticate()` ignores them  | Member still sees only their own rows          |

**Route inventory test.** One test lists every Ninja route whose required permissions a Member holds and compares it with a reviewed allowlist in the test file. A new Member-reachable route fails CI until someone adds it to the list — and to this table.

The two missing access checks (§5.10) exist today without row access, so they ship first, on their own.

---

## 9. Security and performance

**Security**

- Server-side only. The browser never says which rows to show; it can't widen its scope by editing a URL, payload or header.
- Values reach SQL only through SQLAlchemy expressions (`in_()`), never string formatting.
- Preview headers are honoured only for super-admins, Admins and Analysts.
- The PDF scope token is signed, short-lived (5 minutes) and only accepted together with the existing render secret.
- The access list holds emails and scope values only. Emails are already in Dalgo; no new kind of PII (personally identifiable information).
- Multi-tenancy: every row-access model has an `org` FK and every query filters by `request.orguser.org`.

**Performance targets**

| Step                                 | Target                                                              | How                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Resolve a Member's scope             | < 5 ms, once per request                                            | One indexed query; only when a query touches the warehouse                          |
| Column lookup                        | < 5 ms cached; one `information_schema` query per schema per 10 min | Redis                                                                               |
| Added to a chart query               | < 50 ms                                                             | `IN` conditions; recommend indexes on scope columns in large tables (handover note) |
| Upload review for ATECF (~18 tables) | < 30 s, in a Celery task with progress                              | One grouped query per filtered table                                                |

---

## 10. Tests (only the important ones)

**Backend unit — `ddpui/tests/core/rls/`**

- `build_condition`: one test per row of the §2.1 ATECF table (Priya, Rahul, Anita, Sunil's two rows, Sunita's integer `dam_id`, new.user's blank, lead's `*`).
- `build_condition`: a row with `*` on all present columns returns no filter even when other rows restrict.
- `build_condition`: missing column → `*` holders unaffected, value holders get `false()`.
- `build_condition`: table with no scope column → no filter.
- Upload: cleaning (`pune ` → `Pune`), "did you mean", repeated emails allowed, blank vs `*`.
- Save: blocked by errors; blocked before first preview; replaces rows atomically.
- Save doesn't wipe a `missing_columns` entry recorded while the save was running (§5.1 rule 1).
- Two calls to `record_missing_columns()` for the same table queue one email (§5.1 rule 2).
- Member cap: creator, user Edit grant and group Edit grant all return View for a Member.

**Backend API — `ddpui/tests/api_tests/`**

- The launch-gate route tests in §8, plus the route inventory test.
- Access-check fixes (§5.10).
- Preview headers: honoured for Analyst, ignored for Member.
- Alerts: per-scope evaluation and delivery; external recipient with no row gets nothing.
- `migrate_member_content --dry-run` and real run on a fixture org.

**Webapp — Playwright `webapp/e2e/row-access.spec.ts`**

- Admin: download template → upload → review → preview Rahul → save.
- Rahul logs in: locked district filter, filtered charts, "view data" and CSV.
- Member sees no create/edit buttons; sharing modal read-only.

---

## 11. Milestones (16 Nov – 2 Dec)

| #   | Dates          | Work                                                                                                                                           | Done when                                                             |
| --- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| M0  | 16–17 Nov      | Access-check fixes (§5.10), own PR                                                                                                             | Merged and deployed on their own                                      |
| M1  | 16–19 Nov      | Members view-only backend: permissions + data migration, cap, floor fixed, Edit-share block, `migrate_member_content`                          | Member gets View everywhere; dry-run list ready for org emails        |
| M2  | 17–20 Nov      | Row access core: models, `ROW_ACCESS` flag, row scope + reset middleware, `fetch_from` hook, schema cache, fail-closed rules, table guard      | Unit tests for §2.1 pass; a Member's `/charts/{id}/data/` is filtered |
| M3  | 20–25 Nov      | Upload, review checks, draft, save, template, preview endpoints, everyone-at-once                                                              | ATECF's sample CSV gives the expected review                          |
| M4  | 23–27 Nov      | Webapp: Row access tab, review flow, preview mode, locked filters, empty state, chart-builder note, Member UI hiding, sharing modal, Roles tab | E2E happy path passes                                                 |
| M5  | 25–30 Nov      | Reports PDF scope token, alerts per scope, missing-column email, public-link warning                                                           | Launch-gate rows for reports and alerts pass                          |
| M6  | 30 Nov – 2 Dec | Full launch-gate suite, route inventory test, performance check on ATECF-sized data, docs                                                      | All §8 tests green                                                    |
| —   | 3 Dec          | Flagged release: Bhumi, then ATECF. Members view-only for all orgs (after the notice email)                                                    |                                                                       |

**Cut order if late:** (1) "everyone at once" table, (2) "did you mean" suggestions. Nothing else.

**Funding (spec §10):** Bhumi 20–25 contract hours; ATECF from its contract hours; access-check fixes and Members view-only not billed; anything beyond the funded hours is roadmap investment.

---

## 12. Success measures (spec §11)

| Measure                                                  | Target               | How measured                                                      |
| -------------------------------------------------------- | -------------------- | ----------------------------------------------------------------- |
| Rows seen outside a person's scope                       | 0                    | Launch-gate tests per route + preview checks during ATECF testing |
| ATECF's Admin updates the list without consulting's help | Yes, after handover  | Observed; support tickets                                         |
| Weekly active Members at ATECF and Bhumi                 | Targets to set       | PostHog                                                           |
| Orgs using row access                                    | 3 by end of Feb 2027 | `OrgRLSConfig.first_saved_at` set                                 |

**Events:** `row_access_list_uploaded` (rows, people), `row_access_list_saved`, `row_access_preview_used` (single / everyone), and a `row_access_filtered: true` property on dashboard and chart view events.

---

## 13. Handover checklist — what Dalgo can't catch (spec §5)

Consulting covers these with the org's Admin at handover:

- A valid but wrong assignment (Pune instead of Nashik).
- An email typo that matches another real user.
- Sensitive data in a table with no scope column.
- Small numbers on an unfiltered chart that reveal individuals.
- Who can edit the source sheet the CSV comes from.
- Someone clicking through the public-link warning.

Also: add indexes on scope columns in large tables; keep external users as Members; when someone leaves, remove them from Dalgo (the leftover row then shows as "no Dalgo user").

---

## 14. Decisions (spec §9)

| #   | Decision                                        | Outcome                                                                                 |
| --- | ----------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1   | Public link on a dashboard with filtered tables | Warn, then public viewers see all rows. Only Admins and Analysts can make public links. |
| 2   | Bulk invite by CSV                              | Phase 2. ATECF's ~40 users are invited one at a time in v1.                             |
| 3   | Warehouse table as the source                   | Phase 2, refreshed only with "Sync now".                                                |
| 4   | Hand-written rules                              | Cut.                                                                                    |
| 5   | Groups on the access list                       | Cut from v1; phase 2 if needed.                                                         |
| 6   | Members view-only across Dalgo                  | Decided. Floor fixed at View; content moves to an Admin.                                |

---

## 15. Open questions

Questions this plan raises that the spec doesn't answer. Each has a recommendation so work isn't blocked.

| #   | Question                                                                                 | Recommendation                                                                                            | Who      |
| --- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| Q1  | Report comments use `can_edit_dashboards`. Should Members still comment after view-only? | Yes — move comment routes to a new `can_comment_reports` that Members keep                                | Abhishek |
| Q2  | Alert Slack posts go to a channel, not a person. Whose scope?                            | Unrestricted (the author is an Admin/Analyst), with a note on the alert form: "Slack posts show all rows" | Abhishek |

---

## 16. References

- Spec (Google Doc): https://docs.google.com/document/d/10TCh8IRTnkQDaUC4FHkml_Kov2h1fWANebqtGaXc1iM/edit — tab "Spec v3 (11 Nov)"
- Row access architecture notes: `harness/features/access-control/rls-access/plan.md`, `README.md`
- Related: `harness/features/access-control/resource-sharing/`, `role-collapse/`
- Domain map: `harness/domain-map.md`
- Backend conventions: `backend/.claude/CLAUDE.md`; webapp conventions: `webapp/CLAUDE.md`
