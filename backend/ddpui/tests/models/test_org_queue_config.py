import os
import pytest
from unittest.mock import patch
from ddpui.models.org import Org, get_default_queue_config
from ddpui.ddpprefect import (
    DDP_WORK_QUEUE,
    MANUL_DBT_WORK_QUEUE,
    EDR_WORK_QUEUE,
    SCHEDULED_PIPELINE_QUEUE,
    CONNECTION_SYNC_QUEUE,
)


@pytest.fixture
def mock_workpool_env():
    """Mock the PREFECT_WORKER_POOL_NAME environment variable."""
    with patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"}):
        yield


class TestOrgQueueConfig:
    """Test cases for Org.get_queue_config() method."""

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_no_stored_config(self):
        """Test get_queue_config when queue_config is None or empty."""
        org = Org(name="Test Org", queue_config=None)

        config = org.get_queue_config()

        assert config.scheduled_pipeline_queue.name == DDP_WORK_QUEUE
        assert config.scheduled_pipeline_queue.workpool == "test_workpool"
        assert config.connection_sync_queue.name == DDP_WORK_QUEUE
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
        assert config.transform_task_queue.workpool == "test_workpool"
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_empty_dict(self):
        """Test get_queue_config when queue_config is an empty dictionary."""
        org = Org(name="Test Org", queue_config={})

        config = org.get_queue_config()

        assert config.scheduled_pipeline_queue.name == DDP_WORK_QUEUE
        assert config.scheduled_pipeline_queue.workpool == "test_workpool"
        assert config.connection_sync_queue.name == DDP_WORK_QUEUE
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
        assert config.transform_task_queue.workpool == "test_workpool"
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_complete_nested_format(self):
        """Test get_queue_config with complete nested format data."""
        queue_config = {
            "scheduled_pipeline_queue": {
                "name": "custom-sync",
                "workpool": "custom-workpool",
            },
            "connection_sync_queue": {
                "name": "custom-connection",
                "workpool": "another-workpool",
            },
            "transform_task_queue": {
                "name": "custom-transform",
                "workpool": "transform-workpool",
            },
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        assert config.scheduled_pipeline_queue.name == "custom-sync"
        assert config.scheduled_pipeline_queue.workpool == "custom-workpool"
        assert config.connection_sync_queue.name == "custom-connection"
        assert config.connection_sync_queue.workpool == "another-workpool"
        assert config.transform_task_queue.name == "custom-transform"
        assert config.transform_task_queue.workpool == "transform-workpool"
        # edr_queue should fall back to defaults since not in config
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_nested_format_missing_workpool(self):
        """Test get_queue_config with nested format but missing workpool values."""
        queue_config = {
            "scheduled_pipeline_queue": {"name": "custom-sync"},  # missing workpool
            "connection_sync_queue": {
                "name": "custom-connection",
                "workpool": None,
            },  # None workpool
            "transform_task_queue": {
                "name": "custom-transform",
                "workpool": "transform-workpool",
            },
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        # Should fall back to default workpool for missing/None workpool
        assert config.scheduled_pipeline_queue.name == "custom-sync"
        assert config.scheduled_pipeline_queue.workpool == "test_workpool"
        assert config.connection_sync_queue.name == "custom-connection"
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == "custom-transform"
        assert config.transform_task_queue.workpool == "transform-workpool"
        # edr_queue should fall back to defaults since not in config
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_legacy_flat_format(self):
        """Test get_queue_config with legacy flat format (strings)."""
        queue_config = {
            "scheduled_pipeline_queue": "legacy-sync",
            "connection_sync_queue": "legacy-connection",
            "transform_task_queue": "legacy-transform",
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        # Should use queue names from stored config, workpool from default
        assert config.scheduled_pipeline_queue.name == "legacy-sync"
        assert config.scheduled_pipeline_queue.workpool == "test_workpool"
        assert config.connection_sync_queue.name == "legacy-connection"
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == "legacy-transform"
        assert config.transform_task_queue.workpool == "test_workpool"
        # edr_queue should fall back to defaults since not in config
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_mixed_formats(self):
        """Test get_queue_config with mixed format data."""
        queue_config = {
            "scheduled_pipeline_queue": {
                "name": "nested-sync",
                "workpool": "custom-workpool",
            },
            "connection_sync_queue": "flat-connection",  # legacy flat format
            # transform_task_queue missing entirely
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        assert config.scheduled_pipeline_queue.name == "nested-sync"
        assert config.scheduled_pipeline_queue.workpool == "custom-workpool"
        assert config.connection_sync_queue.name == "flat-connection"
        assert config.connection_sync_queue.workpool == "test_workpool"
        # Missing key should fall back to defaults
        assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
        assert config.transform_task_queue.workpool == "test_workpool"
        # edr_queue should fall back to defaults since not in config
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_with_invalid_data_types(self):
        """Test get_queue_config with invalid data types (should fall back to defaults)."""
        queue_config = {
            "scheduled_pipeline_queue": 123,  # invalid type (number)
            "connection_sync_queue": [],  # invalid type (list)
            "transform_task_queue": {"invalid": "structure"},  # invalid structure (missing name)
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        # All should fall back to defaults due to invalid data
        assert config.scheduled_pipeline_queue.name == DDP_WORK_QUEUE
        assert config.scheduled_pipeline_queue.workpool == "test_workpool"
        assert config.connection_sync_queue.name == DDP_WORK_QUEUE
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
        assert config.transform_task_queue.workpool == "test_workpool"
        # edr_queue should fall back to defaults since not in config
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"

    def test_get_queue_config_without_env_var(self):
        """Test get_queue_config when PREFECT_WORKER_POOL_NAME is not set."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            org = Org(name="Test Org", queue_config=None)

            config = org.get_queue_config()

            # Should fall back to "default" for workpool when env var is not set
            assert config.scheduled_pipeline_queue.name == DDP_WORK_QUEUE
            assert config.scheduled_pipeline_queue.workpool == "default"
            assert config.connection_sync_queue.name == DDP_WORK_QUEUE
            assert config.connection_sync_queue.workpool == "default"
            assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
            assert config.transform_task_queue.workpool == "default"
            assert config.edr_queue.name == EDR_WORK_QUEUE
            assert config.edr_queue.workpool == "default"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": ""})
    def test_get_queue_config_with_empty_env_var(self):
        """Test get_queue_config when PREFECT_WORKER_POOL_NAME is empty string."""
        org = Org(name="Test Org", queue_config=None)

        config = org.get_queue_config()

        # Should fall back to "default" when env var is empty string
        assert config.scheduled_pipeline_queue.workpool == "default"
        assert config.connection_sync_queue.workpool == "default"
        assert config.transform_task_queue.workpool == "default"
        assert config.edr_queue.workpool == "default"

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_queue_config_partial_nested_data(self):
        """Test get_queue_config with partial nested data for some queues."""
        queue_config = {
            "scheduled_pipeline_queue": {
                "name": "custom-sync",
                "workpool": "custom-workpool",
            },
        }
        org = Org(name="Test Org", queue_config=queue_config)

        config = org.get_queue_config()

        # Custom queue should use stored data
        assert config.scheduled_pipeline_queue.name == "custom-sync"
        assert config.scheduled_pipeline_queue.workpool == "custom-workpool"

        # Missing queues should fall back to defaults
        assert config.connection_sync_queue.name == DDP_WORK_QUEUE
        assert config.connection_sync_queue.workpool == "test_workpool"
        assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE
        assert config.transform_task_queue.workpool == "test_workpool"
        assert config.edr_queue.name == EDR_WORK_QUEUE
        assert config.edr_queue.workpool == "test_workpool"


class TestGetDefaultQueueConfig:
    """Test cases for get_default_queue_config() function."""

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": "test_workpool"})
    def test_get_default_queue_config_with_env_var(self):
        """Test get_default_queue_config when environment variable is set."""
        config = get_default_queue_config()

        expected = {
            "scheduled_pipeline_queue": {
                "name": DDP_WORK_QUEUE,
                "workpool": "test_workpool",
                "is_workpool_eks": False,
            },
            "connection_sync_queue": {
                "name": DDP_WORK_QUEUE,
                "workpool": "test_workpool",
                "is_workpool_eks": False,
            },
            "transform_task_queue": {
                "name": MANUL_DBT_WORK_QUEUE,
                "workpool": "test_workpool",
                "is_workpool_eks": False,
            },
            "edr_queue": {
                "name": EDR_WORK_QUEUE,
                "workpool": "test_workpool",
                "is_workpool_eks": False,
            },
        }

        assert config == expected

    def test_get_default_queue_config_without_env_var(self):
        """Test get_default_queue_config when environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_default_queue_config()

            expected = {
                "scheduled_pipeline_queue": {
                    "name": DDP_WORK_QUEUE,
                    "workpool": "default",
                    "is_workpool_eks": False,
                },
                "connection_sync_queue": {
                    "name": DDP_WORK_QUEUE,
                    "workpool": "default",
                    "is_workpool_eks": False,
                },
                "transform_task_queue": {
                    "name": MANUL_DBT_WORK_QUEUE,
                    "workpool": "default",
                    "is_workpool_eks": False,
                },
                "edr_queue": {
                    "name": EDR_WORK_QUEUE,
                    "workpool": "default",
                    "is_workpool_eks": False,
                },
            }

            assert config == expected

    @patch.dict(os.environ, {"PREFECT_WORKER_POOL_NAME": ""})
    def test_get_default_queue_config_with_empty_env_var(self):
        """Test get_default_queue_config when environment variable is empty."""
        config = get_default_queue_config()

        expected = {
            "scheduled_pipeline_queue": {
                "name": DDP_WORK_QUEUE,
                "workpool": "default",
                "is_workpool_eks": False,
            },
            "connection_sync_queue": {
                "name": DDP_WORK_QUEUE,
                "workpool": "default",
                "is_workpool_eks": False,
            },
            "transform_task_queue": {
                "name": MANUL_DBT_WORK_QUEUE,
                "workpool": "default",
                "is_workpool_eks": False,
            },
            "edr_queue": {
                "name": EDR_WORK_QUEUE,
                "workpool": "default",
                "is_workpool_eks": False,
            },
        }

        assert config == expected

    @patch.dict(
        os.environ,
        {
            "PREFECT_WORKER_POOL_NAME": "ec2-pool",
            "PREFECT_EKS_WORKER_POOL_NAME": "eks-pool",
        },
    )
    def test_get_default_queue_config_with_eks_env_var(self):
        """Test that all queues use EKS pool when PREFECT_EKS_WORKER_POOL_NAME is configured."""
        config = get_default_queue_config()

        expected = {
            "scheduled_pipeline_queue": {
                "name": SCHEDULED_PIPELINE_QUEUE,
                "workpool": "eks-pool",
                "is_workpool_eks": True,
            },
            "connection_sync_queue": {
                "name": CONNECTION_SYNC_QUEUE,
                "workpool": "eks-pool",
                "is_workpool_eks": True,
            },
            "transform_task_queue": {
                "name": MANUL_DBT_WORK_QUEUE,
                "workpool": "eks-pool",
                "is_workpool_eks": True,
            },
            "edr_queue": {
                "name": EDR_WORK_QUEUE,
                "workpool": "eks-pool",
                "is_workpool_eks": True,
            },
        }

        assert config == expected


# ---------------------------------------------------------------------------------------------
# multi-region: fallbacks must never put a non-home-region org on a home-region (env) pool
# ---------------------------------------------------------------------------------------------
AF_REGION_CONFIG = {
    "aws_region": "af-south-1",
    "country": "ZA",
    "airbyte_secret_name": "dalgoAirbyteRegion-test-af",
}
HOME_REGION_CONFIG = {
    "aws_region": "ap-south-1",
    "country": "India",
    "airbyte_secret_name": "dalgoAirbyteRegion-test-in",
}
AF_POOL = "staging_af_eks_work_pool"
ENV_POOLS = {"PREFECT_WORKER_POOL_NAME": "env_pool", "PREFECT_EKS_WORKER_POOL_NAME": "env_eks_pool"}

# each stored config exercises one fallback branch of get_queue_config for "transform_task_queue";
# the other three queues carry the region pool, as an org created by RegionService would
FALLBACK_BRANCHES = {
    "key_missing": None,
    "nested_without_workpool": {"name": MANUL_DBT_WORK_QUEUE},
    "legacy_flat_string": MANUL_DBT_WORK_QUEUE,
    "invalid_type": 42,
}


def _stored(pool: str, branch_value) -> dict:
    stored = {
        "scheduled_pipeline_queue": {
            "name": SCHEDULED_PIPELINE_QUEUE,
            "workpool": pool,
            "is_workpool_eks": True,
        },
        "connection_sync_queue": {
            "name": CONNECTION_SYNC_QUEUE,
            "workpool": pool,
            "is_workpool_eks": True,
        },
        "edr_queue": {"name": EDR_WORK_QUEUE, "workpool": pool, "is_workpool_eks": True},
    }
    if branch_value is not None:
        stored["transform_task_queue"] = branch_value
    return stored


@pytest.mark.parametrize("branch", list(FALLBACK_BRANCHES))
@patch.dict(os.environ, ENV_POOLS)
def test_fallback_af_org_stays_on_region_pool(branch):
    org = Org(
        name="af",
        slug="af",
        region_config=AF_REGION_CONFIG,
        queue_config=_stored(AF_POOL, FALLBACK_BRANCHES[branch]),
    )
    config = org.get_queue_config()
    for queue in (
        config.scheduled_pipeline_queue,
        config.connection_sync_queue,
        config.transform_task_queue,
        config.edr_queue,
    ):
        assert queue.workpool == AF_POOL
        assert queue.is_workpool_eks is True
    assert config.transform_task_queue.name == MANUL_DBT_WORK_QUEUE


@pytest.mark.parametrize("region_config", [None, HOME_REGION_CONFIG])
@pytest.mark.parametrize("branch", list(FALLBACK_BRANCHES))
@patch.dict(os.environ, ENV_POOLS)
def test_fallback_home_org_unchanged(branch, region_config):
    """a Mumbai org (backfilled or NULL region_config) resolves exactly as before"""
    stored = _stored("env_eks_pool", FALLBACK_BRANCHES[branch])
    org = Org(name="in", slug="in", region_config=region_config, queue_config=stored)
    legacy_org = Org(name="in", slug="in", queue_config=stored)  # pre-multi-region row
    assert org.get_queue_config() == legacy_org.get_queue_config()

    transform = org.get_queue_config().transform_task_queue
    default = get_default_queue_config()["transform_task_queue"]
    assert transform.workpool == default["workpool"]
    expected_eks = {
        "key_missing": default["is_workpool_eks"],
        "nested_without_workpool": False,
        "legacy_flat_string": False,
        "invalid_type": False,
    }[branch]
    assert transform.is_workpool_eks is expected_eks


@patch.dict(os.environ, ENV_POOLS)
def test_fallback_af_org_without_any_pool_raises():
    org = Org(name="af", slug="af", region_config=AF_REGION_CONFIG, queue_config={})
    with pytest.raises(ValueError, match="no workpool"):
        org.get_queue_config()
