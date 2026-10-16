"""Management command to purge old notifications.

Reads NOTIFICATION_RETENTION_DAYS from environment (default: 30).
Actual deletion is handled by notifications_functions.purge_old_notifications.
"""

import os

from django.core.management.base import BaseCommand

from ddpui.core.notifications.notifications_functions import purge_old_notifications
from ddpui.utils.custom_logger import CustomLogger

logger = CustomLogger("ddpui")


class Command(BaseCommand):
    help = "Purge notifications older than NOTIFICATION_RETENTION_DAYS (default: 30)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deleted without deleting them",
        )
        parser.add_argument(
            "--days",
            type=int,
            help="Override NOTIFICATION_RETENTION_DAYS for this run",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        retention_days = options.get("days") or int(os.getenv("NOTIFICATION_RETENTION_DAYS", "30"))

        if dry_run:
            from django.utils import timezone
            from datetime import timedelta
            from ddpui.models.notifications import Notification

            cutoff = timezone.now() - timedelta(days=retention_days)
            count = Notification.objects.filter(timestamp__lt=cutoff).count()
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN — would delete {count} notifications older than "
                    f"{retention_days} days (cutoff: {cutoff.date()})."
                )
            )
            return

        deleted = purge_old_notifications(retention_days)
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} notifications older than {retention_days} days.")
        )
