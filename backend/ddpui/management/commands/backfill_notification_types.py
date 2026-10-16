"""
Management command to backfill notification_type on existing notifications
that were created before the notification_type field was added.

Regex patterns are derived from the message templates in:
  - ddpui/core/notifications/triggers/share.py
  - ddpui/core/notifications/triggers/access.py
  - ddpui/core/notifications/triggers/mention.py
  - ddpui/core/notifications/triggers/schema_change.py (messages caller-defined)
  - ddpui/core/notifications/delivery.py (pipeline failures)
  - ddpui/core/admin/admin_service.py (announcements via target_org_ids)

Run with --dry-run first to preview counts before committing.
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from ddpui.models.notifications import Notification
from ddpui.schemas.notifications_api_schemas import NotificationType


# (pattern, type) pairs — evaluated in order, first match wins
PATTERNS = [
    # MENTION — "{email} mentioned you in a comment on ..."
    (
        re.compile(r"mentioned you in a comment on", re.IGNORECASE),
        NotificationType.MENTION,
    ),
    # SHARING — share.py and report_share.py messages
    (
        re.compile(
            r"(shared .+ with you at .+ access"
            r"|upgraded your access on"
            r"|downgraded your access on"
            r"|shared report '.+' with you)",
            re.IGNORECASE,
        ),
        NotificationType.SHARING,
    ),
    # ACCESS — access.py request / response messages
    (
        re.compile(
            r"(has requested to .+ your"
            r"|approved your request for"
            r"|declined your request for)",
            re.IGNORECASE,
        ),
        NotificationType.ACCESS,
    ),
    # PIPELINE — delivery.py notify_org_managers (pipeline failure alerts).
    # "A job has failed" comes from webhook_functions._build_failure_message_for_org_users
    # when no pipeline/task name is available — it doesn't contain "pipeline" or "prefect",
    # so it needs its own pattern branch.
    (
        re.compile(
            r"(Pipeline Failure" r"|pipeline.*fail" r"|a job has failed" r"|flow.?run" r"|prefect)",
            re.IGNORECASE,
        ),
        NotificationType.PIPELINE,
    ),
    # SCHEMA_CHANGE — celery task messages vary; catch common keywords
    (
        re.compile(
            r"(schema.?change"
            r"|breaking change"
            r"|new column"
            r"|column removed"
            r"|column renamed"
            r"|airbyte.*schema"
            r"|schema.*airbyte)",
            re.IGNORECASE,
        ),
        NotificationType.SCHEMA_CHANGE,
    ),
]


class Command(BaseCommand):
    help = "Backfill notification_type on notifications that have notification_type=NULL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be updated without writing to the database",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of notifications to process per batch (default: 500)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written\n"))

        qs = Notification.objects.filter(notification_type__isnull=True).order_by("id")
        total = qs.count()
        self.stdout.write(f"Found {total} notifications with notification_type=NULL\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        counts: dict[str, int] = {t.value: 0 for t in NotificationType}
        counts["unmatched"] = 0

        # Snapshot all IDs upfront so pagination isn't thrown off as rows get updated
        all_ids = list(qs.values_list("id", flat=True))
        updated_total = 0

        for batch_start in range(0, len(all_ids), batch_size):
            batch_ids = all_ids[batch_start : batch_start + batch_size]
            batch = list(Notification.objects.filter(id__in=batch_ids))
            to_update = []

            for notif in batch:
                matched_type = None
                for pattern, ntype in PATTERNS:
                    if pattern.search(notif.message):
                        matched_type = ntype
                        break

                if matched_type is None:
                    counts["unmatched"] += 1
                    continue

                counts[matched_type.value] += 1
                notif.notification_type = matched_type.value
                to_update.append(notif)

            if not dry_run and to_update:
                with transaction.atomic():
                    Notification.objects.bulk_update(to_update, ["notification_type"])

            updated_total += len(to_update)
            processed = min(batch_start + batch_size, total)
            self.stdout.write(f"  processed {processed}/{total}...", ending="\r")

        self.stdout.write("")  # newline after \r progress

        self.stdout.write("\nResults:")
        for type_value, count in counts.items():
            if type_value == "unmatched":
                style = self.style.WARNING
            else:
                style = self.style.SUCCESS
            self.stdout.write(style(f"  {type_value:<20} {count}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN complete. Would have updated {updated_total} notifications."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"\nDone. Updated {updated_total} notifications."))
        if counts["unmatched"] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"{counts['unmatched']} notifications did not match any pattern "
                    "and were left as NULL."
                )
            )
