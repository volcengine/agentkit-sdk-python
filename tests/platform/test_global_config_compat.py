import pytest
from agentkit.toolkit.config.global_config import GlobalConfig


class TestGlobalConfigCompatibility:
    def test_legacy_region_migration(self):
        """Test that legacy volcengine.region is correctly migrated to top-level region."""
        legacy_data = {
            "volcengine": {
                "access_key": "ak",
                "secret_key": "sk",
                "region": "cn-shanghai",  # Legacy location
            }
        }

        config = GlobalConfig.from_dict(legacy_data)

        # Verify region is hoisted
        assert config.region == "cn-shanghai"

        # Verify credentials are still there
        assert config.volcengine.access_key == "ak"

    def test_new_region_priority(self):
        """Test that top-level region takes priority over legacy location."""
        mixed_data = {
            "region": "cn-beijing",  # New location
            "volcengine": {
                "access_key": "ak",
                "secret_key": "sk",
                "region": "cn-shanghai",  # Legacy location
            },
        }

        config = GlobalConfig.from_dict(mixed_data)

        # Verify top-level wins
        assert config.region == "cn-beijing"
