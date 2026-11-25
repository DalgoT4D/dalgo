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
| **Row access switch**                     | `OrgPreferences.row_access_enabled`: the org's own on/off switch on the Row access page. Members are filtered only when it is on (§5.2).             |
| HLD / LLD                                 | High-Level Design / Low-Level Design.                                                                                                                |

---

## 1. Overview

### 1.1 Row access

One dashboard, and each person sees only their own rows — down to a single school or dam.

> **Example:** Rahul (an ATECF official, `rahul@mh.gov.in`) opens "Silt progress". His access-list row says district = Solapur, taluka = Pandharpur. Every chart, "view data" table and CSV shows Pandharpur rows only. Priya (an ATECF Admin) opens the same dashboard and sees every district.

Today Dalgo has no row filtering, so the only option is a separate dashboard per audience. ATECF says only its internal team can use Dalgo until this exists (spec §1).

### 1.2 Members view-only

Members can view the org's charts, dashboards, KPIs and reports but cannot create or edit anything, in every org (spec §7, decision 6). Data pages stay hidden, except Metrics.

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

| Surface                       | Where                                                                                                                                                                                                                                                    | Change                                                                                                                                                                   |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Query builder**             | `ddpui/core/datainsights/query_builder.py` → `AggQueryBuilder.fetch_from()`                                                                                                                                                                              | Takes a required `scope` argument and adds the row-access condition for it. One choke point for charts, pivots, maps, KPIs, filter values, report data and alerts.       |
| **Data API routes**           | `charts_api.py`, `kpi_api.py`, `filter_api.py`, `report_api.py`, `dashboard_native_api.py`, `public_api.py`, `warehouse_api.py`                                                                                                                          | Each route that reads warehouse rows creates the scope once (`row_scope.for_request(request)`, or `UNRESTRICTED` on public routes) and passes it down (§5.2).            |
| **Services on the data path** | `charts_service.py`, `pivot_service.py`, `maps_service.py`, `kpi_service.py`, `metric_service.py`, `dashboard_service.py`, `report_service.py`, `alerts/alert_query.py`, `datainsights/insights/*`, `warehousefunctions.py`, `visualizationfunctions.py` | Every function between a route and `fetch_from()` takes `scope` as a required argument and passes it on (§5.2).                                                          |
| **Chart routes**              | `ddpui/api/charts_api.py`: `chart-data`, `chart-data-preview`, `chart-data-preview/total-rows`, `map-data`, `map-data-overlay`, `download-csv`, `{id}/data`                                                                                              | Filtered automatically via the builder. Payload routes get a **table guard** for Members (§5.9). `{id}/data` gets its missing access check (§5.10).                      |
| **KPI routes**                | `ddpui/api/kpi_api.py` → `{kpi_id}/data/`                                                                                                                                                                                                                | Filtered automatically. Gets its missing access check.                                                                                                                   |
| **Filter values**             | `ddpui/api/filter_api.py` → `/preview/` → `dashboard_service.get_value_filter_options_with_fallback()`                                                                                                                                                   | Filtered automatically (a Member only sees their own values in the dropdown). Table guard for Members.                                                                   |
| **Raw warehouse routes**      | `ddpui/api/warehouse_api.py` (`table_data`, `column-values`, `download`, `table_count`, `insights`, `ask`), `filter_api` schema/table/column lists                                                                                                       | **Blocked for Members** by removing `can_view_warehouse_data` and `can_view_warehouses` from the Member role. Not filtered (spec §7).                                    |
| **Reports**                   | `ddpui/api/report_api.py` data routes; `ddpui/core/reports/pdf_export_service.py`                                                                                                                                                                       | Data routes filtered automatically (snapshots freeze config, not data). **PDF export renders through the public share route**, so a Member's export needs a scope token (§5.11). |
| **Alerts**                    | `ddpui/celeryworkers/alert_tasks.py` → `evaluate_alert()`; `ddpui/core/alerts/*`                                                                                                                                                                         | Evaluate once per distinct recipient scope; send each recipient only their result (§5.12).                                                                               |
| **Public routes**             | `ddpui/api/public_api.py`                                                                                                                                                                                                                                | Pass `UNRESTRICTED` → unfiltered, by decision 1. Sharing modal warns first (§5.14).                                                                                      |
| **Access control**            | `ddpui/core/access/access_control.py`                                                                                                                                                                                                                    | Members capped at View everywhere (§6.2).                                                                                                                                |
| **Sharing**                   | `ddpui/api/access_api.py`, `ddpui/core/access/resource_share.py`                                                                                                                                                                                         | Edit grants to Members rejected; Members can't change sharing (follows from the cap).                                                                                    |
| **Roles**                     | `seed/003_role_permissions.json` + data migration                                                                                                                                                                                                        | Member loses create/edit/delete and raw-warehouse permissions (§6.1).                                                                                                    |
| **Member floor**              | `ddpui/models/org_preferences.py`, `webapp/components/settings/access/RolesTab.tsx`                                                                                                                                                                      | Fixed at View; not editable (§6.3).                                                                                                                                      |
| **Row access settings (new)** | `ddpui/api/rls_api.py`, `ddpui/core/rls/*`, `ddpui/models/rls.py`, `ddpui/models/org_preferences.py`; `webapp/components/settings/access/RowAccessTab.tsx`                                                                                               | New page: template, upload, review, preview, save, and the org's on/off switch (§5.2).                                                                                   |
| **Webapp dashboards**         | Dashboard view, filters, chart builder, share modal, nav                                                                                                                                                                                                 | Preview mode banner; locked scope filters; "Members will see this in full" note; hide create/edit for Members.                                                           |
| **Superset**                  | `superset_service.py`                                                                                                                                                                                                                                    | No change (out of scope).                                                                                                                                                |
| **AI chat**                   | `chat-with-data`                                                                                                                                                                                                                                         | No change — Members don't have it, and it stays that way until it applies row access (phase 2).                                                                          |

---

## 4. High-Level Design

### 4.1 Where row access sits

```
request ─► JWT auth (CustomJwtAuthMiddleware) ── request.orguser = Rahul
              │
              ▼
          @has_permission  ── role permissions (Members: view-only)
              │
              ▼
          @has_access / access_control  ── can this person open this dashboard/chart?
              │                              (Members capped at View)
              ▼
          API route ── scope = row_scope.for_request(request)   (created once)
              │
              ▼
          service code(…, scope) ─► AggQueryBuilder.fetch_from(table, schema, scope)
                                  │
                                  ▼
                       row_filter.condition_for(scope, schema, table)
                         • no scope / Admin / Analyst  → no condition
                         • table not filtered          → no condition
                         • otherwise                   → (row1) OR (row2) …  or FALSE
                                  │
                                  ▼
                           warehouse returns only the person's rows
```

Row access is the last layer. If someone can't open a dashboard, row access never runs.

### 4.2 Design decisions

**D1 — Apply the condition inside `AggQueryBuilder.fetch_from()`, using a row scope passed down as a required argument.**
**Example:** `build_chart_query()` paginates by building an inner query with `LIMIT` and wrapping it ([charts_service.py:516](../../../../../backend/ddpui/core/charts/charts_service.py)). Because the condition is added in `fetch_from()`, it lands on the **inner** query, before `LIMIT`. Page 2 of Rahul's "view data" is page 2 of Pandharpur rows, and `total-rows` counts Pandharpur rows.
**Why it matters:** There are 31 `fetch_from()` calls across charts, pivots, maps, KPIs, filters, metrics and alerts. All of them go through one function, so the filter is written once.

**The scope is a plain argument, created once and passed down.** Each API route that reads warehouse rows builds it with `row_scope.for_request(request)` and passes it to the service, which passes it on until it reaches `fetch_from(table, schema, scope)`. Background work builds its scope the same way and passes it: alerts per group of recipients (§5.12), the PDF render from its signed token (§5.11).
**Example:** Rahul opens "Silt progress". `get_chart_data_by_id` creates Rahul's scope, calls `charts_service` with it, and `fetch_from` adds `district IN ('Solapur')`.
**Why it matters:** `scope` has **no default** anywhere on the path. A call site that forgets it fails at once in tests (missing argument) instead of quietly showing every row. Anyone reading a function can see that it filters by person.

**D2 — Fail closed everywhere.**

| Situation                                                                          | Result for a Member with values (not `*`)                                                                      |
| ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Table not seen before (created after the last save)                                | Look up its columns live. If it has a scope column, filter it.                                                 |
| A scope column filtered at the last save is now missing                            | **Ignored** (team decision): that column isn't filtered; the table's other scope columns still are. See §5.13. |
| Column lookup fails (warehouse error)                                              | No rows from that table.                                                                                       |
| Person not on the list                                                             | No rows from filtered tables.                                                                                  |
| Value can't be converted to the column's type (e.g. `D-104` for an integer column) | That value matches nothing.                                                                                    |

**Why it matters:** The spec says row access "never falls back to showing more". Treating any of these cases as "no filter" would show a Member every row. The one exception is a missing scope column: the team decided that whoever renames or drops a scope column in dbt re-uploads the sheet at the same time (§5.13).

**D3 — Each upload is stored as a draft upload; review and preview run on it; Save makes it the live one.**
**Example:** Consulting uploads ATECF's CSV. Dalgo stores it as a draft upload with its rows and shows the review. They preview Rahul and Sunita against it. Only when they press Save does it become the live list Members are filtered by.
**Why it matters:** Spec §5 says blocking errors stop the save, and spec §6 says a first setup can't be saved until it has been previewed. Writing the upload's rows straight into the live list would make an unreviewed list live immediately.

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
**Example:** Rahul's rows are read with one indexed query on `(upload, orguser)` against the live upload — about a millisecond — once per request, only when a query touches a filtered table.
**Why it matters:** Spec §3: changes "apply at once". A cache would have to be cleared for everyone on both the old and the new list on every save; if it missed someone removed from the list, they would keep their old scope until the cache expired.

---

## 5. Low-Level Design — row access (backend)

### 5.1 Models

File: `ddpui/models/rls.py` (new). Two models, one migration. Every org's lists live in the same tables, kept apart by `org`.

**The idea:** every CSV upload is stored as an **upload** with its rows. One upload per org is **live** (`status="live"`): the list Members are filtered by. A newer upload that hasn't been saved yet is the **draft**. Save makes the draft live and deletes the previous live upload, so an org has at most two uploads. **No live upload = row access not set up yet**, so Members see everything. Members are filtered by the live upload only while the org's row access switch is on (§5.2).

