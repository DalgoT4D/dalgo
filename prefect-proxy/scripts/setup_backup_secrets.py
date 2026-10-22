"""
Creates or updates Prefect Secret blocks for RDS backup configuration.

Two block types:
  rds   — credentials for one RDS instance (PG_HOST, PG_USER, PG_PASSWORD, S3_BACKUP_PATH)
  s3    — shared AWS/S3 config (S3_BUCKET, AWS_ACCESS_KEY, AWS_SECRET_KEY)

PREFECT_API_URL is read from the environment.

Usage:
    # Create/update an RDS secret block
    uv run python scripts/setup_backup_secrets.py rds \\
        --name my-rds \\
        --pg-host mydb.abc123.us-east-1.rds.amazonaws.com \\
        --pg-user dalgo \\
        --pg-password secret \\
        --s3-backup-path backups/my-rds

    # Create/update the shared S3 secret block
    uv run python scripts/setup_backup_secrets.py s3 \\
        --name backup-s3 \\
        --s3-bucket dalgo-backups \\
        --aws-access-key AKIA... \\
        --aws-secret-key ...
"""

import argparse
import asyncio
import json

from prefect.blocks.system import Secret


async def upsert_secret(block_name: str, value: dict):
    try:
        block = await Secret.load(block_name)
        block.value = json.dumps(value)
        await block.save(name=block_name, overwrite=True)
        print(f"Updated secret block: {block_name}")
    except ValueError:
        block = Secret(value=json.dumps(value))
        await block.save(name=block_name)
        print(f"Created secret block: {block_name}")


async def setup_rds(args):
    value = {
        "PG_HOST": args.pg_host,
        "PG_USER": args.pg_user,
        "PG_PASSWORD": args.pg_password,
        "S3_BACKUP_PATH": args.s3_backup_path,
    }
    await upsert_secret(args.name, value)


async def setup_s3(args):
    value = {
        "S3_BUCKET": args.s3_bucket,
        "AWS_ACCESS_KEY": args.aws_access_key,
        "AWS_SECRET_KEY": args.aws_secret_key,
    }
    await upsert_secret(args.name, value)


def main():
    parser = argparse.ArgumentParser(description="Create or update backup secret blocks")
    sub = parser.add_subparsers(dest="command", required=True)

    rds = sub.add_parser("rds", help="RDS instance credentials")
    rds.add_argument("--name", required=True, help="Secret block name (e.g. rds-production)")
    rds.add_argument("--pg-host", required=True)
    rds.add_argument("--pg-user", required=True)
    rds.add_argument("--pg-password", required=True)
    rds.add_argument("--s3-backup-path", required=True, help="S3 prefix for this instance's backups")

    s3 = sub.add_parser("s3", help="Shared AWS/S3 config")
    s3.add_argument("--name", required=True, help="Secret block name (e.g. backup-s3)")
    s3.add_argument("--s3-bucket", required=True)
    s3.add_argument("--aws-access-key", required=True)
    s3.add_argument("--aws-secret-key", required=True)

    args = parser.parse_args()

    if args.command == "rds":
        asyncio.run(setup_rds(args))
    elif args.command == "s3":
        asyncio.run(setup_s3(args))


if __name__ == "__main__":
    main()
