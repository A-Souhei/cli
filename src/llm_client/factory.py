"""Factory for creating LLM clients based on provider."""

from typing import Optional, Union

from src.model_registry.manager import ModelConfig
from src.config.secrets import SecretsManager
from src.ollama_client import OllamaClient


class LLMClientFactory:
    """Factory for creating LLM clients based on model provider."""

    @staticmethod
    def create_client(
        model_config: ModelConfig,
        secrets_manager: Optional[SecretsManager] = None
    ) -> Union[OllamaClient, 'AnthropicClient']:
        """
        Create an LLM client for the given model configuration.

        Args:
            model_config: ModelConfig with provider, url, model_name, timeout
            secrets_manager: SecretsManager for API keys (required for Anthropic)

        Returns:
            OllamaClient or AnthropicClient based on provider

        Raises:
            ValueError: If provider is unknown or API key is missing for Anthropic
        """
        provider = getattr(model_config, 'provider', 'ollama')

        if provider == 'anthropic':
            # Import here to avoid requiring anthropic package if not used
            from src.anthropic_client import AnthropicClient

            # Get API key from secrets manager
            api_key = None
            if secrets_manager:
                api_key = secrets_manager.get_anthropic_api_key()

            if not api_key:
                raise ValueError(
                    "Anthropic API key not found. Please add it to secrets.yaml "
                    "or set ANTHROPIC_API_KEY environment variable."
                )

            return AnthropicClient(
                model=model_config.model_name,
                api_key=api_key,
                timeout=model_config.timeout
            )

        elif provider == 'ollama':
            return OllamaClient(
                host=model_config.url,
                model=model_config.model_name,
                timeout=model_config.timeout
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def create_from_params(
        provider: str,
        url: str = "",
        model_name: str = "",
        timeout: int = 120,
        secrets_manager: Optional[SecretsManager] = None
    ) -> Union[OllamaClient, 'AnthropicClient']:
        """
        Create an LLM client directly from parameters (without ModelConfig).

        Args:
            provider: 'ollama' or 'anthropic'
            url: Service URL (for Ollama)
            model_name: Model name
            timeout: Request timeout
            secrets_manager: SecretsManager for API keys

        Returns:
            OllamaClient or AnthropicClient based on provider
        """
        if provider == 'anthropic':
            from src.anthropic_client import AnthropicClient

            api_key = None
            if secrets_manager:
                api_key = secrets_manager.get_anthropic_api_key()

            if not api_key:
                raise ValueError(
                    "Anthropic API key not found. Please add it to secrets.yaml "
                    "or set ANTHROPIC_API_KEY environment variable."
                )

            return AnthropicClient(
                model=model_name,
                api_key=api_key,
                timeout=timeout
            )

        elif provider == 'ollama':
            return OllamaClient(
                host=url,
                model=model_name,
                timeout=timeout
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")
