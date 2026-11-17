"""Tests for AWS client"""

import os
import pytest
from unittest.mock import patch, MagicMock

from ddpui.utils.aws_client import AWSClient


class TestAWSClient:
    """Test cases for AWSClient"""

    def setup_method(self):
        """Reset AWS client before each test"""
        AWSClient.reset_instance()

    def teardown_method(self):
        """Clean up after each test"""
        AWSClient.reset_instance()

    @patch.dict(
        os.environ,
        {
            "SECRETSMANAGER_ACCESS_KEY_ID": "test-sm-key",
            "SECRETSMANAGER_SECRET_ACCESS_KEY": "test-sm-secret",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_secretsmanager_credentials(self, mock_session):
        """Test Secrets Manager credentials"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session
        mock_client = MagicMock()
        mock_boto_session.client.return_value = mock_client

        client = AWSClient.get_instance("secretsmanager")

        # Verify session was created with correct credentials
        mock_session.assert_called_once_with(
            aws_access_key_id="test-sm-key",
            aws_secret_access_key="test-sm-secret",
            region_name="us-east-1",
        )

        # Verify client was created
        mock_boto_session.client.assert_called_once_with("secretsmanager")
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "S3_AWS_ACCESS_KEY_ID": "test-s3-key",
            "S3_AWS_SECRET_ACCESS_KEY": "test-s3-secret",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_s3_credentials(self, mock_session):
        """Test S3 credential type"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session
        mock_client = MagicMock()
        mock_boto_session.client.return_value = mock_client

        client = AWSClient.get_instance("s3")

        # Verify session was created with correct credentials
        mock_session.assert_called_once_with(
            aws_access_key_id="test-s3-key",
            aws_secret_access_key="test-s3-secret",
            region_name="us-east-1",
        )

        # Verify client was created
        mock_boto_session.client.assert_called_once_with("s3")
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "SES_ACCESS_KEY_ID": "test-ses-key",
            "SES_SECRET_ACCESS_KEY": "test-ses-secret",
            "AWS_DEFAULT_REGION": "ap-south-1",
        },
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_ses_credentials(self, mock_session):
        """Test SES credential type"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session
        mock_client = MagicMock()
        mock_boto_session.client.return_value = mock_client

        client = AWSClient.get_instance("ses")

        # Verify session was created with correct credentials
        mock_session.assert_called_once_with(
            aws_access_key_id="test-ses-key",
            aws_secret_access_key="test-ses-secret",
            region_name="ap-south-1",
        )

        # Verify client was created
        mock_boto_session.client.assert_called_once_with("ses")
        assert client == mock_client

    def test_unsupported_service(self):
        """Test error for unsupported service"""
        with pytest.raises(ValueError, match="Unsupported service: invalid"):
            AWSClient.get_instance("invalid")

    def test_invalid_service_name(self):
        """Test error for invalid service name"""
        with pytest.raises(ValueError, match="Unsupported service: invalid2"):
            AWSClient.get_instance("invalid2")

    @pytest.mark.parametrize("service_name", ["secretsmanager", "s3", "ses"])
    @patch.dict(os.environ, {"AWS_DEFAULT_REGION": "ap-south-1"}, clear=True)
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_missing_keys_falls_back_to_default_credential_chain(self, mock_session, service_name):
        """No static keys -> session without explicit creds, so boto3 uses the instance/pod role"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session

        client = AWSClient.get_instance(service_name)

        mock_session.assert_called_once_with(region_name="ap-south-1")
        mock_boto_session.client.assert_called_once_with(service_name)
        assert client == mock_boto_session.client.return_value

    @patch.dict(
        os.environ,
        {"S3_AWS_ACCESS_KEY_ID": "test-s3-key", "AWS_DEFAULT_REGION": "ap-south-1"},
        clear=True,
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_half_set_keys_falls_back_to_default_credential_chain(self, mock_session):
        """Access key without secret is unusable, so it is ignored rather than passed half-set"""
        AWSClient.get_instance("s3")

        mock_session.assert_called_once_with(region_name="ap-south-1")

    @patch.dict(
        os.environ,
        {
            "SECRETSMANAGER_ACCESS_KEY_ID": "test-sm-key",
            "SECRETSMANAGER_SECRET_ACCESS_KEY": "test-sm-secret",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_client_caching(self, mock_session):
        """Test that clients are cached and reused"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session
        mock_client = MagicMock()
        mock_boto_session.client.return_value = mock_client

        # Get the same client twice
        client1 = AWSClient.get_instance("secretsmanager")
        client2 = AWSClient.get_instance("secretsmanager")

        # Should be the same instance
        assert client1 == client2

        # Session should only be created once
        mock_session.assert_called_once_with(
            aws_access_key_id="test-sm-key",
            aws_secret_access_key="test-sm-secret",
            region_name="us-east-1",
        )

        # Client should only be created once
        mock_boto_session.client.assert_called_once_with("secretsmanager")

    @patch.dict(
        os.environ,
        {
            "SECRETSMANAGER_ACCESS_KEY_ID": "test-sm-key",
            "SECRETSMANAGER_SECRET_ACCESS_KEY": "test-sm-secret",
            "S3_AWS_ACCESS_KEY_ID": "test-s3-key",
            "S3_AWS_SECRET_ACCESS_KEY": "test-s3-secret",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    )
    @patch("ddpui.utils.aws_client.boto3.Session")
    def test_separate_sessions_for_different_services(self, mock_session):
        """Test that different services create separate sessions"""
        mock_boto_session = MagicMock()
        mock_session.return_value = mock_boto_session
        mock_client = MagicMock()
        mock_boto_session.client.return_value = mock_client

        # Get clients for different services
        sm_client = AWSClient.get_instance("secretsmanager")
        s3_client = AWSClient.get_instance("s3")

        # Should create separate sessions
        assert mock_session.call_count == 2

        # Verify correct credentials were used for each session
        calls = mock_session.call_args_list
        assert calls[0][1]["aws_access_key_id"] == "test-sm-key"
        assert calls[1][1]["aws_access_key_id"] == "test-s3-key"
