"""
Creates or updates a Prefect deployment for backup_rds_flow.

Run once per RDS instance. Re-running updates the existing deployment.

PREFECT_API_URL and PREFECT_PROXY_GIT_BRANCH are read from the environment.

Usage:
    uv run python scripts/setup_backup_deployment.py \\
        --name backup-production \\
        --rds-secret-block rds-production \\
        --aws-secret-block backup-s3 \\
        --retention-days 30 \\
        --cron "0 2 * * *"
"""

import argparse
import asyncio
import os

from prefect import Flow
from prefect.runner.storage import GitRepository

PREFECT_PROXY_GIT_BRANCH = os.getenv("PREFECT_PROXY_GIT_BRANCH", "main")


async def create_deployment(args):
    source = GitRepository(
        url="https://github.com/DalgoT4D/dalgo.git",
        branch=PREFECT_PROXY_GIT_BRANCH,
        directories=["prefect-proxy"],
    )
    deployment_id = await Flow.from_source(
        source=source,
        entrypoint="prefect-proxy/proxy/backup_rds_flow.py:backup_rds_flow",
    ).deploy(
        name=args.name,
        work_pool_name=args.work_pool,
        work_queue_name=args.work_queue,
        parameters={
            "rds_secret_block": args.rds_secret_block,
            "aws_secret_block": args.aws_secret_block,
            "retention_days": args.retention_days,
        },
        schedules=[{"schedule": {"cron": args.cron, "timezone": "Asia/Kolkata"}, "active": True}],
        build=False,
        push=False,
    )
    print(f"Deployment '{args.name}' created/updated: {deployment_id}")


def main():
    parser = argparse.ArgumentParser(description="Create or update an RDS backup deployment")
    parser.add_argument("--name", required=True, help="Deployment name (e.g. backup-production)")
    parser.add_argument("--work-pool", required=True, help="Prefect work pool name")
    parser.add_argument("--work-queue", default="dailybackup", help="Prefect work queue name (default: dailybackup)")
    parser.add_argument("--rds-secret-block", required=True, help="Prefect secret block name for RDS creds")
    parser.add_argument("--aws-secret-block", required=True, help="Prefect secret block name for S3 creds")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--cron", default="0 8 * * *", help="Cron schedule (default: 8am IST daily)")
    args = parser.parse_args()

    asyncio.run(create_deployment(args))


if __name__ == "__main__":
    main()