```python
class OrgAccessListUpload(models.Model):
    """One uploaded access list: the live one, or a draft waiting for review, preview and save."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        LIVE = "live"

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="access_list_uploads")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    file_name = models.CharField(max_length=255)       # "atecf_access_nov.csv": the uploaded file's name, shown on the page
    scope_columns = models.JSONField(default=list)     # ["district", "taluka", "dam_id"]: CSV header minus email
    # Warnings and info from the §5.5 checks, kept so the page shows them again without re-querying the warehouse.
    # Blocking errors are never stored: a file with one is not saved at all (§5.4).
    # {"warnings": [...], "info": [...], "people": {...}, "tables": {...}, "counts": {...}}
    review_result = models.JSONField(default=dict)
    previewed = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(OrgUser, null=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    saved_by = models.ForeignKey(OrgUser, null=True, on_delete=models.SET_NULL, related_name="+")
    saved_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org"], condition=Q(status="draft"), name="one_draft_upload_per_org"),
            models.UniqueConstraint(fields=["org"], condition=Q(status="live"), name="one_live_upload_per_org"),
        ]


class OrgAccessListRow(models.Model):
    """One row of an upload, for one person. Several rows for the same person add up."""
    upload = models.ForeignKey(OrgAccessListUpload, on_delete=models.CASCADE, related_name="rows")
    orguser = models.ForeignKey(OrgUser, null=True, on_delete=models.CASCADE)   # set once the person is in the org
    email = models.EmailField(null=True)                                         # lowercased; only until they join
    # "*" = every value, [] = none, ["Pune", "Nashik"] = those values (data's spelling)
    scope_values = models.JSONField()    # {"district": ["Solapur"], "taluka": ["Pandharpur"], "dam_id": "*"}

    class Meta:
        indexes = [models.Index(fields=["upload", "orguser"])]
        constraints = [
            # exactly one of orguser / email is set
            models.CheckConstraint(
                check=Q(orguser__isnull=False, email__isnull=True) | Q(orguser__isnull=True, email__isnull=False),
                name="access_row_orguser_or_email",
            ),
        ]
```

Each row points at a person in one of two ways:

| Person                        | `orguser`     | `email`          |
| ----------------------------- | ------------- | ---------------- |
| Rahul, already in the org     | Rahul (id 45) | empty            |
| Ravi, invited, not joined yet | empty         | `ravi@atecf.org` |

When Ravi accepts his invite, his rows get `orguser=Ravi` and `email` is emptied (rule 4). From then on they are found only by `orguser`.

Each upload stores its own rows, inserted in that file's order. The template download reads only the live upload's rows ordered by `id`, so it comes back in the order of the **last saved file**. Earlier uploads don't matter: their rows are deleted on Save.

**Example:** upload #1 (Rahul, Priya, Sunil) is saved, then upload #2 (Sunil, Anjali, Rahul) is saved. The template now lists Sunil, Anjali, Rahul.

**What each field holds**

`OrgAccessListUpload`: one per uploaded CSV, at most 2 per org

| Field                        | Example                                   | Why it's needed                                                                                                                                            |
| ---------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`                     | `draft` or `live`                         | Members read only the live upload. Preview reads the draft. No live upload means row access isn't set up, so Members see everything.                       |
| `file_name`                  | `atecf_access_nov.csv`                    | Shown on the page next to each upload, so Admins know which sheet is live and which is the draft. Taken from the uploaded file, without its folder path.   |
| `scope_columns`              | `district`, `taluka`, `dam_id`            | The CSV headers minus `email`. Dalgo looks for these columns in every table.                                                                               |
| `review_result`              | Warnings, info, people groups, row counts | The page shows the latest review after a refresh (spec §5). "Everyone at once" reads the counts. No blocking errors here: a file with one is never stored. |
| `previewed`                  | `true` after a preview                    | A first setup can't be saved until it has been previewed (spec §6).                                                                                        |
| `uploaded_by`, `uploaded_at` | Abhishek, 20 Nov 09:50                    | Shown on the page: "Uploaded by Abhishek".                                                                                                                 |
| `saved_by`, `saved_at`       | Abhishek, 20 Nov 10:05                    | Shown on the page: "Last saved by Abhishek on 20 Nov".                                                                                                     |

`OrgAccessListRow`: one per CSV row

| Field          | Example                                            | Why it's needed                                                                                                 |
| -------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `upload`       | Upload #1                                          | Which list this row belongs to. Deleting an upload deletes its rows.                                            |
| `orguser`      | Rahul (id 45)                                      | Whose access this is. Removing Rahul from the org deletes his rows with him.                                    |
| `email`        | `ravi@atecf.org`                                   | For someone not in the org yet: whom Save invites, and how their rows are found when they accept. Emptied then. |
| `scope_values` | district: Solapur, taluka: Pandharpur, dam_id: `*` | What this person can see. `*` means every value, blank means none, a list means those values.                   |

**How many rows each model has**

| Model                 | Holds                                                | Rows per org                             |
| --------------------- | ---------------------------------------------------- | ---------------------------------------- |
| `OrgAccessListUpload` | One uploaded list, with its review and preview state | At most 2: the live one and a draft      |
| `OrgAccessListRow`    | The people's rows of an upload, one per CSV row      | ~40 for ATECF (~80 while a draft exists) |

**Example:** ATECF over two uploads.

| Moment                  | Uploads for ATECF                 | Rahul is filtered by            |
| ----------------------- | --------------------------------- | ------------------------------- |
| First upload            | #1 draft                          | Nothing (row access not set up) |
| Save                    | #1 live                           | #1: Pandharpur                  |
| Re-upload (Rahul moves) | #1 live, #2 draft                 | #1: Pandharpur                  |
| Save                    | #2 live (#1 and its rows deleted) | #2: Mohol                       |

This table assumes ATECF's row access switch is on. With it off, Rahul is filtered by nothing at every step (§5.2).

**Why it matters:** Members only ever read the live upload's rows, so an unsaved list can't reach them. Rows are stored once, in one table and one format, and Save is a switch, not a copy. If history is ever needed, Save stops deleting the previous upload; nothing else changes.

#### Rules for writing these models

**Rule 1 — An org has at most one draft at a time. A new upload is refused while one exists, until it is saved or discarded.**
**Example:** Abhishek uploads a list for ATECF at 10:00 and hasn't saved it. Meera uploads another at 10:05. Dalgo refuses hers: "Abhishek has an unsaved upload from 10:00. Save or discard it first." Either of them can Save or Discard Abhishek's draft from the Row access page; then Meera uploads again.
**Why it matters:** Abhishek's reviewed draft can't be silently replaced by someone else's sheet.
**How:** no lock. The database's `one_draft_upload_per_org` constraint decides. Upload only **inserts** a draft; it never deletes an existing one.

```python
try:
    with transaction.atomic():
        draft = OrgAccessListUpload.objects.create(org=org, status=OrgAccessListUpload.Status.DRAFT, ...)
        OrgAccessListRow.objects.bulk_create(rows)
except IntegrityError as err:
    raise DraftExistsError(org) from err      # → 409 naming who uploaded the existing draft and when
```

`POST /draft/` also checks for an existing draft **before** starting the review task, so Meera is told at once instead of after the warehouse checks. The constraint is the final guard for two uploads at the same moment: the database lets one insert through and refuses the other, whichever server or Celery worker they run on.

| Situation                                    | Result                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| ATECF has no draft                           | Upload is stored as the draft                                            |
| ATECF has Abhishek's unsaved draft           | Meera's upload → 409 "Abhishek has an unsaved upload from 10:00"         |
| Abhishek and Meera upload at the same moment | One is stored; the other gets the same 409                               |
| Bhumi uploads while ATECF has a draft        | Stored (the rule is per org)                                             |
| Abhishek wants to upload a corrected file    | He discards his own draft first ("Discard and upload again" on the page) |

**Rule 2 — every write to an upload saves only the fields it changed.**
**Example:** Save writes `status`, `saved_by` and `saved_at` on the draft. Marking a draft previewed writes only `previewed`. Neither puts back an old value of the other's field.
**How:** `save(update_fields=[...])` or a queryset `.update(...)`, naming only its own fields.

**Rule 3 — Preview, Save and Discard name the draft upload they act on, and change it only if it is still the draft.**
**Example:** Abhishek has draft #1 open. Meera discards it, then uploads her own sheet as draft #2. Abhishek's page still thinks the draft is #1. When he clicks Save, his request says `upload_id = 1`. #1 is no longer the org's draft, so Dalgo refuses with 409: "This draft was already saved or discarded. Reload to see the current one." After reloading he sees Meera's sheet, labelled "Draft uploaded by Meera".
**Why it matters:** Without it, Abhishek would save a list he never reviewed.
**How:** The previewed, save and discard endpoints take `upload_id` (§5.15). The preview header carries it too (§5.6). The check and the change are **one** database statement, filtered on `id=upload_id, status="draft"`, so two Admins clicking at the same moment can't both succeed. If it changes 0 rows, the endpoint raises `DraftNotCurrentError` → 409.

| Clash at the same moment                | Result                                        |
| --------------------------------------- | --------------------------------------------- |
| Two Admins click Save on draft #1       | One saves it; the other gets 409              |
| Save and Discard on draft #1            | Whichever runs first wins; the other gets 409 |
| Save on draft #1 after it was discarded | 409; the live list is untouched               |

**Rule 4 — When an invited person accepts, their rows are switched from `email` to their new `OrgUser`.**
**Example:** Ravi is on the list as `email=ravi@atecf.org`. Save invites him. He accepts on 21 Nov. His rows become `orguser=Ravi, email=empty`, and on his first login he sees only his district. Nobody re-uploads the sheet. Before he accepts he can't log in, so there is nothing to filter.
**Why it matters:** Without it, Ravi's rows would never match him and he would see nothing from filtered tables.
**How:** one more step in `accept_invitation_v1` ([orguserfunctions.py:400](../../../../../backend/ddpui/core/orguserfunctions.py)), next to the existing steps for group members and dashboard shares:

```python
OrgAccessListRow.objects.filter(
    upload__org=target_org, orguser=None, email__iexact=invitation.invited_email
).update(orguser=orguser, email=None)
```

It matches by org and email, not by draft or live, so it fixes both uploads at once, and another org's rows for the same email are untouched.

| Event                                                    | Rows for that person                                                                |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Ravi accepts his invite                                  | Switched to his `OrgUser`, email emptied; filtered from his first login             |
| Ravi accepts before Save (someone invited him by hand)   | The draft's rows are switched; Save finds him already linked and doesn't invite him |
| Ravi's invite is cancelled, then sent again and accepted | Still matched, because the row keeps his email until he joins                       |
| Rahul changes his login email after joining              | Unaffected; his rows are on `orguser`                                               |
| Rahul is removed from the org                            | Deleted with his `OrgUser` (`CASCADE`)                                              |

**A same-named column that means something else is fixed in dbt.**
**Example:** `prod.applications` has a `state` column holding application status ("approved", "pending"). Dalgo filters it like any other `state` column, so Members see no rows from it. Review check 7 flags it; consulting renames the column in dbt (`application_status`) and the table stops being filtered.
**Why it matters:** A wrong match only hides rows, never shows extra ones, and fixing names in dbt is the spec's rule for every naming problem (spec §8: "Names must match; differences are fixed in dbt").

### 5.2 Row scope

File: `ddpui/core/rls/row_scope.py` (new).

```python
@dataclass(frozen=True)
class RowScope:
    org_id: Optional[int]
    unrestricted: bool                       # Admin / Analyst / super-admin / public link
    scope_columns: tuple[str, ...]
    rows: tuple[dict, ...]                   # the person's rows; empty = not on the list


