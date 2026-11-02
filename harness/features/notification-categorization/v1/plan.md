# Notification Categorization — Implementation Plan v1

**Spec:** no formal spec — feature described in conversation (2026-10-16)
**Research:** `harness/features/notification-categorization/v1/research.md`
**Services affected:** `backend/` (Django), `webapp/` (Next.js)

---

## 1. Overview

The notifications tab is hard to use because every notification looks the same —
no tag tells you whether it is a pipeline failure or an access request — and long
messages like maintenance announcements appear as a wall of text (all newlines
collapsed).

This plan adds category tags to every notification, fixes message formatting, and
splits the notifications page into two top-level tabs: **Notifications** (personal
events) and **Announcements** (platform broadcasts).

---

## 2. Blast Radius

Every surface below was confirmed in conversation with the user on 2026-10-16.

| Surface | Hop | Why affected | Status |
|---------|-----|--------------|--------|
| `Notification` model | primary | New `notification_type` field | In scope |
| 6 trigger files (`share`, `access`, `report_share`, `mention`, `schema_change`, `delivery`) | 1-hop | Must pass `notification_type` on create | In scope |
| Admin broadcast API (`/api/v1/admin/notifications`) | 1-hop | Must auto-set `notification_type=announcement` | In scope |
| `NotificationDataSchema` | 1-hop | Carries `notification_type` from caller to model | In scope |
| `GET /api/notifications/v1` endpoint | 1-hop | Returns `notification_type`; supports type filter | In scope |
| Frontend `NotificationRow` | 1-hop | Renders tag badge; fixes message line-break display | In scope |
| Frontend `notifications/page.tsx` | 1-hop | Adds top-level Notifications / Announcements tabs and tag filter chips | In scope |
| Frontend `useNotifications` hook | 1-hop | Adds `notification_type` and `exclude_announcements` params | In scope |
| Unread count (`/api/notifications/unread_count`) | 1-hop | Keeps counting all types (no change needed in v1) | In scope — no change |
| Admin portal notification history (`/admin/notifications`) | 1-hop | Could show tags in broadcast history | Deferred to v2 |
| `NotificationPreferencesDialog` | 1-hop | Email / schema-change toggles | Out of scope — no change |

**Not affected:**
- `ReportSnapshot`, `Dashboard`, `Alert`, `KPI`, `Metric` — no link to the `Notification` entity in the domain map.
- `triggers/trial.py`, `triggers/user.py`, `triggers/alert.py`, `triggers/biz_dev.py` — email-only; no `Notification` row created by these triggers, so no type field to set.

---

## 3. High-Level Design (HLD)

### Tag flow — personal notification (e.g. pipeline failure)

```
Pipeline fails
      │
      ▼  delivery.notify_org_managers()
      │  passes notification_type = "pipeline"
      │
      ▼  create_notification(NotificationDataSchema(..., notification_type="pipeline"))
      │  Notification row saved with notification_type="pipeline"
      │
      ▼  GET /api/notifications/v1?exclude_announcements=true
      │  Returns { ..., notification_type: "pipeline" }
      │
      ▼  Notifications tab → NotificationRow → [Pipeline] badge
```

### Tag flow — admin broadcast (announcement)

```
Admin fills BroadcastComposer → POST /api/v1/admin/notifications
      │
      ▼  API handler auto-sets notification_type = "announcement"
      │  create_notification(NotificationDataSchema(..., notification_type="announcement"))
      │
      ▼  GET /api/notifications/v1?notification_type=announcement
      │  Returns { ..., notification_type: "announcement" }
      │
      ▼  Announcements tab → AnnouncementCard (full formatted message, no truncation)
```

### Page structure — before vs after

```
BEFORE                           AFTER
──────────────────────────       ─────────────────────────────────────────
[ All ] [ Read ] [ Unread ]      [ Notifications ]  [ Announcements ]
                                       │                    │
  NotificationRow (no tag,            ▼                    ▼
  collapsed wall of text)       [ All ] [ Read ] [ Unread ]
                                 Tag chips:            Full formatted cards
                                 [All][Pipeline]       (no truncation,
                                 [Sharing][Access]      whitespace preserved,
                                 [Mention][Schema]      links clickable)
                                 NotificationRow
                                 (tag badge, formatted)
```

---

## 4. Low-Level Design (LLD)

### 4.1 Data model

**File:** `backend/ddpui/models/notifications.py`

Add a `NotificationType` choices class and a new field on `Notification`.

