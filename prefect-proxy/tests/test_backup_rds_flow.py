"""Tests for proxy.backup_rds_flow"""

import json
from unittest.mock import MagicMock, patch

import pytest

from proxy.backup_rds_flow import _load_secret, backup_rds


# ── _load_secret ─────────────────────────────────────────────────────────────


def _mock_secret(value):
    mock_block = MagicMock()
    mock_block.get.return_value = value
    return mock_block


@patch("proxy.backup_rds_flow.Secret")
def test_load_secret_returns_dict_directly(mock_secret_cls):
    config = {"PG_HOST": "localhost", "PG_USER": "user"}
    mock_secret_cls.load.return_value = _mock_secret(config)

    result = _load_secret("my-block")

    assert result == config


@patch("proxy.backup_rds_flow.Secret")
def test_load_secret_parses_json_string(mock_secret_cls):
    config = {"PG_HOST": "localhost", "PG_USER": "user"}
    mock_secret_cls.load.return_value = _mock_secret(json.dumps(config))

    result = _load_secret("my-block")

    assert result == config


# ── backup_rds task ───────────────────────────────────────────────────────────

RDS_CONFIG = {
    "PG_HOST": "db.example.com",
    "PG_USER": "admin",
    "PG_PASSWORD": "secret",
    "S3_BACKUP_PATH": "backups/production",
}

AWS_CONFIG = {
    "S3_BUCKET": "dalgo-backups",
    "AWS_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
}


def _setup_mocks(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess, databases):
    mock_secret_cls.load.side_effect = [_mock_secret(RDS_CONFIG), _mock_secret(AWS_CONFIG)]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(db,) for db in databases]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn

    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_subprocess.return_value = MagicMock(returncode=0)

    return mock_s3


@patch("proxy.backup_rds_flow.subprocess.run")
@patch("proxy.backup_rds_flow.boto3")
@patch("proxy.backup_rds_flow.psycopg2")
@patch("proxy.backup_rds_flow.Secret")
def test_backup_rds_backs_up_all_databases(
    mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess
):
    databases = ["app_db", "analytics_db"]
    mock_s3 = _setup_mocks(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess, databases)
    mock_s3.list_objects_v2.return_value = {}

    backup_rds.fn("rds-production", "backup-s3", 30)

    assert mock_subprocess.call_count == 2
    assert mock_s3.upload_file.call_count == 2


@patch("proxy.backup_rds_flow.subprocess.run")
@patch("proxy.backup_rds_flow.boto3")
@patch("proxy.backup_rds_flow.psycopg2")
@patch("proxy.backup_rds_flow.Secret")
def test_backup_rds_deletes_expired_objects(
    mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess
):
    mock_s3 = _setup_mocks(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess, ["app_db"])
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/production/app_db_2020-01-01.sql.gz"},
            {"Key": "backups/production/app_db_2020-01-02.sql.gz"},
        ]
    }

    backup_rds.fn("rds-production", "backup-s3", 30)

    assert mock_s3.delete_object.call_count == 2


@patch("proxy.backup_rds_flow.subprocess.run")
@patch("proxy.backup_rds_flow.boto3")
@patch("proxy.backup_rds_flow.psycopg2")
@patch("proxy.backup_rds_flow.Secret")
def test_backup_rds_skips_recent_objects(
    mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess
):
    mock_s3 = _setup_mocks(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess, ["app_db"])
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/production/app_db_2099-01-01.sql.gz"},
        ]
    }

    backup_rds.fn("rds-production", "backup-s3", 30)

    mock_s3.delete_object.assert_not_called()


@patch("proxy.backup_rds_flow.subprocess.run")
@patch("proxy.backup_rds_flow.boto3")
@patch("proxy.backup_rds_flow.psycopg2")
@patch("proxy.backup_rds_flow.Secret")
def test_backup_rds_no_databases(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess):
    mock_s3 = _setup_mocks(mock_secret_cls, mock_psycopg2, mock_boto3, mock_subprocess, [])
    mock_s3.list_objects_v2.return_value = {}

    backup_rds.fn("rds-production", "backup-s3", 30)

    mock_subprocess.assert_not_called()
    mock_s3.upload_file.assert_not_called()