UNRESTRICTED = RowScope(org_id=None, unrestricted=True, scope_columns=(), rows=())
```

**The rule:** a `RowScope` is created once, where the work starts, and passed down as an argument to every function until `fetch_from()`. Nothing stores it globally.

| Where the work starts    | Creates the scope with                                       | Example                                      |
| ------------------------ | ------------------------------------------------------------ | -------------------------------------------- |
| An API route (logged in) | `row_scope.for_request(request)`                             | Rahul opens a chart → Rahul's rows           |
| An API route in preview  | `row_scope.for_request(request)` (reads the preview headers) | Priya previews as Rahul → Rahul's rows       |
| A public route           | `row_scope.UNRESTRICTED` (decision 1)                        | Public link → all rows                       |
| The PDF render           | `row_scope.from_pdf_token(request, snapshot)` (§5.11)        | Rahul exports a report → Rahul's rows        |
| An alert evaluation      | `resolve_for_orguser(...)` per recipient group (§5.12)       | Rahul's alert → Rahul's rows                 |
| Admin-only code          | `row_scope.UNRESTRICTED`                                     | Warehouse insights (Members can't call them) |

- `for_request(request)` — the API helper. Returns the previewed person's scope if valid preview headers are present (§5.6), otherwise the caller's own. Each route calls it once and passes the scope down.
- `resolve_for_orguser(orguser)` — unrestricted if role is super-admin, admin or analyst, or the org has no saved row access (no upload with `status="live"`). Otherwise loads the Member's rows from the live upload by their `orguser`.
- `resolve_as_member(orguser, draft_upload_id=None)` — used by preview. Reads that person's rows by `orguser`, always treating them as a Member. With `draft_upload_id`, reads that draft upload's rows (preview of an unsaved list), after checking it is still the org's draft (§5.1 rule 3); otherwise reads the live upload's rows.
- `UNRESTRICTED` — no filter. Passed by public routes and Admin-only code, so "no filter" is always written out where it happens.

Rows are only ever read by `orguser`. Rows still holding an `email` (people not joined yet) are never used to filter: those people can't log in, and preview shows them as "hasn't accepted the invite yet" (§5.6).

#### Creating a row scope: `resolve_for_orguser` and `resolve_as_member`

These are the only two functions that read access-list rows. `for_request` and `from_pdf_token` call one of them.

```python
def resolve_for_orguser(orguser) -> RowScope:
    """The logged-in person's row scope, from the live list."""
    org = orguser.org
    if orguser.new_role.slug in UNRESTRICTED_ROLES or not row_access_on(org):
        return _unrestricted(org.id)
    live = _live_upload(org)
    if live is None:
        return _unrestricted(org.id)                       # row access not set up yet
    return _scope_from_upload(live, orguser)


def resolve_as_member(orguser, draft_upload_id=None) -> RowScope:
    """A person's row scope, always treated as a Member; used by preview."""
    org = orguser.org
    if draft_upload_id:
        upload = OrgAccessListUpload.objects.filter(
            id=draft_upload_id, org=org, status=OrgAccessListUpload.Status.DRAFT
        ).first()
        if upload is None:
            raise DraftNotCurrentError(draft_upload_id)    # → 409 "already saved or discarded" (§5.1 rule 3)
    else:
        upload = _live_upload(org)
        if upload is None:
            return _unrestricted(org.id)                   # nothing saved yet
    return _scope_from_upload(upload, orguser)


def row_access_on(org) -> bool:
    """Members are filtered only when the feature flag and the org's switch are both on."""
    if not is_feature_flag_enabled("ROW_ACCESS", org=org):
        return False
    return OrgPreferences.objects.filter(org=org, row_access_enabled=True).exists()


def _live_upload(org):
    return OrgAccessListUpload.objects.filter(org=org, status=OrgAccessListUpload.Status.LIVE).first()


def _scope_from_upload(upload, orguser) -> RowScope:
    rows = OrgAccessListRow.objects.filter(upload=upload, orguser=orguser).order_by("id")
    return RowScope(
        org_id=upload.org_id,
        unrestricted=False,
        scope_columns=tuple(upload.scope_columns),
        rows=tuple(r.scope_values for r in rows),          # empty = not on the list → sees nothing
    )


def _unrestricted(org_id) -> RowScope:
    return RowScope(org_id, True, (), ())
```

| Call                                                        | Result                                                      |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `resolve_for_orguser(Priya)` (Admin)                        | `unrestricted=True`, no database read                       |
| `resolve_for_orguser(Rahul)`, flag off or nothing saved yet | `unrestricted=True`                                         |
| `resolve_for_orguser(Rahul)`, list saved, switch off        | `unrestricted=True`                                         |
| `resolve_for_orguser(Rahul)`, list saved                    | `rows=({"district": ["Solapur"], ...},)` from the live list |
| `resolve_for_orguser(new.user)`, not on the list            | `rows=()` → sees nothing on filtered tables                 |
| `resolve_as_member(Rahul, 57)`                              | Rahul's rows from draft upload #57                          |
| `resolve_as_member(Rahul, 57)`, #57 saved or discarded      | `DraftNotCurrentError` → 409                                |

- **`DraftNotCurrentError`** and **`DraftExistsError`** are new, in `ddpui/core/rls/exceptions.py`; the API maps both to 409 (§5.1 rules 1 and 3).
- **`PreviewUserNotFoundError`** is new, in the same file; the API maps it to 404. It is raised when the preview header names someone who isn't an org user in this org.

#### How a request gets its row scope

```
Request ─► CustomJwtAuthMiddleware      request.orguser = Rahul   (unchanged)
        ─► API route                    scope = row_scope.for_request(request)    ← created once
        ─► service(..., scope)          passes it on
        ─► fetch_from(table, schema, scope)   adds Rahul's condition
        ─► response                     the scope ends with the request; nothing to clean up
```

`ddpui/core/rls/row_scope.py`:

```python
UNRESTRICTED_ROLES = {RoleSlug.SUPER_ADMIN, RoleSlug.ADMIN, RoleSlug.ANALYST}


def for_request(request) -> RowScope:
    """The row scope for this API request: the previewed person's, or the caller's own."""
    preview_orguser, draft_upload_id = preview_headers(request, request.orguser)
    if preview_orguser is not None:
        return resolve_as_member(preview_orguser, draft_upload_id)
    return resolve_for_orguser(request.orguser)


def preview_headers(request, orguser) -> tuple[Optional[OrgUser], Optional[str]]:
    """Preview headers count only for super-admins, Admins and Analysts with row access on (§5.6)."""
    preview_id = request.headers.get("X-Row-Access-Preview")
    if not preview_id or orguser.new_role.slug not in UNRESTRICTED_ROLES:
        return None, None
    if not row_access_on(orguser.org):
        return None, None
    preview_orguser = OrgUser.objects.filter(id=preview_id, org=orguser.org).first()   # same org only
    if preview_orguser is None:
        raise PreviewUserNotFoundError(preview_id)          # → 404
    return preview_orguser, request.headers.get("X-Row-Access-Draft")
```

**A route and a service with the scope.** Example: `GET /api/charts/{chart_id}/data/`.

```python
# ddpui/api/charts_api.py
def get_chart_data_by_id(request, chart_id: int, dashboard_filters: Optional[str] = None):
    scope = row_scope.for_request(request)                          # NEW: created once
    ...
    query_builder = charts_service.build_chart_query(payload, org_warehouse, scope)   # NEW argument


# ddpui/core/charts/charts_service.py
def build_chart_query(payload: ChartDataPayload, org_warehouse: OrgWarehouse, scope: RowScope):
    ...
    query_builder.fetch_from(payload.table_name, payload.schema_name, scope)        # NEW argument