```python
class NotificationType(models.TextChoices):
    SHARING       = "sharing",       "Sharing"
    ACCESS        = "access",        "Access"
    MENTION       = "mention",       "Mention"
    SCHEMA_CHANGE = "schema_change", "Schema Change"
    PIPELINE      = "pipeline",      "Pipeline"
    ANNOUNCEMENT  = "announcement",  "Announcement"

class Notification(models.Model):
    # ... existing fields unchanged ...
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        null=True,
        blank=True,
    )
```

**Why nullable:** Existing rows have no type. Nullable lets the migration run
without a default value and without touching historical rows. New rows always
receive a type from the trigger or API.

**Migration:** auto-generated via `python manage.py makemigrations`.

---

### 4.2 Schema update

**File:** `backend/ddpui/schemas/notifications_api_schemas.py`

Add `notification_type` to `NotificationDataSchema` (the shape that flows from
every trigger into `create_notification`).

```python
from ddpui.models.notifications import NotificationType

class NotificationDataSchema(Schema):
    # ... existing fields ...
    notification_type: Optional[str] = None
```

Also add to `CreateNotificationPayloadSchema` (used by the POST `/api/notifications/`
endpoint) in case callers want to set it manually.

---

### 4.3 Service layer

**File:** `backend/ddpui/core/notifications/notifications_functions.py`

`create_notification()` — store `notification_type` on the `Notification` row:

```python
notification = Notification.objects.create(
    ...
    notification_type=data.notification_type,
)
```

`fetch_user_notifications_v1()` — add two optional filter params:

```python
def fetch_user_notifications_v1(
    orguser,
    page: int,
    limit: int,
    read_status=None,
    notification_type: Optional[str] = None,
    exclude_announcements: bool = False,
):
```

Filter logic:
```python
qs = NotificationRecipient.objects.filter(recipient=orguser, notification__send_in_app=True)
if read_status is not None:
    qs = qs.filter(read_status=read_status)
if notification_type:
    qs = qs.filter(notification__notification_type=notification_type)
if exclude_announcements:
    qs = qs.exclude(notification__notification_type=NotificationType.ANNOUNCEMENT)
```

---

### 4.4 API endpoint update

**File:** `backend/ddpui/api/notifications_api.py`

`GET /api/notifications/v1` — add two optional query params:

```python
@router.get("/v1")
def get_notifications_v1(
    request,
    page: int = 1,
    limit: int = 10,
    read_status: Optional[int] = None,
    notification_type: Optional[str] = None,
    exclude_announcements: bool = False,
):
```

Pass both new params down to `fetch_user_notifications_v1()`.

**Response** — update the per-notification shape to include `notification_type`:

```python
{
  "total_notifications": 42,
  "res": [
    {
      "id": 1,
      "author": "priya@ngo.org",
      "message": "...",
      "read_status": false,
      "timestamp": "2026-10-16T14:30:00Z",
      "urgent": false,
      "notification_type": "pipeline"   # NEW
    }
  ]
}
```

**Admin broadcast API** — `POST /api/v1/admin/notifications` handler
(in the admin namespace, exact file TBD from search during execution):
Add `notification_type = NotificationType.ANNOUNCEMENT` to the
`NotificationDataSchema` before calling `create_notification()`. No UI change
needed — all admin broadcasts are announcements by definition.

---

### 4.5 Trigger files — type assignments

Each trigger passes `notification_type` when constructing `NotificationDataSchema`.

| File | Function | Value to pass |
|------|----------|---------------|
| `triggers/share.py` | `notify_share_recipients`, `notify_row_level_change` | `NotificationType.SHARING` |
| `triggers/report_share.py` | `notify_report_shared` | `NotificationType.SHARING` |
| `triggers/access.py` | `notify_owner_of_new_request`, `notify_requester_of_response` | `NotificationType.ACCESS` |
| `triggers/mention.py` | `notify_mentioned` | `NotificationType.MENTION` |
| `triggers/schema_change.py` | `notify_schema_change` | `NotificationType.SCHEMA_CHANGE` |
| `core/notifications/delivery.py` | `notify_org_managers` | `NotificationType.PIPELINE` |

---

### 4.6 Frontend — types and constants

**File:** `webapp/types/notifications.ts`

