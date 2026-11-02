# Notification Categorization — Research

## What this file covers

Net-new findings for the notification categorization (v1). Does not duplicate anything
already in `landmarks.md` (which does not exist yet for this codebase).

---

## 1. Notification model — current state

**File:** `backend/ddpui/models/notifications.py`

| Field | Type | Notes |
|-------|------|-------|
| `author` | EmailField | Sender email |
| `message` | TextField | Full message body (stored with `\n` newlines) |
| `email_subject` | TextField | Email subject line |
| `timestamp` | DateTimeField | Auto-set on create |
| `urgent` | BooleanField | Default False |
| `scheduled_time` | DateTimeField | Nullable — for future sends |
| `sent_time` | DateTimeField | Nullable — set after delivery |
| `target_org_ids` | JSONField | Nullable — used for admin broadcast targeting |
| `send_in_app` | BooleanField | Controls whether it appears in the tab |
| `send_email` | BooleanField | Controls email delivery |

`NotificationRecipient` links `Notification` → `OrgUser` (FK, CASCADE both).
Carries `read_status` (BooleanField) and `task_id` (Celery task for scheduled sends).

**Key finding:** No `notification_type` field exists today. All notifications are
treated identically in the model, API, and frontend.

---

## 2. Trigger files — what each one creates

### In-app notifications (appear in the tab)

These triggers call `create_notification()` with `send_in_app=True`.

| File | Function(s) | Event | Proposed type |
|------|-------------|-------|---------------|
| `triggers/share.py` | `notify_share_recipients` | New grant or access upgrade to a dashboard/report | `sharing` |
| `triggers/share.py` | `notify_row_level_change` | Single grant row upgraded or downgraded | `sharing` |
| `triggers/report_share.py` | `notify_report_shared` | Report PDF shared with you | `sharing` |
| `triggers/access.py` | `notify_owner_of_new_request` | Someone requests access to your resource | `access` |
| `triggers/access.py` | `notify_requester_of_response` | Your access request approved or declined | `access` |
| `triggers/mention.py` | `notify_mentioned` | @-mention in a comment on a report/KPI | `mention` |
| `triggers/schema_change.py` | `notify_schema_change` | Airbyte detects breaking or non-breaking schema change | `schema_change` |
| `core/notifications/delivery.py` | `notify_org_managers` | Pipeline run failure — sent to org managers | `pipeline` |
| Admin broadcast API (`/api/v1/admin/notifications`) | — | Maintenance, downtime, RCA, feature news | `announcement` |

### Email-only (no Notification model record — no type needed)

| File | Functions | Delivery path |
|------|-----------|---------------|
| `triggers/trial.py` | All `send_*` functions | SES email only |
| `triggers/user.py` | `send_password_reset`, `send_signup`, `send_invite_user`, `send_added_to_org` | SES email only |
| `triggers/alert.py` | `notify_alert_recipients` | SES email only (no Notification row created) |
| `triggers/biz_dev.py` | `send_notification` | Internal SES email only |

---

## 3. Service layer entry point

**File:** `backend/ddpui/core/notifications/notifications_functions.py`

`create_notification(data: NotificationDataSchema)` at line ~143 is the single
entry point for creating all Notification rows. Every trigger goes through it.

`NotificationDataSchema` (in `schemas/notifications_api_schemas.py`) is the shape
passed into `create_notification`. We add `notification_type` here — triggers pass
it in; the function stores it on the model.

`fetch_user_notifications_v1()` at line ~321 drives the `GET /api/notifications/v1`
endpoint. It currently filters by `send_in_app=True` and optional `read_status`.
We extend it with optional `notification_type` and `exclude_type` params.

---

## 4. API — current shapes

**Endpoint:** `GET /api/notifications/v1`
**Params today:** `page`, `limit`, `read_status` (optional)
**Response today:** `{ total_notifications: int, res: [{ id, urgent, author, message, read_status, timestamp }] }`

`notification_type` is absent from both the filter and the response.

**Admin broadcast endpoint:** `POST /api/v1/admin/notifications`
Handled in `api/` (admin namespace). This is what the `BroadcastComposer` UI calls.
The handler creates notifications with `target_org_ids` for multi-org broadcast.
This must be updated to auto-set `notification_type = "announcement"`.

---

## 5. Message formatting root cause

**File:** `webapp/lib/notificationMessage.tsx`

`renderMessageWithLinks(message)` linkifies URLs in the message string but returns
inline content — it does not split on `\n`.

The message is stored in the database with real newline characters (`\n`). When
the frontend renders it inside a standard `<div>` or `<p>`, browsers collapse all
whitespace (including `\n`) into a single space. This is why a structured
multi-paragraph announcement appears as one wall of text.

**Fix:** Wrap the message container with `whitespace-pre-wrap` Tailwind class
(equivalent to CSS `white-space: pre-wrap`). This preserves newlines without
needing to split the string. The existing `renderMessageWithLinks` call still runs
inside — order matters: linkify first, then set `white-space: pre-wrap` on the
container so both line breaks and links work.

---

## 6. Frontend notification page — current structure

| File | Role |
|------|------|
| `webapp/app/notifications/page.tsx` | Top-level page — tabs (All / Read / Unread), action buttons |
| `webapp/components/notifications/NotificationsList.tsx` | Paginated table, checkbox selection |
| `webapp/components/notifications/NotificationRow.tsx` | Single row: message truncated to 300 chars, expand/collapse |
| `webapp/components/notifications/NotificationPreferencesDialog.tsx` | Email + schema-change toggles |
| `webapp/components/notifications/TablePagination.tsx` | Page size + navigation |
| `webapp/hooks/api/useNotifications.ts` | SWR hooks for notifications, unread count, actions |
| `webapp/lib/notificationMessage.tsx` | `renderMessageWithLinks()` |
| `webapp/constants/notifications.ts` | `MESSAGE_TRUNCATE_LENGTH = 300`, tab options, page sizes |
| `webapp/types/notifications.ts` | `Notification`, `NotificationsResponse`, `NotificationFilters` |

The top-level tabs today are All / Read / Unread. There is no type-based split.

---

## 7. Unread count

`GET /api/notifications/unread_count` counts all unread `send_in_app=True`
notifications for the logged-in OrgUser. In v1, keep this counting everything
(notifications + announcements) — the bell badge in `components/header.tsx` shows
the total.

---

## 8. UserPreferences

**File:** `backend/ddpui/models/userpreferences.py`

`enable_schema_change_notifications` (Boolean) already exists. The
`NotificationPreferencesDialog` in the frontend surfaces this toggle (admin-only).
No changes needed here for v1.