```

`scope` has **no default** in any of these signatures. If a route or service forgets to pass it, Python raises `TypeError: missing 1 required positional argument: 'scope'` the first time a test calls it, so a missed path is caught before release instead of leaking rows.

**Functions that gain `scope`.** Every function between a data route and `fetch_from()`:

| File                                                                                                            | Functions                                                                               |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `core/charts/charts_service.py`                                                                                 | `build_chart_query` and its callers (chart data, table preview, total rows, CSV stream) |
| `core/charts/pivot_service.py`, `maps_service.py`                                                               | the functions that call `build_chart_query`                                             |
| `core/kpi/kpi_service.py`                                                                                       | `compute_latest_value`, `_compute_trend` and the KPI data functions that call them      |
| `core/metric/metric_service.py`                                                                                 | `compute_metric_value_with_sql`                                                         |
| `services/dashboard_service.py`                                                                                 | `get_value_filter_options_with_fallback` (filter dropdown values)                       |
| `core/reports/report_service.py`                                                                                | report data functions that call the chart and KPI services                              |
| `core/alerts/alert_query.py`                                                                                    | `_execute_standalone` and the KPI/metric paths (§5.12)                                  |
| `api/filter_api.py`, `api/public_api.py`                                                                        | `get_filter_preview`, `_execute_filter_preview`                                         |
| Admin-only: `warehouse_api.py`, `warehousefunctions.py`, `visualizationfunctions.py`, `datainsights/insights/*` | pass `UNRESTRICTED` (Members can't reach them, spec §7)                                 |

The exact list is confirmed at the start of M2 with a search for `fetch_from(`; the missing-argument error catches any function left out.

| Request                                | Scope created by                                  | Condition on a warehouse query     |
| -------------------------------------- | ------------------------------------------------- | ---------------------------------- |
| Rahul (Member) opens a chart           | `for_request` → `resolve_for_orguser(Rahul)`      | Rahul's rows: `district = Solapur` |
| Priya (Admin) opens a chart            | `for_request` → `resolve_for_orguser(Priya)`      | `unrestricted=True`, no filter     |
| Priya previews as Rahul                | `for_request` → `resolve_as_member(Rahul, draft)` | Rahul's rows                       |
| Rahul sends the preview header himself | `for_request` (header ignored) → his own          | Rahul's rows                       |
| Public dashboard link (no login)       | `UNRESTRICTED`, written in the public route       | No filter (decision 1)             |

**CSV download streams after the route returns.** `POST /download-csv/` returns a `StreamingHttpResponse`, and its generator runs the page queries later ([charts_api.py:834](../../../../../backend/ddpui/api/charts_api.py)). The route creates the scope **before** building the response and passes it into `stream_chart_data_csv(..., scope)`, so every page of the file is filtered.
**Example:** Rahul downloads "Silt progress" as CSV. All 40 pages of the file hold Pandharpur rows only.

**Why no clean-up is needed:** the scope is a normal argument and lives only as long as the function call. Nothing is shared between requests, so there is no middleware and nothing to reset in tests.

Every Member-reachable path is also covered by the launch-gate tests in §8, including a test that fails if a new Member-reachable route appears without being reviewed.

#### Feature flag and the org's on/off switch

Two separate controls decide whether Members are filtered. Both must be on.

| Control           | Who sets it                                             | Where                                                | What it does                                                                                                                                                                                          |
| ----------------- | ------------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ROW_ACCESS` flag | The Dalgo team                                          | `ddpui/utils/feature_flags.py`                       | Off: the Row access page is hidden and nobody is filtered. This is how the 3 Dec release reaches Bhumi and ATECF only.                                                                                |
| Row access switch | The org's Admins and Analysts (`can_manage_row_access`) | `OrgPreferences.row_access_enabled`, default `False` | Off: the page shows only the switch; template, upload, review, preview, save and discard are locked, and Members see everything. On: the page unlocks, and Members are filtered once a list is saved. |

```python
# ddpui/models/org_preferences.py: new field, one migration
row_access_enabled = models.BooleanField(default=False)
```

**The rule:** the switch starts off. Nothing else on the Row access page works until an Admin turns it on.
**Example:** On 20 Nov Abhishek opens the Row access page for ATECF and sees only "Row access: Off". He turns it on, and Download template and Upload appear. Members still see everything, because no list is saved yet. He uploads, previews and saves; from Rahul's next request Rahul sees Pandharpur only. If something looks wrong later, Abhishek turns the switch off: Members see everything again and the page locks, but the saved list (and any draft) stays as it is. Turning it back on picks up where he left off.
**Why it matters:** the org opts in on purpose, and can stop filtering at once without deleting its list or asking the Dalgo team to change the flag.

| Flag | Switch | Live list | Row access page                     | Rahul (Member) sees |
| ---- | ------ | --------- | ----------------------------------- | ------------------- |
| Off  | any    | any       | Hidden                              | Everything          |
| On   | Off    | any       | Only the switch                     | Everything          |
| On   | On     | None yet  | Unlocked: template, upload, preview | Everything          |
| On   | On     | Saved     | Unlocked                            | Pandharpur only     |

- **Every `/api/rls/` endpoint checks the switch** except `GET /status/` and `PUT /enabled/`. With it off, they return 400 "Turn on row access first". Two read endpoints answer instead of refusing: `/me/` returns `{filtered: false}` and `/table-status/` returns `{filtered: false}`, so Member dashboards and the chart builder keep working.
- **Preview needs the switch on.** `preview_headers` checks `row_access_on(org)` instead of only the flag, so with the switch off the headers are ignored (§5.6).
- **Save and Discard don't change the switch.** It is already on before anything can be uploaded, so the first Save filters Members straight away (after the required preview, §5.7).
- Turning the switch on or off takes effect on the next request; there is nothing to invalidate (D7). `row_access_on` adds one small query, made once per request, when the route creates a Member's scope.
- Everything that reads a Member's scope goes through `resolve_for_orguser`, so alerts (§5.12) and PDF exports (§5.11) follow the switch with no extra code.

### 5.3 Building the condition

File: `ddpui/core/rls/row_filter.py` (new). Called from `AggQueryBuilder.fetch_from()`.

```python
def fetch_from(self, db_table: str, db_schema: str, scope: RowScope):
    self.select_from = table(db_table, schema=db_schema)
    condition = row_filter.condition_for(scope, db_schema, db_table)
    if condition is not None:
        self.where_clauses.append(condition)
    return self
```

`scope` is required. Every one of the 31 existing `fetch_from()` calls passes it (§5.2).

`condition_for` connects `fetch_from` to `build_condition`: it takes the scope it was given and looks up the table's real columns.

```python
def condition_for(scope: RowScope, db_schema: str, db_table: str):
    """The row filter for this table, or None for no filter."""
    if scope.unrestricted:
        return None                                    # public link / Admin / Analyst
    if db_schema.lower() == "information_schema":
        return None                                    # listing tables/columns, not NGO data
    live_columns = schema_cache.table_columns(scope.org_id, db_schema, db_table)  # {"district": "str", "block_id": "int", ...}
    return build_condition(scope, live_columns)
```

| Rahul opens a chart on…                                             | `condition_for` returns                           |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| `prod.silt_data` (has `district`)                                   | `district IN ('Solapur')`                         |
| `prod.national_totals` (no scope column)                            | `None` → shown in full                            |
| `prod.silt_data` after `district` was renamed, `taluka` still there | `taluka IN ('Pandharpur')`: `district` is ignored |
| `prod.silt_data` after its only scope column was renamed            | `None` → shown in full (team decision, §5.13)     |
| Any table, logged in as Priya (Admin)                               | `None`                                            |
| Any table, via a public link                                        | `None` (`UNRESTRICTED`, decision 1)               |

```python
def build_condition(scope: RowScope, live_columns: dict[str, str]):
    """None = no filter; false() = no rows."""
    if scope.unrestricted:
        return None
    # match column names ignoring case; keep the real name for the SQL
    by_lower = {}
    for name, col_type in live_columns.items():
        by_lower.setdefault(name.lower(), []).append((name, col_type))
    present = [c for c in scope.scope_columns if c in by_lower]   # a scope column the table lacks is ignored
    if not present:
        return None                                  # table has no scope column → shown in full
    if any(len(by_lower[c]) > 1 for c in present):
        return false()                               # "district" and "District" both exist → fail closed

    row_clauses = []
    for row in scope.rows:
        parts, blank = [], False
        for c in present:
            value = row[c]
            if value == "*":
                continue
            if not value:
                blank = True                         # blank cell = none
                break
            real_name, col_type = by_lower[c][0]
            parts.append(column(real_name).in_(coerce(value, col_type)))
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
- Only the scope columns the table has **now** are used. A scope column the table lacks, because it never had it or because it was renamed or dropped in dbt, is ignored (§5.13).
- Column names match ignoring case, and the SQL uses the warehouse's real spelling (below).

#### Column names: matched ignoring case

Postgres and BigQuery treat the case of column names differently:

|                                                    | Postgres                                          | BigQuery             |
| -------------------------------------------------- | ------------------------------------------------- | -------------------- |
| Column created as `District` without quotes        | Stored as `district`                              | Stored as `District` |
| Column created as `"District"` with quotes         | Stored as `District`; SQL must write `"District"` | n/a                  |
| Can one table have both `district` and `District`? | Yes, if quoted                                    | No                   |

**The rule:** a scope column matches a warehouse column whose name is the same ignoring case. The SQL uses the warehouse's real name.
**Example:** the sheet header is `district` (headers are lowercased, §5.4 step 2). A BigQuery table has `District`. Dalgo matches them and writes `WHERE District IN ('Solapur')`. SQLAlchemy adds quotes when Postgres needs them.
**Why it matters:** with an exact match, `district` wouldn't find `District`. The table would be treated as having no scope column, so Members would see all of it.

| Sheet header | Warehouse column                               | Result                                                                                         |
| ------------ | ---------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `district`   | `district`                                     | Filtered on `district`                                                                         |
| `district`   | `District`                                     | Filtered on `District`                                                                         |
| `district`   | both `district` and `District` (Postgres only) | Can't tell which one is meant → no rows for Members, and a review warning: "rename one in dbt" |

The same ignore-case match is used when finding filtered tables (§5.4 step 3), and for review check 2 ("scope column exists in no table").

#### `coerce`: sheet text → the column's type

The sheet is a CSV, so every stored value is text (`["101", "102"]`). The warehouse column may be an integer or a date. The same column name can have different types in different tables (`visits.block_id` integer, `surveys.block_id` text), so values are stored as text and converted per table, at query time.

```python
def parse_bool(value: str) -> bool:
    """'true'/'yes'/'1' → True, 'false'/'no'/'0' → False; anything else is dropped."""
    v = value.strip().lower()
    if v in ("true", "yes", "1"):
        return True
    if v in ("false", "no", "0"):
        return False
    raise ValueError(value)


# keyed by the column's Python type name, from get_table_columns() (below)
CONVERTERS = {
    "str": str,
    "int": int,
    "Decimal": Decimal,
    "float": Decimal,
    "date": lambda v: date.fromisoformat(v).isoformat(),   # YYYY-MM-DD, kept as text: Postgres can't render a date literal
    "bool": parse_bool,                                    # "true"/"false", "yes"/"no", "1"/"0"
}


def coerce(values: list[str], col_type: str) -> list:
    """Sheet values in the column's type; values that can't be converted are dropped."""
    convert = CONVERTERS.get(col_type)
    if convert is None:
        return []                             # timestamp, JSON, …: not a usable scope column → matches nothing
    out = []
    for value in values:
        try:
            out.append(convert(value))
        except (ValueError, ArithmeticError):
            continue
    return out
```

`col_type` is the column's **Python type name**. SQLAlchemy already turns every Postgres and BigQuery type into a Python type, so there is no list of warehouse type names to keep in sync (`int4`, `integer`, `INTEGER`, `INT64` all become `int`; `varchar`, `STRING(50)` become `str`).

| Warehouse type (examples)                 | `col_type`          | Allowed as a scope column?                |
| ----------------------------------------- | ------------------- | ----------------------------------------- |
| `varchar`, `text`, BigQuery `STRING`      | `str`               | Yes                                       |
| `int4`, `int8`, BigQuery `INT64`          | `int`               | Yes                                       |
| `numeric`, BigQuery `NUMERIC` / `FLOAT64` | `Decimal` / `float` | Yes                                       |
| `date`, BigQuery `DATE`                   | `date`              | Yes                                       |
| `bool`, BigQuery `BOOL`                   | `bool`              | Yes                                       |
| `timestamptz`, `jsonb`, arrays, …         | anything else       | No: matches nothing, and the review warns |

| Stored values    | Column type | `coerce` returns | SQL                            |
| ---------------- | ----------- | ---------------- | ------------------------------ |
| `["Solapur"]`    | `str`       | `["Solapur"]`    | `district IN ('Solapur')`      |
| `["101", "102"]` | `int`       | `[101, 102]`     | `block_id IN (101, 102)`       |
| `["101", "abc"]` | `int`       | `[101]`          | `block_id IN (101)`            |
| `["abc"]`        | `int`       | `[]`             | `block_id IN ()` → no rows     |
| `["2026-02-01"]` | `date`      | `["2026-02-01"]` | `visit_date IN ('2026-02-01')` |
| `["yes"]`        | `bool`      | `[True]`         | `attended IN (true)`           |

Nothing about types is stored at upload: values stay as text, and the type is read live on every query. If a column's type changes in the warehouse after Save, the next query uses the new type.

**The rule:** a value that can't be converted to the column's type is dropped, never guessed.
**Example:** `12.5` on an integer column is dropped, not rounded to `12`, so Rahul never sees block 12 by accident.
**Why it matters:** a dropped value can only show less, never more. It's a safety net for a column whose type changes after Save.

**How `live_columns` is found:** `ddpui/core/rls/schema_cache.py`.

- Reuses the existing `Warehouse.get_table_columns(schema, table)` (`postgres.py`, `bigquery.py`), which already reads columns through the SQLAlchemy inspector for both warehouses.
- One small change there: each column dict also returns `"python_type": column["type"].python_type.__name__` (`None` for `NullType`). Existing callers ignore the extra key.
- Cached in Redis for 10 minutes per table, key `rls_cols:{org_id}:{schema}.{table}`. Returns `{column: python_type_name}`, e.g. `{"district": "str", "block_id": "int"}`.
- Finding filtered tables at upload (§5.4 step 3) and the template's column search (§5.8) list tables with `get_tables()` and read each one through the same cache. This runs in the upload's Celery task, so many tables don't time out a request.
- If the lookup fails, Members get `false()` for that table.

**Executor note:** `charts_service.execute_query()` compiles with `literal_binds=True`, so SQLAlchemy renders bound values into the SQL text using the dialect's own escaping. That is the same path every existing dashboard filter uses. Switching the executor to server-side parameters is a wider change and is not part of v1.

### 5.4 Upload: parse and clean

File: `ddpui/core/rls/access_list_service.py` (new).

1. **Parse** with `csv.DictReader`. Lowercase and trim emails. Trim cell values. Split on `;`, drop empty parts.
   `"Pune; Nashik"` → `["Pune", "Nashik"]`; `"*"` → `"*"`; `""` → `[]`.
2. **Scope columns** = header minus `email`, lowercased and trimmed. Duplicate headers are a blocking error.
3. **Find filtered tables** from the schema cache: every `schema.table` that has at least one scope column, matched ignoring case (§5.3).
4. **Link each email to a person:** if it belongs to an `OrgUser` in this org, the row gets `orguser`. Otherwise the row keeps the `email`; that person is invited when the list is saved (§5.7) and listed by check 4.
   **Example:** `rahul@mh.gov.in` → `orguser=Rahul`. `ravi@atecf.org` (not in this org yet) → `email=ravi@atecf.org`.

   **Stop here if any blocking check fails** (§5.5 checks 1 and 2). Nothing is stored and the existing draft and live uploads are untouched. The task result carries the errors, and the page shows them straight away:

   ```
   {"status": "blocked", "errors": [{"check": 2, "message": "Column 'ngo' is not in any table"}]}
   ```

5. **Fetch real values** (D5): for each filtered table, one grouped count over the scope columns it has. Results are capped at 50,000 groups per table. Above that, Dalgo falls back to `SELECT DISTINCT` per column (also capped), and the "everyone at once" counts for that table show "too many to count". These run on the warehouse in a Celery task with progress, so a slow warehouse doesn't time out the upload request.
6. **Clean values** (D4): match each value case- and space-insensitively against the real values for that column. Store the data's spelling. Unmatched values are kept as typed and flagged "value not found", with the closest match from `difflib.get_close_matches` ("Ahmednagar" → did you mean "Ahilyanagar"?). For non-text columns, the sheet value goes through the same converter as `coerce` (§5.3) before comparing, so `"101"` matches `101` and `"yes"` matches `true`. Values are still stored as text.
7. **Store as the draft upload** (§5.1 rule 1), in one transaction:
   - create `OrgAccessListUpload(status="draft")` with `file_name` (the uploaded file's name, e.g. `atecf_access_nov.csv`), `scope_columns`, `review_result` (§5.5) and `uploaded_by`;
   - `bulk_create` its rows in CSV order, each with its `orguser` or `email` from step 4.

   An existing draft is never deleted here. If another Admin's draft was stored while this file was being reviewed, the insert hits the one-draft constraint and the task result is a 409 naming that draft's uploader.

   Nobody is invited at upload, so a discarded draft sends no emails.

   The live upload is not touched, so Members keep their current access until Save. Only files with no blocking errors reach this step, so `review_result` holds warnings and info only.

### 5.5 Review checks

All checks from spec §5. They run on upload only — no daily job.

| Type          | Stored?                                        | Where the page gets it                                                                           |
| ------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Blocking**  | No. The file is not saved at all (§5.4 step 4) | The upload task's result, shown once right after upload                                          |
| Warning, Info | Yes, in the draft's `review_result`            | `GET /draft/` or `GET /status/`, so they survive a refresh until the draft is saved or discarded |

**Example:** Abhishek uploads a CSV with a column `ngo` that no table has. The page shows "Column 'ngo' is not in any table" and nothing is saved. He fixes the sheet and uploads again; this time it is stored as a draft with 3 warnings, which stay on the page until he saves it, or discards it and uploads a corrected file.

| #   | Check                                                              | Example                                                                       | Type                                                   | How                                                                                                                                                 |
| --- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | File is malformed: no `email` column, duplicate headers, not a CSV | `email` column missing                                                        | **Blocking**                                           | Parse step                                                                                                                                          |
| 2   | A scope column exists in no table                                  | `ngo` vs the data's `ngo_name`                                                | **Blocking**                                           | Schema cache                                                                                                                                        |
| 3   | Member has no row, so sees nothing                                 | `new.user@atecf.org`                                                          | Warning                                                | Members (role = member) not on the list                                                                                                             |
| 4   | Email on the list isn't in this org yet                            | `ravi@atecf.org`, or a typo                                                   | Warning: "These people will be invited when you save"  | Not an `OrgUser` in this org (§5.4 step 4). The full list is shown so the Admin can catch a typo before anyone is invited                           |
| 5   | Value not found in the data, with the closest match                | "Ahmednagar": did you mean "Ahilyanagar"?                                     | Warning                                                | §5.4 step 6                                                                                                                                         |
| 6   | Blank cell, so sees nothing on tables with that column             | `dam_id` left empty                                                           | Warning                                                | Cell is `[]`                                                                                                                                        |
| 7   | Same-named column whose values never match the list                | `state` holding application status                                            | Warning: "rename it in dbt if it means something else" | No listed value for that column is found in that table, while it is found in other tables                                                           |
| 8   | Partial scope: scoped to a taluka, but a table only has district   | Sees the whole district on that table                                         | Info                                                   | Person has a non-`*` value on a column the table lacks                                                                                              |
| 9   | `*` on every column                                                | Confirm `lead@atecf.org` should see everything                                | Info                                                   |                                                                                                                                                     |
| 10  | A value in the data no one is assigned                             | New district Jalna                                                            | Info                                                   | Real values minus all listed values                                                                                                                 |
| 11  | Tables affected                                                    | `silt_daily: district, taluka`. `farmer_list`: not filtered (no scope column) | Info, shown before saving                              | Schema cache                                                                                                                                        |
| 12  | Dashboards Members can open that use unfiltered tables             | Listed by dashboard                                                           | Warning                                                | Dashboards that are not private, or private but shared with a Member or a group containing one, whose charts/KPIs read a table with no scope column |

Also, from spec §4 journey 5: when someone is removed from the org, their saved rows are deleted with their `OrgUser`, so they drop off the list.

**Example:** Abhishek's sheet has `rahul@mh.gov.in` (in the org), `ravi@atecf.org` (new to Dalgo) and `rahull@mh.gov.in` (a typo). Check 4 lists Ravi and `rahull@mh.gov.in` as "will be invited when you save". Abhishek spots the typo, fixes the sheet and uploads again. On Save, only Ravi is invited.

**Repeated emails are allowed** — they are how a person gets two scopes. They are not an error.

**How it's shown** (spec §5, design to mock): one step at a time, counts first, details only where action is needed.

```
1. What changes   — dashboards affected, each: N charts filtered, M shown in full → open for tables + columns
2. Must fix       — blocking errors, from the upload result only; nothing was saved, re-upload a fixed file
3. People         — grouped counts side by side:
                      will see their data | will see nothing | sees everything | will be invited / not joined yet
                    only groups needing action start open
4. Worth a look   — collapsed: same-named columns, partial scopes, unassigned values
5. Preview, then save
```

"Will see nothing" collects three reasons: no row (check 3), blank cell (check 6), value not found (check 5).

### 5.6 Preview

Spec §6: pick a person and see any dashboard exactly as they would, including empty charts and fixed filters, without logging in as them. For Admins, Analysts and consulting.

**How it works**

- **Only people who have joined can be previewed.** Someone still on the list by `email` shows in the "Preview as" picker greyed out: "Ravi hasn't accepted the invite yet, so there's nothing to preview." Once he accepts, he can be previewed like anyone else.
- The webapp's dashboard view takes `?previewAs=<orguser_id>&draft=<upload_id>`. In preview mode, every data request carries `X-Row-Access-Preview: <orguser_id>`, plus `X-Row-Access-Draft: <upload_id>` when previewing a draft.
- `row_scope.for_request(request)` honours these headers **only** for super-admins, Admins and Analysts in an org with the flag on. For anyone else they are ignored. The preview `OrgUser` must be in the same org (otherwise 404). The scope becomes `resolve_as_member(preview_orguser, draft_upload_id)`, and the route passes it down like any other scope. If that upload is no longer the org's draft, the request gets 409 "already saved or discarded" (§5.1 rule 3).
- **Preview needs the row access switch on** (§5.2). With it off the page is locked and the preview headers are ignored.
- **Which list preview uses:** the draft upload if there is one (what the person **will** see after Save), otherwise the live upload (what they see **now**). So preview works before and after Save (spec §6: "after that, preview is available anytime").
- `GET /api/rls/preview/dashboards/{id}/?orguser_id=` answers "can this person open this dashboard?" using `access_control` for that `OrgUser`. If they can't, the page shows "Rahul can't open this dashboard" instead of charts.
- A banner shows which list is used: "Previewing as rahul@mh.gov.in · Unsaved upload · Exit preview", or "· Saved list ·".
- Starting a preview of a draft calls `POST /api/rls/draft/{upload_id}/previewed/`, which sets `previewed = True` on the draft upload (`update_fields=["previewed"]`). Opening the "everyone at once" table counts too, so an org with no dashboards yet can still complete its first setup.

**Example:** Before the first save, consulting picks Sunita in preview. On "Silt progress" every chart shows dam D-104 only; the District filter is locked to Beed; a national-totals chart shows national totals.

**Everyone at once** (cut first if late): `GET /api/rls/preview/everyone/` returns one row per person on the list (the draft upload, or the live one when there is no draft), built from the grouped counts saved in that upload's `review_result` (§5.4) — no extra warehouse queries.

| email              | district   | taluka     | dam_id | silt_daily rows | dams rows | Status                    |
| ------------------ | ---------- | ---------- | ------ | --------------- | --------- | ------------------------- |
| rahul@mh.gov.in    | Solapur    | Pandharpur | \*     | 1,234           | 89        | Has access                |
| new.user@atecf.org | Solapur    | _(blank)_  | \*     | 0               | 12        | No row on `taluka` tables |
| anita@atecf.org    | Ahmednagar | Parner     | \*     | 0               | 0         | Value not found           |
| ravi@atecf.org     | Solapur    | Mohol      | \*     | 640             | 31        | Not joined yet            |

Status values (spec §6): has access, no row, value not found, plus "not joined yet" for people still on the list by `email`. Their counts show what they will see once they accept.

### 5.7 Save

`POST /api/rls/draft/{upload_id}/save/`, in one transaction:

1. Refuse if this is the first setup (no live upload yet) and the draft hasn't been previewed. Later saves don't need a preview (spec §6). (No blocking-error check needed: a file with one never becomes a draft.)
2. Delete the previous live upload (its rows go with it). Deleting first keeps the one-live-upload constraint true at every step.
3. Switch the draft to live and set `saved_by`, `saved_at`, in **one** statement that only matches if `upload_id` is still the org's draft (§5.1 rule 3).
4. If that changed 0 rows, the draft was already saved or discarded: raise `DraftNotCurrentError` → 409. The transaction rolls back, so the previous live upload deleted in step 2 is **restored**.
5. After the transaction commits, invite everyone still on the list by `email` (below).

Save does not touch the row access switch (§5.2). The switch is already on, since nothing can be uploaded while it is off, so Members are filtered by the saved list from their next request.

```python
with transaction.atomic():
    OrgAccessListUpload.objects.filter(org=org, status=OrgAccessListUpload.Status.LIVE).delete()
    updated = OrgAccessListUpload.objects.filter(
        id=upload_id, org=org, status=OrgAccessListUpload.Status.DRAFT
    ).update(status=OrgAccessListUpload.Status.LIVE, saved_by=orguser, saved_at=timezone.now())
    if updated == 0:
        raise DraftNotCurrentError(upload_id)          # rollback: the old live list comes back
    transaction.on_commit(lambda: invite_people_on_list(upload_id, orguser))
```

**Why the rollback matters:** if Meera discarded the draft a moment before Abhishek's Save, step 2 would already have deleted the live list. Without the rollback, ATECF would have no live list, and Members would see everything.

**Inviting the people on the list.** After the Save commits (`transaction.on_commit`, so a failed Save sends no emails), `invite_people_on_list` takes each distinct `email` still on the saved rows and invites it as a Member with the existing `invite_user_to_org` ([orguserfunctions.py:245](../../../../../backend/ddpui/core/orguserfunctions.py)):

| Email on the list                                | What happens                                                                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Ravi, new to Dalgo                               | An invite is created and emailed. His rows keep the email until he accepts (§5.1 rule 4)                                            |
| Sunita, a Dalgo user in another org              | `invite_user_to_org` adds her to this org at once. Her rows are switched to her new `OrgUser` straight away (same update as rule 4) |
| Meena, already has a pending invite for this org | Skipped. `invite_user_to_org` would re-send her invite email on every Save                                                          |
| Rahul, joined between upload and Save            | Nothing to do: his rows were already switched when he accepted                                                                      |

**Example:** Abhishek saves a list with Ravi, Sunita and Meena still on it by email. Ravi gets an invite email. Sunita is added to ATECF at once and is filtered from her next login. Meena gets nothing new.

**Discard** (`DELETE /api/rls/draft/{upload_id}/`): one statement that deletes the upload only if it is still the org's draft; its rows go with it. If it deleted nothing, 409 (§5.1 rule 3). The live upload is untouched. Any Admin can discard any draft, so a forgotten draft never blocks uploads for long.

```python
deleted, _ = OrgAccessListUpload.objects.filter(id=upload_id, org=org, status=OrgAccessListUpload.Status.DRAFT).delete()
if deleted == 0:
    raise DraftNotCurrentError(upload_id)
```

Takes effect on the next request. There is nothing to invalidate (D7).

### 5.8 Template download

`GET /api/rls/template/` (spec §3 step 1)

| Situation                  | Download contains                                                                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First time (nothing saved) | Header `email` + the scope columns the Admin picked on the page (`?columns=district,taluka,dam_id`). One row per current Member, scope cells blank. Admins and Analysts are left out. |
| After a save               | The live upload's rows in their uploaded order (by `id`), then a row for each Member not yet on it, scope cells blank.                                                                |

The `email` cell is written from the row's person: `orguser.user.email`, or the row's own `email` for someone not joined yet.

Values are written back joined with `; `, and `*` as `*`. There are no reference-value rows; spec v3 doesn't ask for them, and they would break re-upload.

**Picking the columns (first time).** The spec says the template has the scope columns but not how they're chosen; consulting agrees them with the org (spec §4 journey 1). The page has one search box with two kinds of results:

- **Search a column:** typing `distr` lists matching columns, each with the tables that have it.
- **Search a table:** typing `silt` lists matching tables; opening one lists its columns.

```
🔍 [ distr ]
  ☐ district     — in 5 tables: silt_daily, dams, state_summary, farmer_list, visits
  ☐ district_id  — in 1 table: geo_master

🔍 [ silt ]
  ▸ prod.silt_daily
      ☐ district  (5 tables)   ☐ taluka  (3 tables)   ☐ date   ☐ silt_removed

Template columns:  email · district ✕ · taluka ✕ · dam_id ✕     [Download template]
```

**The rule:** a ticked column filters **every** table that has it, not only the table it was found in (spec §2: "no table picking").
**Example:** The Admin finds `district` under `silt_daily`. It also filters `dams`, `state_summary`, `farmer_list` and `visits`, so the page shows "in 5 tables" next to it.
**Why it matters:** Without the table list, an Admin could think they are choosing which tables to filter.

- Data comes from `GET /api/rls/columns/`: every table in the warehouse and its columns, from the schema cache (§5.3) — no new warehouse query. Loaded once; searching happens in the browser, so it stays fast on slow connections.
- The picks only pre-fill the template. The Admin can still add or remove headers in the CSV; the **uploaded header** is what counts (§5.4 step 2).

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

- **Data routes** (`/reports/{id}/charts/{chart_id}/data/`, `/kpis/{kpi_id}/data/`, `/map-data/`, `/table-data/`, `/table-data/total-rows/`): `ReportSnapshot` freezes config but queries data live ([report.py:8](../../../../../backend/ddpui/models/report.py)). Each route creates the scope with `row_scope.for_request(request)` and passes it to `report_service`, like the chart routes.
- **PDF export** (`POST /reports/{id}/export/pdf/`) renders `/share/report/{public_share_token}?print=true` in headless Chromium. That page calls **public** routes, so without a fix a Member's PDF would contain every row. The fix is below.

#### How a Member's PDF gets their scope

```
Rahul ─► POST /api/reports/57/export/pdf/      export_report_pdf: Rahul known (login)
          └─ generate_pdf(57, "abc123", Rahul)
              ├─ Member → token "k7Xp…" in Redis: rls_pdf:k7Xp… → {orguser_id: 45, snapshot_id: 57}
              └─ hidden Chromium: every request gets  x-render-secret + x-row-access-pdf: k7Xp…
                  └─ GET /api/v1/public/reports/abc123/charts/12/data/
                      └─ scope = row_scope.from_pdf_token(request, snapshot)  → Rahul's scope
                          └─ generate_chart_data_and_config(..., scope) → fetch_from → Pandharpur only
          └─ render done → Redis key deleted
```

**Step 1 — `export_report_pdf` passes the exporter.** `ddpui/api/report_api.py`:

```python
pdf_bytes = PdfExportService.generate_pdf(snapshot_id, share_token, orguser, dashboard_filters=dashboard_filters)
```

`orguser` is a required argument of `generate_pdf` (no default), so no caller can skip it.

**Step 2 — `generate_pdf` makes a token for Members only.** `ddpui/core/reports/pdf_export_service.py`:

```python
scope_token = None
if row_scope.needs_pdf_scope(orguser):                         # Members only
    scope_token = secrets.token_urlsafe(32)
    redis.set(
        f"rls_pdf:{scope_token}",
        json.dumps({"orguser_id": orguser.id, "snapshot_id": snapshot_id}),
        ex=PDF_SCOPE_TTL_S,                                    # 300 s, safety net if the worker dies
    )
try:
    def _inject_render_headers(route):
        headers = {**route.request.headers, "x-render-secret": render_secret}
        if scope_token:
            headers["x-row-access-pdf"] = scope_token
        route.continue_(headers=headers)

    page.route("**/*", _inject_render_headers)
    ...                                                        # render, page.pdf()
