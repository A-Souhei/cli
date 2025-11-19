"""Configuration manager for the AI CLI."""

import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    """Manages loading and accessing configuration from config.yaml."""

    def __init__(self, config_path: str = None):
        """
        Initialize the ConfigManager.

        Args:
            config_path: Path to the config.yaml file. If None, uses default location.
        """
        if config_path is None:
            # Default to config.yaml in the project root
            config_path = Path(__file__).parent.parent.parent / "config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        return config

    def get_ollama_url(self) -> str:
        """Get the Ollama service URL."""
        return self.config.get('ollama', {}).get('url', 'http://localhost:11434')

    def get_ollama_model(self) -> str:
        """Get the Ollama model name."""
        return self.config.get('ollama', {}).get('model', 'llama2')

    def get_ollama_timeout(self) -> int:
        """Get the Ollama request timeout."""
        return self.config.get('ollama', {}).get('timeout', 120)

    def get_system_prompt(self) -> str:
        """Get the system prompt for chat."""
        return self.config.get('chat', {}).get('system_prompt', 'You are a helpful AI assistant.')

    def get_max_context_length(self) -> int:
        """Get the maximum context length for chat."""
        return self.config.get('chat', {}).get('max_context_length', 10)

    def get_temperature(self) -> float:
        """Get the temperature for response generation."""
        return self.config.get('chat', {}).get('temperature', 0.7)

    def get_stream_enabled(self) -> bool:
        """Check if streaming is enabled."""
        return self.config.get('chat', {}).get('stream', True)
