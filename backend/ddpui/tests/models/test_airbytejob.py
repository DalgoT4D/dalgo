import os

import django
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.models.airbyte import AirbyteJob

pytestmark = pytest.mark.django_db


def _create(job_id: int, config_id: str) -> AirbyteJob:
    return AirbyteJob.objects.create(
        job_id=job_id,
        job_type="sync",
        config_id=config_id,
        status="succeeded",
        created_at=timezone.now(),
    )


def test_same_job_id_different_connection_is_allowed():
    first = _create(1, "conn-in")
    second = _create(1, "conn-af")
    assert first.id != second.id
    assert AirbyteJob.objects.filter(job_id=1).count() == 2


def test_duplicate_job_id_and_connection_is_rejected():
    _create(1, "conn-in")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _create(1, "conn-in")
