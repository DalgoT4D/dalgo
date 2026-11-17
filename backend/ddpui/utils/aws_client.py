"""Unified AWS client for all AWS services used in Dalgo"""

import os
import logging
import threading
import boto3

logger = logging.getLogger(__name__)


class AWSClient:
    """
    Singleton AWS client with session management.
    Use this class anywhere in the code to interact with AWS services.

    Environment Variables by Service:
    - secretsmanager: Uses SECRETSMANAGER_ACCESS_KEY_ID & SECRETSMANAGER_SECRET_ACCESS_KEY
    - s3: Uses S3_AWS_ACCESS_KEY_ID & S3_AWS_SECRET_ACCESS_KEY
    - ses: Uses SES_ACCESS_KEY_ID & SES_SECRET_ACCESS_KEY

    If a service's key pair is not set, boto3's default credential chain is used
    (EC2 instance profile, EKS pod identity / IRSA, ~/.aws, AWS_* env vars).

    Each service maintains its own boto3 session and client cache.
    """

    _locks = {"secretsmanager": threading.Lock(), "s3": threading.Lock(), "ses": threading.Lock()}

    _clients = {}  # for various services

    # Supported AWS services
    SUPPORTED_SERVICES = {"s3", "ses", "secretsmanager"}

    @classmethod
    def get_instance(cls, service_name: str):
        """
        Returns the AWS service client instance.

        Args:
            service_name: AWS service name (e.g., 's3', 'ses', 'secretsmanager')

        Returns:
            boto3 client for the specified service

        Raises:
            ValueError: If service_name is not supported
        """
        if service_name not in cls.SUPPORTED_SERVICES:
            raise ValueError(
                f"Unsupported service: {service_name}. Supported services: {cls.SUPPORTED_SERVICES}"
            )

        return cls._get_client(service_name)

    @classmethod
    def _get_client(cls, service_name: str):
        """Get client for the specified service"""
        if service_name not in cls._clients or cls._clients[service_name] is None:
            if cls._locks[service_name].acquire(timeout=10):
                if service_name not in cls._clients or cls._clients[service_name] is None:
                    try:
                        boto_session = cls._initialize_boto_session(service_name)
                        cls._clients[service_name] = boto_session.client(service_name)
                    finally:
                        cls._locks[service_name].release()
            else:
                logger.warning(
                    f"Timeout while acquiring lock for {service_name} session initialization"
                )

        if cls._clients[service_name] is None:
            raise RuntimeError(f"Failed to initialize client for {service_name}")

        return cls._clients[service_name]

    @classmethod
    def _initialize_boto_session(cls, service_name: str) -> boto3.Session:
        """Initialize generic AWS boto3 session for a particular set of creds"""
        region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

        # Get credentials based on service
        if service_name == "secretsmanager":
            access_key = os.getenv("SECRETSMANAGER_ACCESS_KEY_ID")
            secret_key = os.getenv("SECRETSMANAGER_SECRET_ACCESS_KEY")
            service_display = "Secrets Manager"
        elif service_name == "s3":
            access_key = os.getenv("S3_AWS_ACCESS_KEY_ID")
            secret_key = os.getenv("S3_AWS_SECRET_ACCESS_KEY")
            service_display = "S3"
        elif service_name == "ses":
            access_key = os.getenv("SES_ACCESS_KEY_ID")
            secret_key = os.getenv("SES_SECRET_ACCESS_KEY")
            service_display = "SES"
        else:
            raise ValueError(f"Unsupported service: {service_name}")

        if access_key and secret_key:
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            logger.info(f"Initialized boto session for {service_display} with static keys")
            return session

        # No static keys: boto3's default chain finds the EC2 instance profile / EKS pod role
        session = boto3.Session(region_name=region)
        logger.info(f"Initialized boto session for {service_display} with default credential chain")
        return session

    @classmethod
    def reset_instance(cls):
        """Reset all sessions and clients"""
        # Release any locks that might be held
        for service_name in cls.SUPPORTED_SERVICES:
            try:
                if cls._locks[service_name].locked():
                    cls._locks[service_name].release()
            except:
                pass

        cls._clients = {}