finally:
    if scope_token:
        redis.delete(f"rls_pdf:{scope_token}")                 # stops working as soon as the PDF is done
```

- The token is random and carries no data. A new one is made for each export, so two people exporting the same report never mix.
- `page.route("**/*", ...)` already catches every request the page makes, including the chart-data `fetch(...)` calls. **The frontend does not change.**
- The token never reaches the user's browser or a URL. Admin and Analyst exports get no token and no header: they run exactly as today.

**Step 3 — `row_scope.py`: who needs a token, and reading it back.**

```python
def needs_pdf_scope(orguser) -> bool:
    """Only filtered roles need a scope token for the PDF render."""
    return orguser.new_role.slug not in UNRESTRICTED_ROLES


def from_pdf_token(request, snapshot) -> RowScope:
    """Scope for a public report request: the Member's during their PDF render, else unrestricted."""
    token = request.META.get("HTTP_X_ROW_ACCESS_PDF")
    if not token or not has_valid_render_secret(request):
        return UNRESTRICTED                                    # public link, or an Admin/Analyst render
    raw = redis.get(f"rls_pdf:{token}")
    if raw is None:
        raise PdfScopeInvalidError()                           # expired or made up → 404
    data = json.loads(raw)
    orguser = OrgUser.objects.filter(id=data["orguser_id"], org=snapshot.org).first()
    if data["snapshot_id"] != snapshot.id or orguser is None:
        raise PdfScopeInvalidError()                           # another report, or user removed → 404
    return resolve_for_orguser(orguser)
