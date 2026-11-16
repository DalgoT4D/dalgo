"""Celery task that reviews an uploaded row-access list; the warehouse queries can be slow."""

from ddpui.celery import app
from ddpui.core.rls import access_list_service
from ddpui.core.rls.exceptions import RowAccessError
from ddpui.models.org_user import OrgUser
from ddpui.models.tasks import TaskProgressStatus
from ddpui.utils.custom_logger import CustomLogger
from ddpui.utils.singletaskprogress import SingleTaskProgress

logger = CustomLogger("ddpui.celeryworkers.rls_tasks")

# long enough for the page to read the result after a slow warehouse review
REVIEW_PROGRESS_TTL_SECONDS = 30 * 60


@app.task
def review_access_list_upload(task_key: str, orguser_id: int, csv_text: str):
    progress = SingleTaskProgress(task_key, REVIEW_PROGRESS_TTL_SECONDS)
    progress.add({"status": TaskProgressStatus.RUNNING, "message": "Checking the list against your data"})
    orguser = OrgUser.objects.select_related("org").get(id=orguser_id)
    try:
        upload = access_list_service.upload_access_list(orguser.org, orguser, csv_text)
    except RowAccessError as err:
        progress.add({"status": TaskProgressStatus.FAILED, "message": str(err)})
        return
    except Exception:  # pylint: disable=broad-except
        logger.exception(f"row access review failed for org {orguser.org.slug}")
        progress.add(
            {"status": TaskProgressStatus.FAILED, "message": "Something went wrong. Try again."}
        )
        return
    progress.add(
        {
            "status": TaskProgressStatus.COMPLETED,
            "message": "Review ready",
            "result": {"upload_id": upload.id},
        }
    )
