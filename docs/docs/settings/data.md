---
sidebar_position: 4
---

# Data

**Settings → Data is where you configure your warehouse and manage connection behaviour across every sync.**

Two tabs:

| Tab | What it covers |
|---|---|
| **Warehouse** | Set up or update the database all synced data is stored in |
| **Connections** | Org-wide behaviour that applies to every Airbyte connection |

## Warehouse tab

Your warehouse is the single database where data from all your sources lands after syncing. You need one before you can sync anything — so this is usually the first thing you set up.

Select the **Warehouse** tab to view the current warehouse, set one up for the first time, or edit its connection details.

→ [Full warehouse setup guide](./warehouse.md)

## Connections tab

### Auto-accept non-breaking schema changes

When a source adds a new column or a new stream, Dalgo will apply the change automatically instead of queuing it for manual review.

Toggle **Auto-accept non-breaking schema changes** on to enable this for your organisation.

Breaking changes — removed columns, renamed tables — always require manual review regardless of this setting.

---

**Related:** [Ingest](../data/ingest/index.md) · [Access](./access.md) · [Branding](./branding.md)