```

| Request to a public report route                               | Scope                           |
| -------------------------------------------------------------- | ------------------------------- |
| Funder opens the public link                                   | `UNRESTRICTED` (decision 1)     |
| Priya's (Admin) PDF render, no header                          | `UNRESTRICTED`                  |
| Rahul's PDF render, valid token                                | Rahul's scope → Pandharpur only |
| Header present but not in Redis, wrong report, or user removed | 404, never all rows             |

**The rule:** a request carrying a scope token is served with that Member's scope, or refused. It never falls back to all rows.
**Example:** Rahul's render runs past the 5-minute safety TTL; its remaining chart calls get 404 and those charts show as unavailable, instead of every district's rows.
**Why it matters:** the render secret skips the report's `is_public` check, so a fallback to "no filter" there would serve every row of a private report.

`PdfScopeInvalidError` is new, in `ddpui/core/rls/exceptions.py`; the public routes map it to 404.

**Step 4 — public report routes pass the scope.** Each of these adds `scope = row_scope.from_pdf_token(request, snapshot)` and passes it on, like `get_public_report_chart_data`:

```python
def get_public_report_chart_data(request, token: str, chart_id: int):
    snapshot, chart_config, org_warehouse = _get_frozen_chart_for_public_report(token, chart_id, request)
    scope = row_scope.from_pdf_token(request, snapshot)                                          # NEW
    ...
    chart_data = generate_chart_data_and_config(payload, org_warehouse, scope, chart_id=chart_id)   # NEW: scope
```

| Route                                 | Function                             |
| ------------------------------------- | ------------------------------------ |
| `…/reports/{token}/charts/{id}/data/` | `get_public_report_chart_data`       |
| `…/charts/{id}/data-preview/`         | `get_public_report_table_data`       |
| `…/charts/{id}/total-rows/`           | `get_public_report_table_total_rows` |
| `…/charts/{id}/map-data/`             | `get_public_report_map_data`         |
| `…/kpis/{id}/data/`                   | `get_public_report_kpi_data`         |
| `…/filters/preview/`                  | `get_public_report_filter_preview`   |

Public dashboard routes stay `UNRESTRICTED` (decision 1). A route that forgets the scope fails with the missing-argument error (§5.2).

### 5.12 Alerts

Spec §7: an alert on a filtered table checks its condition and sends its data per recipient, by that person's scope. Engineering to confirm the effort.

`Alert.recipients` is JSON with three kinds of entry: `{"type": "orguser", "orguser_id": …}`, `{"type": "user_group", …}` or `{"type": "external", "email": …}` ([alert.py:83](../../../../../backend/ddpui/models/alert.py)). Delivery also has a Slack channel.

A scheduled alert runs in a Celery worker (beat → `dispatch_due_alerts` → `evaluate_alert` → `_run_evaluation`), so there is no logged-in user. The alert already stores **who** it is for, so each recipient's scope is resolved from `recipients` at every run (daily, weekly or monthly). A new list, a switch change or a removed user applies from the next run.

**Flow in `_run_evaluation()`** (`ddpui/celeryworkers/alert_tasks.py`):

```
group recipients by scope (user groups expanded to their members first):
  Admin / Analyst orguser  → unrestricted
  Member orguser           → their saved rows
  external email           → no rows (sees nothing from filtered tables)
for each distinct scope:
  compute value with that scope (alert_query → kpi/metric service → fetch_from)
  condition met? → render + deliver to that group only
Slack (if enabled) → evaluated as unrestricted (see Q2)
write one AlertLog per scope evaluated
```

When no recipient is filtered (all Admins/Analysts, or row access is off), this is one group and one query: today's behaviour.

```python
# ddpui/celeryworkers/alert_tasks.py — _run_evaluation
for scope, people in group_recipients_by_scope(alert).items():
    value, sql_str, rag_status = alert_query.compute(alert, org_warehouse, scope)
    eval_input = rag_status if alert.alert_type == AlertType.KPI_RAG else value
    fired = condition_helpers.evaluate(alert.alert_type, cond, eval_input)
    deliveries = []
    if fired:
        tokens = rendering.tokens_for_alert(alert, current_value=value, rag_status=rag_status)
        body = rendering.render(alert.message_template, tokens)
        deliveries = notify_alert_recipients(alert, subject=subject, body=body, recipients=people)  # this group only
    AlertLog.objects.create(..., value=value, scope_label=label_for(people), deliveries=deliveries)
# Slack, if enabled: one evaluation with UNRESTRICTED → deliver_slack (Q2)


