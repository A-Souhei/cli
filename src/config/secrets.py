"""Secrets manager for API keys and sensitive configuration."""

import os
import yaml
from pathlib import Path
from typing import Optional

from src.sentry_config import capture_exception


class SecretsManager:
    """Manages loading and accessing secrets from secrets.yaml."""

    def __init__(self, secrets_path: str = None):
        """
        Initialize the SecretsManager.

        Args:
            secrets_path: Path to secrets.yaml. If None, uses default location.
        """
        if secrets_path is None:
            # Default to secrets.yaml in the project root
            secrets_path = Path(__file__).parent.parent.parent / "secrets.yaml"

        self.secrets_path = Path(secrets_path)
        self.secrets = self._load_secrets()

    def _load_secrets(self) -> dict:
        """
        Load secrets from YAML file.

        Returns:
            Dictionary with secrets, empty dict if file doesn't exist.
        """
        if not self.secrets_path.exists():
            # Return empty dict if secrets file doesn't exist
            # This allows the app to run without Anthropic configured
            return {}

        try:
            with open(self.secrets_path, 'r') as f:
                secrets = yaml.safe_load(f)
            return secrets if secrets else {}
        except Exception as e:
            capture_exception(e)
            return {}

    def get_anthropic_api_key(self) -> Optional[str]:
        """
        Get the Anthropic API key.

        First checks the secrets.yaml file, then falls back to
        ANTHROPIC_API_KEY environment variable.

        Returns:
            API key string if found, None otherwise.
        """
        # Check secrets.yaml first
        api_key = self.secrets.get('anthropic', {}).get('api_key', '')

        if api_key:
            return api_key

        # Fall back to environment variable
        return os.environ.get('ANTHROPIC_API_KEY')

    def has_anthropic_api_key(self) -> bool:
        """
        Check if an Anthropic API key is configured.

        Returns:
            True if API key is available, False otherwise.
        """
        api_key = self.get_anthropic_api_key()
        return bool(api_key and api_key.strip())

    def reload(self) -> None:
        """Reload secrets from file."""
        self.secrets = self._load_secrets()
