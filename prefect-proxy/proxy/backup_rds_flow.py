"""Daily RDS backup flow — secret block names and retention passed as deployment parameters."""

import datetime
import json
import os
import subprocess
import tempfile

import boto3
import psycopg2
import pytz
from prefect import flow, task
from prefect.blocks.system import Secret
from prefect.logging import get_run_logger


def _load_secret(block_name: str) -> dict:
    value = Secret.load(block_name).get()
    if isinstance(value, str):
        value = json.loads(value)
    return value


def _s3_client(aws: dict, logger):
    """Static keys only if the secret block still carries them (legacy).

    Otherwise use boto3's default credential chain: the IRSA role on EKS
    (service account prefect-backup) or the instance role on EC2.
    """
    access_key = aws.get("AWS_ACCESS_KEY")
    secret_key = aws.get("AWS_SECRET_KEY")
    if access_key and secret_key:
        logger.info("S3 auth: static keys from secret block")
        return boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    logger.info("S3 auth: default credential chain (IAM role)")
    return boto3.client("s3")


@task
def backup_rds(rds_secret_block: str, aws_secret_block: str, retention_days: int):
    logger = get_run_logger()

    rds = _load_secret(rds_secret_block)
    aws = _load_secret(aws_secret_block)

    pg_host = rds["PG_HOST"]
    pg_user = rds["PG_USER"]
    pg_password = rds["PG_PASSWORD"]
    s3_backup_path = rds["S3_BACKUP_PATH"]

    s3_bucket = aws["S3_BUCKET"]

    logger.info("Connecting to database host: %s", pg_host)
    conn = psycopg2.connect(
        dbname="postgres",
        user=pg_user,
        password=pg_password,
        host=pg_host,
        sslmode="require",
    )
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT datname FROM pg_database
        WHERE datistemplate = false AND datname != 'postgres' AND datname != 'rdsadmin';
    """
    )
    databases = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    logger.info("Found %d database(s) to back up: %s", len(databases), databases)

    s3_client = _s3_client(aws, logger)

    IST = pytz.timezone("Asia/Kolkata")
    timestamp = datetime.datetime.now(IST).strftime("%Y-%m-%d")

    with tempfile.TemporaryDirectory() as tmpdirname:
        for db in databases:
            backup_file = f"{db}_{timestamp}.sql.gz"
            backup_path = os.path.join(tmpdirname, backup_file)
            s3_key = f"{s3_backup_path}/{backup_file}"
            dump_cmd = (
                f'pg_dump "host={pg_host} user={pg_user} dbname={db} sslmode=require"'
                f" | gzip > {backup_path}"
            )
            logger.info("Backing up %s", db)
            subprocess.run(dump_cmd, shell=True, check=True, env={"PGPASSWORD": pg_password})
            s3_client.upload_file(backup_path, s3_bucket, s3_key)
            logger.info("Uploaded %s to s3://%s/%s", db, s3_bucket, s3_key)

    logger.info("Backups done. Cleaning up old backups...")

    expiration_date = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    ).strftime("%Y-%m-%d")

    response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_backup_path)
    for obj in response.get("Contents", []):
        obj_date = obj["Key"].split("_")[-1].replace(".sql.gz", "")
        if obj_date < expiration_date:
            logger.info("Deleting expired backup: %s", obj["Key"])
            s3_client.delete_object(Bucket=s3_bucket, Key=obj["Key"])

    logger.info("Backup process completed.")


@flow
def backup_rds_flow(
    rds_secret_block: str,
    aws_secret_block: str,
    retention_days: int = 30,
):
    backup_rds(rds_secret_block, aws_secret_block, retention_days)
