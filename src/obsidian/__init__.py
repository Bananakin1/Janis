"""Obsidian integration module."""

from .vault_index import VaultIndex
from .rest_client import ObsidianRESTClient

__all__ = ["VaultIndex", "ObsidianRESTClient"]
