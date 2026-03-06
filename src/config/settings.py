"""Application settings using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    discord_guild_id: int | None = Field(
        default=None,
        description="Optional Discord guild ID for fast guild-scoped slash command sync.",
    )

    # Azure OpenAI
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    azure_openai_api_key: str = Field(..., description="Azure OpenAI API key")
    azure_openai_deployment: str = Field(
        default="gpt-4o", description="Azure OpenAI deployment name"
    )
    llm_provider: Literal["azure_openai"] = Field(
        default="azure_openai",
        description="Configured LLM provider implementation.",
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
    obsidian_cli_command: str = Field(
        default="obsidian",
        description="Executable name for the Obsidian CLI.",
    )

    # Optional
    default_note_folder: str = Field(
        default="Inbox", description="Default folder for new notes"
    )
    reasoning_effort: Literal["none", "low", "medium", "high"] = Field(
        default="medium",
        description="Reasoning effort level: none, low, medium, high"
    )
    memory_db_path: Path = Field(
        default=Path(".janis-memory.sqlite3"),
        description="SQLite path for persistent conversation memory.",
    )
    memory_summary_interval: int = Field(
        default=10,
        description="Number of new conversation messages between summary refreshes.",
    )
    max_tool_iterations: int = Field(
        default=8,
        description="Maximum number of tool-calling loop iterations.",
    )
    prompt_cache_ttl_seconds: int = Field(
        default=300,
        description="Prompt cache TTL for conventions and tag registry reads.",
    )
    vault_conventions_note_path: str = Field(
        default="Vault Conventions",
        description="Vault-relative path for the note describing vault conventions.",
    )
    tag_registry_note_path: str = Field(
        default="Tag Registry",
        description="Vault-relative path for the tag registry note.",
    )

    @property
    def obsidian_api_url(self) -> str:
        """Get the full Obsidian REST API URL."""
        return f"https://{self.obsidian_api_host}:{self.obsidian_api_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
