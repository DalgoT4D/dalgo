"""
One-time fixup: re-tag notifications that were incorrectly classified as 'platform'
during the original backfill but actually contain pipeline-failure message patterns.

The original backfill missed "A job has failed…" messages because the PIPELINE regex
only matched "pipeline", "flow run", and "prefect" — not the short-form message that
webhook_functions._build_failure_message_for_org_users emits when no deployment name
is available.

Run with --dry-run first to preview how many rows will change.
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from ddpui.models.notifications import Notification
from ddpui.schemas.notifications_api_schemas import NotificationType

PIPELINE_PATTERN = re.compile(
    r"(Pipeline Failure" r"|pipeline.*fail" r"|a job has failed" r"|flow.?run" r"|prefect)",
    re.IGNORECASE,
)


class Command(BaseCommand):
    help = (
        "Re-tag notifications incorrectly classified as 'platform' that are actually "
        "pipeline failure alerts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be updated without writing to the database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written\n"))

        platform_qs = Notification.objects.filter(notification_type=NotificationType.PLATFORM.value)
        total = platform_qs.count()
        self.stdout.write(f"Scanning {total} notifications tagged as 'platform'...\n")

        to_fix = [n for n in platform_qs if PIPELINE_PATTERN.search(n.message)]
        self.stdout.write(f"Found {len(to_fix)} that match the pipeline pattern.\n")

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("Nothing to fix."))
            return

        for n in to_fix[:5]:
            self.stdout.write(f"  [{n.id}] {n.message[:80]!r}")
        if len(to_fix) > 5:
            self.stdout.write(f"  … and {len(to_fix) - 5} more")

        if not dry_run:
            with transaction.atomic():
                for n in to_fix:
                    n.notification_type = NotificationType.PIPELINE.value
                Notification.objects.bulk_update(to_fix, ["notification_type"])
            self.stdout.write(
                self.style.SUCCESS(f"\nDone. Re-tagged {len(to_fix)} notifications as 'pipeline'.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"\nDRY RUN complete. Would re-tag {len(to_fix)} notifications.")
            )
