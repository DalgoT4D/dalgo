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


def _load_secret(block_name: str) -> dict:
    value = Secret.load(block_name).get()
    if isinstance(value, str):
        value = json.loads(value)
    return value


@task
def backup_rds(rds_secret_block: str, aws_secret_block: str, retention_days: int):
    rds = _load_secret(rds_secret_block)
    aws = _load_secret(aws_secret_block)

    pg_host = rds["PG_HOST"]
    pg_user = rds["PG_USER"]
    pg_password = rds["PG_PASSWORD"]
    s3_backup_path = rds["S3_BACKUP_PATH"]

    s3_bucket = aws["S3_BUCKET"]
    aws_access_key = aws["AWS_ACCESS_KEY"]
    aws_secret_key = aws["AWS_SECRET_KEY"]

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

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
    )

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
            print(f"Backing up {db} → s3://{s3_bucket}/{s3_key}")
            subprocess.run(f"PGPASSWORD={pg_password} " + dump_cmd, shell=True, check=True)
            s3_client.upload_file(backup_path, s3_bucket, s3_key)

    print("Backups done. Cleaning up old backups...")

    expiration_date = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    ).strftime("%Y-%m-%d")

    response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_backup_path)
    for obj in response.get("Contents", []):
        obj_date = obj["Key"].split("_")[-1].replace(".sql.gz", "")
        if obj_date < expiration_date:
            print(f"Deleting {obj['Key']}")
            s3_client.delete_object(Bucket=s3_bucket, Key=obj["Key"])

    print("Backup process completed.")


@flow
def backup_rds_flow(
    rds_secret_block: str,
    aws_secret_block: str,
    retention_days: int = 30,
):
    backup_rds(rds_secret_block, aws_secret_block, retention_days)