```typescript
export type NotificationType =
  | "sharing"
  | "access"
  | "mention"
  | "schema_change"
  | "pipeline"
  | "announcement";

export interface Notification {
  id: number;
  urgent: boolean;
  author: string;
  message: string;
  read_status: boolean;
  timestamp: string;
  notification_type: NotificationType | null;  // nullable for old rows
}

export interface NotificationFilters {
  limit: number;
  page: number;
  read_status?: ReadStatus;
  notification_type?: NotificationType;
  exclude_announcements?: boolean;
}
```

**File:** `webapp/constants/notifications.ts`

```typescript
export const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  sharing:       "Sharing",
  access:        "Access",
  mention:       "Mention",
  schema_change: "Schema Change",
  pipeline:      "Pipeline",
  announcement:  "Announcement",
};

export const NOTIFICATION_TYPE_COLORS: Record<NotificationType, string> = {
  sharing:       "bg-blue-100 text-blue-700",
  access:        "bg-purple-100 text-purple-700",
  mention:       "bg-teal-100 text-teal-700",
  schema_change: "bg-yellow-100 text-yellow-700",
  pipeline:      "bg-orange-100 text-orange-700",
  announcement:  "bg-green-100 text-green-700",
};

export const PERSONAL_NOTIFICATION_TYPES: NotificationType[] = [
  "pipeline", "sharing", "access", "mention", "schema_change",
];
```

---

### 4.7 Frontend — message formatting fix

**File:** `webapp/components/notifications/NotificationRow.tsx`

The message container currently renders content inline. Add `whitespace-pre-wrap`
so newlines in the stored message are preserved on screen.

```tsx
<div className="whitespace-pre-wrap text-sm text-gray-700">
  {renderMessageWithLinks(displayMessage)}
</div>
```

**The rule:** `whitespace-pre-wrap` tells the browser to treat `\n` as a visible
line break instead of collapsing it to a space.
**Example:** Priya receives a maintenance announcement. Before the fix, all
numbered points run together in one line. After the fix, she sees the list exactly
as the admin typed it.
**Why it matters:** The message is already stored correctly in the database — this
is a one-line CSS fix.

For the `AnnouncementCard` (new component, see §4.9), apply the same class with no
truncation — show the full message.

---

### 4.8 Frontend — tag badge component

New small component: `webapp/components/notifications/NotificationTypeBadge.tsx`

```tsx
import { NOTIFICATION_TYPE_LABELS, NOTIFICATION_TYPE_COLORS } from "@/constants/notifications";

export function NotificationTypeBadge({ type }: { type: NotificationType | null }) {
  if (!type) return null;
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${NOTIFICATION_TYPE_COLORS[type]}`}>
      {NOTIFICATION_TYPE_LABELS[type]}
    </span>
  );
}
```

Use this in both `NotificationRow` and `AnnouncementCard`.

---

### 4.9 Frontend — page restructure

**File:** `webapp/app/notifications/page.tsx`

Replace the current single-tab structure with two top-level tabs.

```
[ Notifications ]  [ Announcements ]
       │                   │
       ▼                   ▼
  existing list        AnnouncementsTab
  + tag filter chips   (new component)