# ddpui/core/alerts/recipient_scope.py (new)
def group_recipients_by_scope(alert) -> dict[RowScope, list[dict]]:
    """Recipients grouped by the rows they may see; user groups expanded to their members."""
    groups = defaultdict(list)
    for r in expand_user_groups(alert.recipients, alert.org):
        if r["type"] == "orguser":
            orguser = OrgUser.objects.filter(id=r["orguser_id"], org=alert.org).first()
            if orguser is None:
                continue                                          # left the org → gets nothing
            groups[row_scope.resolve_for_orguser(orguser)].append(r)
        else:
            groups[row_scope.resolve_for_external(alert.org)].append(r)   # external email
    return groups


# ddpui/core/rls/row_scope.py
def resolve_for_external(org) -> RowScope:
    """Scope for someone outside the org (an alert's external email): nothing from filtered tables."""
    if not row_access_on(org):
        return _unrestricted(org.id)
    live = _live_upload(org)
    if live is None:
        return _unrestricted(org.id)                       # row access not set up yet
    return RowScope(org.id, False, tuple(live.scope_columns), ())   # the org's scope columns, no rows
```

| Function                                                                   | Change                                                                                          |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `alert_query.compute(alert, org_warehouse, scope)`                         | New `scope` argument, passed to `compute_metric_value_with_sql`, `compute_latest_value` and `_execute_standalone` (§5.2) |
| `notify_alert_recipients(alert, *, subject, body, recipients=None)`        | Optional `recipients`; defaults to `alert.recipients`, so other callers don't change            |
| `group_recipients_by_scope`, `expand_user_groups`                          | New, in `ddpui/core/alerts/recipient_scope.py`                                                  |
| `row_scope.resolve_for_external(org)`                                      | New: the org's scope columns with no rows, so every filtered table returns nothing and unfiltered tables show as usual. It needs the org's scope columns: with none, every table would look unfiltered |

`RowScope` is a frozen dataclass of tuples, so it can be a dictionary key: two Members with identical rows land in the same group.

**Example:** "Notify when silt removed < 100 tonnes this week." Rahul (Pandharpur, 80 t) gets an alert showing 80 t. Sunita (D-104, 140 t) gets nothing. Priya (Admin, 2,300 t org-wide) gets nothing.

- People with identical rows share one evaluation (fewer warehouse queries).
- An external email gets nothing from a filtered table — it fails closed. Rows are read only by `orguser`, so an external recipient never matches a row, even one still holding their email.
- `AlertLog` stays one row per evaluation. A new nullable `scope_label` column ("unrestricted", or the recipient emails) tells them apart. `alert_snapshot.recipients` records who that evaluation was for.
- KPI-RAG alerts go through `kpi_service`, which uses `AggQueryBuilder`, so they're covered the same way.
- `AlertService.dry_run()` (the "Test" button) runs as the alert's author: unrestricted, since only Admins and Analysts can create alerts once Members are view-only.

### 5.13 When things are added or change (spec §4 journey 6)

| Event                                                                      | Behaviour                                                                                                                                                                                                                            | Code                                                                                                                                         |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| New table with a scope column                                              | Filtered on the next query (live column lookup). It appears in the Row access page's list of filtered tables.                                                                                                                        | The page lists filtered tables live from the schema cache: every table with at least one scope column                                        |
| New chart on a table with no scope column, on a dashboard Members can open | The builder (Admin/Analyst) sees a short, non-blocking note: "Members will see this table in full."                                                                                                                                  | `GET /api/rls/table-status/?schema=&table=` → `{filtered, scope_columns}`; shown in the chart builder and when adding a chart to a dashboard |
| New value in the data (a new dam)                                          | Visible only to people with `*` in that column                                                                                                                                                                                       | Falls out of §5.3                                                                                                                            |
| Scope column renamed or dropped                                            | **Ignored** (team decision). The table is filtered on its remaining scope columns; if none are left, it is shown in full. Whoever renames or drops the column in dbt re-uploads the sheet with the new column name at the same time. | `build_condition` uses only the scope columns the table has now (§5.3). The Row access page shows a standing warning about this (§7.1)       |

**Empty-state message.** When a Member's chart returns no rows **because of** row access, the chart shows "No data for your access, contact your admin" rather than a generic empty chart. The data response carries `row_access: "no_rows"` when the condition was `false()`. Where the condition was a real filter that simply matched nothing, the normal empty state shows.

### 5.14 Public links (decision 1)

**The rule:** Warn, then public viewers see all rows. Only Admins and Analysts can make public links.
**Example:** Priya turns on the public link for "Silt progress". The sharing modal shows: "This dashboard uses filtered tables (silt_daily, dams). Anyone with the link will see **all** rows, not just their own." She confirms; the link works unfiltered.
**Code:** `GET /api/access/{rtype}/{id}` (sharing modal data) adds `uses_filtered_tables: [...]`. The frontend shows the warning before the toggle takes effect. Public routes need no other change: they already pass `UNRESTRICTED`.

### 5.15 API endpoints

Router: `ddpui/api/rls_api.py`, mounted at `/api/rls/`. New permission `can_manage_row_access` (super-admin, Admin, Analyst). All responses use `api_response(...)`.

| Method | Path                                    | What it does                                                                                                                                                                                                              |
| ------ | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/status/`                              | Row access switch (`enabled`). Live upload: `file_name`, scope columns, counts, filtered tables (live, from the schema cache), saved by/at, `review_result`                                                               |
| PUT    | `/enabled/`                             | Turn the row access switch on or off: `{"enabled": true}` (§5.2). Every other endpoint below returns 400 "Turn on row access first" while it is off, except `/me/` and `/table-status/`, which answer `{filtered: false}` |
| GET    | `/template/`                            | CSV download (§5.8)                                                                                                                                                                                                       |
| GET    | `/columns/`                             | Every warehouse table and its columns, from the schema cache, for the column search (§5.8)                                                                                                                                |
| POST   | `/draft/`                               | Upload CSV (multipart) → starts the review task, returns `task_id`; the task result gives the new `upload_id`, or the blocking errors (nothing stored). 409 if the org already has a draft (§5.1 rule 1)                  |
| GET    | `/draft/`                               | Current draft upload: `upload_id`, `file_name`, uploaded by/at, `review_result`                                                                                                                                           |
| DELETE | `/draft/{upload_id}/`                   | Discard: deletes the draft upload and its rows (§5.7). 409 if not current                                                                                                                                                 |
| POST   | `/draft/{upload_id}/previewed/`         | Record that the draft upload has been previewed (§5.6). 409 if not current                                                                                                                                                |
| POST   | `/draft/{upload_id}/save/`              | Commit (§5.7). 409 if not current                                                                                                                                                                                         |
| GET    | `/preview/people/`                      | People on the draft/saved list, for the "Preview as" picker                                                                                                                                                               |
| GET    | `/preview/dashboards/{id}/?orguser_id=` | Can this person open this dashboard?                                                                                                                                                                                      |
| GET    | `/preview/everyone/`                    | "Everyone at once" table                                                                                                                                                                                                  |
| GET    | `/table-status/`                        | Filtered or not, for the chart-builder note                                                                                                                                                                               |
| GET    | `/me/`                                  | For the current Member: `{filtered: bool, scope: {column: values}}` — used to lock dashboard filters                                                                                                                      |

People on the list who aren't in the org yet are invited as Members on Save (§5.7), through the existing `invite_user_to_org`. There is no separate invite endpoint for row access.

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

> **Spec gap to raise:** orgs whose Member floor is **No access** today will suddenly let Members see every non-private dashboard. The spec only says to tell orgs whose floor is _above_ View. Recommendation: tell both groups, and tell No-access orgs to mark sensitive dashboards Private before 3 Dec.

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
2. Move `created_by` to that Admin for Member-owned dashboards, charts, KPIs, reports (`ReportSnapshot`) and alerts. Public ones are included.
3. Give the previous Member owner a **View** grant on each moved item that is private, so nobody loses sight of their own work.
4. Downgrade existing Edit grants to Members to View. Don't delete them.
5. Print a per-org summary. Orgs with Member-owned content but no Admin are listed for manual handling and skipped.

**Public dashboards and reports owned by Members:** move them like any other item, and leave the public link as it is.
**Example:** Rahul (Member) made "Village water survey" public last month. After the command, Priya (Admin) owns it, and the link Rahul sent to the funder still opens.
**Why it's safe:** public routes look up a dashboard or report by `public_share_token` + `is_public` only ([public_api.py:128](../../../../../backend/ddpui/api/public_api.py)). They never check `created_by`. The command doesn't touch `is_public`, `public_share_token`, `public_shared_at` or `public_disabled_at`.
**What changes:** Rahul can no longer turn the link off, because Members can't change sharing (§6.4). Only an Admin or Analyst can. The org email says so.

**Before release:** `--dry-run` produces the list of orgs to email:

- floor above View (Edit), or
- floor No access (see §6.3), or
- Members own content.

The dry-run prints, per org, how many dashboards, charts, KPIs, reports and alerts each Member owns, and **how many of those dashboards and reports are public**. If every count is 0, the command has nothing to move for that org. Run it on production before release to confirm.

Spec §10: orgs are told before it ships. The access docs (`docs/`) are updated in the same release.

**Email text (draft):**

> **Subject:** From 3 December, Members in Dalgo will be view-only
>
> From 3 December, Members can view all dashboards, charts, KPIs and reports in your org, but can't create or edit them. Anything a Member owns today will move to {admin_name}. {n_items} items are affected in {org_name}.
>
> Public links on these items keep working. To turn one off, an Admin or Analyst can do it from the sharing menu.
>
> If someone needs to keep building, make them an Analyst before 3 December (Settings → Access → People). If a dashboard should not be seen by every Member, mark it Private and share it with the right people.
>
> Why: we're adding row-level access so each person sees only their own rows. Letting Members build charts would let them go around it. Since 14 July, Members have created almost no content.

---

## 7. Frontend (webapp)

### 7.1 Row access page

Location: a fourth tab, **Row access**, on Settings → Access (`components/settings/access/AccessPage.tsx`), next to People, Groups and Roles. Shown only with the `ROW_ACCESS` flag and `can_manage_row_access`. Exact layout follows the designs due 16 Nov.

New components in `webapp/components/settings/access/row-access/`:

