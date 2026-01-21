"""Application settings using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord
    discord_token: str = Field(..., description="Discord bot token")
    discord_channel_id: int = Field(..., description="Discord channel ID to listen on")

    # Azure OpenAI
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    azure_openai_api_key: str = Field(..., description="Azure OpenAI API key")
    azure_openai_deployment: str = Field(
        default="gpt-4o", description="Azure OpenAI deployment name"
    )
    azure_openai_api_version: str = Field(
        default="2024-08-01-preview", description="Azure OpenAI API version"
    )

    # Obsidian
    obsidian_vault_path: Path = Field(..., description="Path to Obsidian vault")
    obsidian_api_host: str = Field(
        default="127.0.0.1", description="Obsidian REST API host"
    )
    obsidian_api_port: int = Field(
        default=27124, description="Obsidian REST API port"
    )
    obsidian_api_key: str = Field(..., description="Obsidian REST API key")

    # Optional
    default_note_folder: str = Field(
        default="Inbox", description="Default folder for new notes"
    )
    reasoning_effort: str = Field(
        default="medium",
        description="Reasoning effort level: none, low, medium, high"
    )

    @property
    def obsidian_api_url(self) -> str:
        """Get the full Obsidian REST API URL."""
        return f"https://{self.obsidian_api_host}:{self.obsidian_api_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