```

**Notifications tab** adds a tag filter chip row above the list:

```tsx
const TAG_FILTERS = [
  { label: "All",          value: undefined },
  { label: "Pipeline",     value: "pipeline" },
  { label: "Sharing",      value: "sharing" },
  { label: "Access",       value: "access" },
  { label: "Mention",      value: "mention" },
  { label: "Schema Change",value: "schema_change" },
];
```

Active chip state is local React state. On change, the `useNotifications` hook is
called with the selected `notification_type` and `exclude_announcements: true`.

**Announcements tab** (`webapp/components/notifications/AnnouncementsTab.tsx`):
- Calls `useNotifications({ notification_type: "announcement", ... })`
- Renders `AnnouncementCard` per item (no table, no checkboxes)
- Supports mark-as-read per card + mark-all-as-read button

---

### 4.10 Frontend — AnnouncementCard component

New file: `webapp/components/notifications/AnnouncementCard.tsx`

```
┌─────────────────────────────────────────────────────────┐
│  [Announcement]  ·  priya@dalgo.org  ·  3 hours ago     │
│  ─────────────────────────────────────────────────────  │
│  We will be performing scheduled infrastructure          │
│  upgrades tonight. During this window, Dalgo may be     │
│  intermittently unavailable.                            │
│                                                         │
│  What to expect:                                        │
│  1. Dalgo platform — may be down...                     │
│  2. Superset dashboards — unaffected...                 │
│                                                         │
│                              [Mark as read]  ●unread    │
└─────────────────────────────────────────────────────────┘
```

- Full message, no truncation
- `whitespace-pre-wrap` on the message container
- `renderMessageWithLinks` for clickable URLs
- `NotificationTypeBadge` in the header
- Read/unread dot indicator

---

### 4.11 Frontend — API hook update

**File:** `webapp/hooks/api/useNotifications.ts`

Update `useNotifications(filters)` to pass `notification_type` and
`exclude_announcements` to `buildQueryString()`.

Update `buildQueryString()` in `webapp/lib/notifications.ts`:

```typescript
export function buildQueryString(filters: NotificationFilters): string {
  const params = new URLSearchParams();
  params.set("page", String(filters.page));
  params.set("limit", String(filters.limit));
  if (filters.read_status !== undefined) params.set("read_status", String(filters.read_status));
  if (filters.notification_type)         params.set("notification_type", filters.notification_type);
  if (filters.exclude_announcements)     params.set("exclude_announcements", "true");
  return params.toString();
}
```

---

## 5. Security Review

| Area | Assessment |
|------|-----------|
| Authentication | `/api/notifications/v1` is already behind auth middleware. The new query params (`notification_type`, `exclude_announcements`) are read-only filters — no new risk. |
| Data access | `fetch_user_notifications_v1` already scopes to `recipient=orguser` — users only see their own notifications. The type filter does not broaden this. |
| Input validation | `notification_type` is an optional string query param. Add an explicit allowlist check in the API handler: reject any value not in `NotificationType.values`. |
| Injection | No raw SQL. All filtering is via Django ORM `.filter()` calls — safe. |
| Admin broadcast | The admin endpoint already requires platform-admin auth. Auto-setting `notification_type=announcement` in the handler adds no new surface. |
| PII | No PII change. Notifications already contain email addresses of senders. |

---

## 6. Testing Strategy

### Unit tests (backend)

**File:** `backend/ddpui/tests/core/notifications/test_notifications_functions.py`
(or create if it doesn't exist)

| Test | What to verify |
|------|----------------|
| `test_create_notification_stores_type` | `create_notification()` with `notification_type="pipeline"` → DB row has `notification_type="pipeline"` |
| `test_fetch_filters_by_type` | `fetch_user_notifications_v1(..., notification_type="pipeline")` returns only pipeline rows |
| `test_fetch_excludes_announcements` | `fetch_user_notifications_v1(..., exclude_announcements=True)` excludes rows with `notification_type="announcement"` |
| `test_fetch_null_type_not_excluded` | Old rows (null `notification_type`) still appear when `exclude_announcements=True` |
| `test_invalid_type_rejected` | `GET /api/notifications/v1?notification_type=garbage` returns 422 |

### Unit tests (frontend)

- `NotificationTypeBadge` renders correct label and colour class for each type
- `renderMessageWithLinks` with a multi-line string: output contains the original `\n` (so `whitespace-pre-wrap` can render it)

### Integration / manual testing

| Scenario | Steps | Expected result |
|----------|-------|----------------|
| Pipeline failure notification | Trigger a pipeline failure → open Notifications tab | Row shows [Pipeline] badge, orange |
| Admin broadcast | Admin sends a broadcast → open Announcements tab | Full formatted message displayed with line breaks and clickable Discord link |
| Tag filter | Open Notifications tab → click [Sharing] chip | Only sharing notifications shown |
| Old notifications | Notifications created before this deploy | Appear in Notifications tab, no badge (null type) |
| Mark as read | Click [Mark as read] on an announcement card | Card dims, unread count in header decreases |

---

## 7. Milestones

### Milestone 1 — Backend: model + triggers + API

**Deliverable:** Every new notification is stored with a `notification_type`. The
`GET /api/notifications/v1` endpoint accepts type filters and returns the type in
its response. Old rows are unaffected (null type).

**Services:** `backend/`

**Key tasks:**
- [ ] Add `NotificationType` choices and `notification_type` field to `Notification` model
- [ ] Generate and run migration
- [ ] Add `notification_type: Optional[str]` to `NotificationDataSchema`
- [ ] Update `create_notification()` to store `notification_type`
- [ ] Update `fetch_user_notifications_v1()` to filter by `notification_type` / `exclude_announcements`
- [ ] Update `GET /api/notifications/v1` endpoint: new query params + validate against allowlist + include `notification_type` in response
- [ ] Update all 6 trigger files to pass the correct type (see §4.5)
- [ ] Update admin broadcast API handler to auto-set `notification_type = "announcement"`

**Acceptance criteria:**
- POST a notification via `share.py` trigger → `Notification.notification_type == "sharing"` in DB
- `GET /api/notifications/v1` response includes `notification_type` field
- `GET /api/notifications/v1?notification_type=pipeline` returns only pipeline rows
- `GET /api/notifications/v1?exclude_announcements=true` excludes announcement rows
- `GET /api/notifications/v1?notification_type=garbage` returns 422

---

### Milestone 2 — Frontend: tag badges + message formatting fix

**Deliverable:** Every notification row shows a coloured tag chip. Long messages
display with preserved line breaks and clickable links. The fix applies to all
notifications including announcements.

**Services:** `webapp/`

**Key tasks:**
- [ ] Add `notification_type: NotificationType | null` to `Notification` TypeScript type
- [ ] Add `NotificationType` type, `NOTIFICATION_TYPE_LABELS`, `NOTIFICATION_TYPE_COLORS` constants
- [ ] Create `NotificationTypeBadge` component
- [ ] Update `NotificationRow` to render `NotificationTypeBadge`
- [ ] Add `whitespace-pre-wrap` to the message container in `NotificationRow`
- [ ] Update `NotificationFilters` type and `buildQueryString()` to support new params
- [ ] Update `useNotifications` hook to pass new filter params

**Acceptance criteria:**
- A pipeline notification shows an orange [Pipeline] chip
- A sharing notification shows a blue [Sharing] chip
- Old notifications (null type) show no chip — row still renders cleanly
- A multi-paragraph announcement message displays with line breaks in the row
- A URL in a message is a clickable link

---

### Milestone 3 — Frontend: tag filter chips in Notifications tab

**Deliverable:** A chip row appears above the notification list. Clicking a chip
filters the list to that type. The Notifications tab always excludes announcements.

**Services:** `webapp/`

**Key tasks:**
- [ ] Add tag filter chip row to `notifications/page.tsx` (chips: All, Pipeline, Sharing, Access, Mention, Schema Change)
- [ ] Manage active chip in local React state
- [ ] Pass `exclude_announcements: true` and `notification_type: activeChip` to `useNotifications`
- [ ] Reset to page 1 when chip changes
- [ ] Active chip visual: filled vs outline style

**Acceptance criteria:**
- Clicking [Pipeline] shows only pipeline notifications
- Clicking [All] shows all personal notifications (still excludes announcements)
- Switching chip resets to page 1

---

### Milestone 4 — Frontend: Announcements tab

**Deliverable:** The notifications page has two top-level tabs. The Announcements
tab shows admin broadcast messages as full formatted cards.

**Services:** `webapp/`

**Key tasks:**
- [ ] Restructure `notifications/page.tsx` to have top-level tabs: Notifications | Announcements
- [ ] Create `AnnouncementsTab` component
- [ ] Create `AnnouncementCard` component (full message, `whitespace-pre-wrap`, `NotificationTypeBadge`, mark-as-read button)
- [ ] Wire `AnnouncementsTab` to `useNotifications({ notification_type: "announcement", ... })`
- [ ] Add mark-all-as-read button scoped to announcements
- [ ] Unread count badge on "Announcements" tab label (shows count of unread announcements)

**Acceptance criteria:**
- Admin sends a broadcast → it appears in the Announcements tab, not in the Notifications tab
- Full maintenance notice message shows with numbered lists and line breaks preserved
- Discord link in the message is clickable
- Marking an announcement as read removes the unread dot on that card
- Mark All as Read on announcements tab does not affect the Notifications tab

---

## 8. Open Questions & Risks

| Item | Detail |
|------|--------|
| Null-type old notifications | Old rows have `notification_type = null`. They show no badge. They appear in the Notifications tab (not excluded by `exclude_announcements`). If this is wrong, add a backfill migration. |
| Admin broadcast API file location | The exact file for `POST /api/v1/admin/notifications` was not read during planning. Find it during Milestone 1 execution. |
| `notify_org_managers` in `delivery.py` | Confirm this function calls `create_notification()` (not a direct DB write). If it does not, wire through `create_notification` first. |
| Unread badge split | Currently one bell badge for all unread. If the team wants separate counts for Notifications vs Announcements in the header, that is a v2 change. |
| Mobile / slow connection | `AnnouncementCard` renders the full message without pagination. If announcements are ever very long, add a "Show more" toggle in v2. |