| Component                  | Shows                                                                                                                                                                                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RowAccessTab.tsx`         | The row access switch (below). Status: saved file name ("atecf_access_nov.csv · Last saved by Abhishek on 20 Nov"), scope columns, people count, filtered tables, latest review, the column-change warning (below). Buttons: Download template, Upload |
| `TemplateDialog.tsx`       | First time only: one search box for columns (shows the tables that have each) and tables (shows their columns); ticked columns go into the template                                                                                                    |
| `UploadReview.tsx`         | The 5-step review (§5.5): What changes → Must fix → People → Worth a look → Preview, then save                                                                                                                                                         |
| `PeopleGroups.tsx`         | Grouped counts, including "will be invited when you save" (check 4) and "invited, not joined yet"                                                                                                                                                      |
| `EveryonePreviewTable.tsx` | "Everyone at once" table (cut first if late)                                                                                                                                                                                                           |

A file with blocking errors shows them and is not saved, so there is no Save button for it. Save stays disabled on first setup until a preview has been opened.

**Row access switch.** At the top of the page: "Row access: On / Off", calling `PUT /api/rls/enabled/` (§5.2).

- It starts **off**. While it is off, the page shows only the switch and "Row access is off. Members see all rows. Turn it on to upload an access list." Template, Upload, review, preview, Save and Discard are hidden.
- Turning it on unlocks the rest of the page. Members are still unfiltered until a list is saved.
- Turning it off asks first: "Members will see all rows on every dashboard until you turn this back on. Your saved list is kept."

While the org has a draft, the Upload button is replaced by "Unsaved upload atecf_access_dec.csv by Abhishek, 10:00" with **Review**, **Save** and **Discard** (§5.1 rule 1). For the person who uploaded it, Discard reads **Discard and upload again**.

**Column-change warning.** Always shown to Admins at the top of the Row access page (static text, no check behind it):

> ⚠ **Keep your access columns stable.** If a column used for row access (for example `district`) is renamed or removed in dbt, Dalgo stops filtering on it, and people may see data that isn't theirs. When you change one of these columns, upload an updated access sheet at the same time.

**Why it matters:** a renamed or dropped scope column is ignored (§5.13), so this warning is the only reminder that a dbt change needs a new sheet.

### 7.2 Preview mode

- "Preview as" picker on the Row access page and on any dashboard (Admins/Analysts only).
- People not joined yet are greyed out in the picker: "hasn't accepted the invite yet, so there's nothing to preview".
- Adds `?previewAs=<orguser_id>&draft=<upload_id>` to the dashboard URL (no `draft` when previewing the saved list). On a 409 "already saved or discarded", the page shows a Reload button. An API client wrapper adds the two headers to every request while those params are present.
- Banner: "Previewing as rahul@mh.gov.in · Unsaved upload · Exit preview" (or "Saved list" when there is no draft).
- If the person can't open the dashboard, show that instead of charts.

### 7.3 Dashboard filters for Members

- On dashboard load, a filtered Member calls `/api/rls/me/`.
- A filter whose column is a scope column:
  - with one value → shown locked ("District: Solapur 🔒")
  - with several → a dropdown of just those values.
- The dropdown values already come back filtered from `/filters/preview/` (§3). The lock is UX only; the server enforces the rule either way.

### 7.4 Other UI

| Where                                             | Change                                                                                                               |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Chart builder / add chart to dashboard            | Non-blocking note when `table-status` says not filtered and row access is on: "Members will see this table in full." |
| Chart empty state                                 | "No data for your access, contact your admin" when `row_access: "no_rows"`                                           |
| Sharing modal                                     | Members: read-only, copy public link only. Admins/Analysts: filtered-tables warning before going public              |
| Nav, list pages, dashboard/chart/KPI/report pages | Hide create/edit/delete for Members (driven by the removed permissions via `lib/rbac.tsx`)                           |
| Roles tab                                         | Member floor shown as "View (fixed)"                                                                                 |

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
| `POST /api/reports/{id}/export/pdf/`                                                                                             | Scope token (§5.11)            | Render calls are scoped to Rahul               |
| Alerts                                                                                                                           | Per-scope evaluation (§5.12)   | Rahul's email holds Pandharpur value only      |
| `warehouse_api` raw routes, `filter_api` schema/table/column lists                                                               | Permission removed             | 403/404 for Members                            |
| Public routes                                                                                                                    | —                              | Unfiltered (decision 1)                        |
| Preview headers sent by a Member                                                                                                 | `for_request` ignores them     | Member still sees only their own rows          |

**Route inventory test.** One test lists every Ninja route whose required permissions a Member holds and compares it with a reviewed allowlist in the test file. A new Member-reachable route fails CI until someone adds it to the list — and to this table.

The two missing access checks (§5.10) exist today without row access, so they ship first, on their own.

---

## 9. Security and performance

**Security**

- Server-side only. The browser never says which rows to show; it can't widen its scope by editing a URL, payload or header.
- Values reach SQL only through SQLAlchemy expressions (`in_()`), never string formatting.
- Preview headers are honoured only for super-admins, Admins and Analysts.
- The PDF scope token is made only for Members, is random, lives in Redis only while the render runs (deleted after, 5-minute TTL as a safety net), is tied to one report and is only accepted together with the existing render secret. A request with a bad token is refused, never served unfiltered (§5.11).
- The access list holds links to org users and scope values. An email is stored only for someone not in the org yet, until they accept. No new kind of PII (personally identifiable information).
- Rows are only read by `orguser`, so a row still holding an email can never filter anyone's data.
- Multi-tenancy: `OrgAccessListUpload` has an `org` FK, rows belong to an upload, and every query filters by `request.orguser.org`.

**Performance targets**

| Step                                 | Target                                                 | How                                                                                 |
| ------------------------------------ | ------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Resolve a Member's scope             | < 5 ms, once per request                               | One indexed query; only when a query touches the warehouse                          |
| Column lookup                        | < 5 ms cached; one inspector call per table per 10 min | Redis                                                                               |
| Added to a chart query               | < 50 ms                                                | `IN` conditions; recommend indexes on scope columns in large tables (handover note) |
| Upload review for ATECF (~18 tables) | < 30 s, in a Celery task with progress                 | One grouped query per filtered table                                                |

---

## 10. Tests (only the important ones)

**Backend unit — `ddpui/tests/core/rls/`**

- `build_condition`: one test per row of the §2.1 ATECF table (Priya, Rahul, Anita, Sunil's two rows, Sunita's integer `dam_id`, new.user's blank, lead's `*`).
- `build_condition`: a row with `*` on all present columns returns no filter even when other rows restrict.
- `build_condition`: a scope column the table lacks is ignored; the other scope columns still filter, and a table with none left is shown in full.
- `build_condition`: table with no scope column → no filter.
- Upload: cleaning (`pune ` → `Pune`), "did you mean", repeated emails allowed, blank vs `*`.
- Upload: an org user is linked by `orguser`; anyone else keeps their `email` and is listed by check 4.
- Save invites each email once after commit: a new person gets an invite, a Dalgo user from another org is added and linked at once, a pending invite is not re-sent.
- Accepting an invite switches that person's rows from `email` to their new `OrgUser` in both draft and live, and another org's rows with the same email are untouched (§5.1 rule 4).
- Upload while a live list exists: Members keep the live rows until Save.
- Upload while the org has a draft → 409 naming its uploader; two uploads at the same moment → one stored, the other 409 (§5.1 rule 1).
- Preview, Save or Discard with an `upload_id` that was already saved or discarded → 409 (§5.1 rule 3); a Save that gets 409 leaves the previous live list in place.
- Save: blocked by errors; blocked before first preview; switches the live upload and deletes the previous one in one transaction.
- Row access switch: while it is off, upload/save/preview endpoints return 400 and preview headers are ignored; with a saved list, Rahul is unrestricted while it is off and filtered once it is on; turning it off keeps the saved list.
- Member cap: creator, user Edit grant and group Edit grant all return View for a Member.

**Backend API — `ddpui/tests/api_tests/`**

- The launch-gate route tests in §8, plus the route inventory test.
- Access-check fixes (§5.10).
- Preview headers: honoured for Analyst, ignored for Member.
- Alerts: per-scope evaluation and delivery; external recipient with no row gets nothing.
- `migrate_member_content --dry-run` and real run on a fixture org.

**Webapp — Playwright `webapp/e2e/row-access.spec.ts`**

- Admin: turn row access on → download template → upload → review → preview Rahul → save.
- Rahul logs in: locked district filter, filtered charts, "view data" and CSV.
- Member sees no create/edit buttons; sharing modal read-only.

---

## 11. Milestones (16 Nov – 2 Dec)

| #   | Dates          | Work                                                                                                                                                                                                                                                   | Done when                                                             |
| --- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| M0  | 16–17 Nov      | Access-check fixes (§5.10), own PR                                                                                                                                                                                                                     | Merged and deployed on their own                                      |
| M1  | 16–19 Nov      | Members view-only backend: permissions + data migration, cap, floor fixed, Edit-share block, `migrate_member_content`                                                                                                                                  | Member gets View everywhere; dry-run list ready for org emails        |
| M2  | 17–20 Nov      | Row access core: models, `ROW_ACCESS` flag, row access switch (`OrgPreferences.row_access_enabled`), row scope (`for_request`, `scope` passed through every service on the data path), `fetch_from` hook, schema cache, fail-closed rules, table guard | Unit tests for §2.1 pass; a Member's `/charts/{id}/data/` is filtered |
| M3  | 20–25 Nov      | Upload, review checks, draft, save, template, preview endpoints, everyone-at-once                                                                                                                                                                      | ATECF's sample CSV gives the expected review                          |
| M4  | 23–27 Nov      | Webapp: Row access tab, review flow, preview mode, locked filters, empty state, chart-builder note, Member UI hiding, sharing modal, Roles tab                                                                                                         | E2E happy path passes                                                 |
| M5  | 25–30 Nov      | Reports PDF scope token, alerts per scope, public-link warning                                                                                                                                                                                         | Launch-gate rows for reports and alerts pass                          |
| M6  | 30 Nov – 2 Dec | Full launch-gate suite, route inventory test, performance check on ATECF-sized data, docs                                                                                                                                                              | All §8 tests green                                                    |
| —   | 3 Dec          | Flagged release: Bhumi, then ATECF. Members view-only for all orgs (after the notice email)                                                                                                                                                            |                                                                       |

**Cut order if late:** (1) "everyone at once" table, (2) "did you mean" suggestions. Nothing else.

**Funding (spec §10):** Bhumi 20–25 contract hours; ATECF from its contract hours; access-check fixes and Members view-only not billed; anything beyond the funded hours is roadmap investment.

---

## 12. Success measures (spec §11)

| Measure                                                  | Target               | How measured                                                      |
| -------------------------------------------------------- | -------------------- | ----------------------------------------------------------------- |
| Rows seen outside a person's scope                       | 0                    | Launch-gate tests per route + preview checks during ATECF testing |
| ATECF's Admin updates the list without consulting's help | Yes, after handover  | Observed; support tickets                                         |
| Weekly active Members at ATECF and Bhumi                 | Targets to set       | PostHog                                                           |
| Orgs using row access                                    | 3 by end of Feb 2027 | org has a live upload                                             |

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
- A scope column renamed or dropped in dbt without re-uploading the sheet with the new name: Members then see that column unfiltered.
- Report summary text. It is written by hand, not queried, so it is shown in full to everyone who can open the report, on screen and in the PDF. **Example:** Priya writes "Solapur removed 2,300 t, Beed 1,200 t" in the summary; Rahul (Pandharpur only) sees both numbers above his filtered charts. Keep summaries free of numbers from other scopes, or make the report private to the people who may see them.

Also: add indexes on scope columns in large tables; keep external users as Members; when someone leaves, remove them from Dalgo (their rows are removed with them).

---

## 14. Decisions (spec §9)

| #   | Decision                                        | Outcome                                                                                                                                       |
| --- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Public link on a dashboard with filtered tables | Warn, then public viewers see all rows. Only Admins and Analysts can make public links.                                                       |
| 2   | Bulk invite by CSV                              | Phase 2 for Settings → Access → People. In v1, people on the access list who aren't in the org yet are invited when the list is saved (§5.7). |
| 3   | Warehouse table as the source                   | Phase 2, refreshed only with "Sync now".                                                                                                      |
| 4   | Hand-written rules                              | Cut.                                                                                                                                          |
| 5   | Groups on the access list                       | Cut from v1; phase 2 if needed.                                                                                                               |
| 6   | Members view-only across Dalgo                  | Decided. Floor fixed at View; content moves to an Admin.                                                                                      |

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
