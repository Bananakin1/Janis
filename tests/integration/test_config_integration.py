"""Integration tests for configuration loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config.settings import Settings, get_settings


class TestSettingsIntegration:
    """Integration tests for Settings loading from environment."""

    def test_settings_loads_from_env(self, mock_env_vars, temp_vault):
        """Test that settings loads all values from environment variables."""
        # Clear the lru_cache to force reload
        get_settings.cache_clear()

        settings = Settings()

        assert settings.discord_token == "test-discord-token"
        assert settings.discord_channel_id == 123456789012345678
        assert settings.azure_openai_endpoint == "https://test.openai.azure.com/"
        assert settings.azure_openai_api_key == "test-azure-key"
        assert settings.azure_openai_deployment == "gpt-4o"
        assert settings.obsidian_vault_path == Path(temp_vault)
        assert settings.obsidian_api_host == "127.0.0.1"
        assert settings.obsidian_api_port == 27124
        assert settings.obsidian_api_key == "test-obsidian-key"
        assert settings.default_note_folder == "Inbox"

    def test_settings_obsidian_api_url_property(self, mock_env_vars):
        """Test that obsidian_api_url is constructed correctly."""
        settings = Settings()

        assert settings.obsidian_api_url == "https://127.0.0.1:27124"

    def test_settings_default_values(self, mock_env_vars):
        """Test that default values are applied correctly."""
        # The default values are already tested implicitly
        # Just verify the settings object has expected defaults
        settings = Settings()

        # These are the defaults from the Settings class
        assert settings.azure_openai_deployment == "gpt-4o"
        assert settings.azure_openai_api_version == "2024-08-01-preview"
        assert settings.obsidian_api_host == "127.0.0.1"
        assert settings.obsidian_api_port == 27124
        assert settings.default_note_folder == "Inbox"

    def test_settings_requires_discord_token(self, mock_env_vars):
        """Test that missing discord token raises ValidationError."""
        env_without_token = {k: v for k, v in mock_env_vars.items() if k != "DISCORD_TOKEN"}

        with patch.dict(os.environ, env_without_token, clear=True):
            with pytest.raises(ValidationError):
                Settings(_env_file=None)

    def test_settings_invalid_channel_id_raises(self, mock_env_vars):
        """Test that non-numeric channel ID raises ValidationError."""
        env_with_bad_channel = mock_env_vars.copy()
        env_with_bad_channel["DISCORD_CHANNEL_ID"] = "not-a-number"

        with patch.dict(os.environ, env_with_bad_channel, clear=True):
            with pytest.raises(ValidationError):
                Settings()

    def test_get_settings_caches_result(self, mock_env_vars):
        """Test that get_settings returns cached instance."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_settings_with_custom_port(self, mock_env_vars):
        """Test settings with non-default Obsidian API port."""
        env_with_custom_port = mock_env_vars.copy()
        env_with_custom_port["OBSIDIAN_API_PORT"] = "8080"

        with patch.dict(os.environ, env_with_custom_port, clear=True):
            settings = Settings()

            assert settings.obsidian_api_port == 8080
            assert settings.obsidian_api_url == "https://127.0.0.1:8080"
