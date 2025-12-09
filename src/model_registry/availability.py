"""Model availability checker for dynamic models and fallback logic."""

import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from src.sentry_config import capture_exception
from src.model_registry.manager import ModelRegistry, ModelConfig


@dataclass
class LLMConfig:
    """Configuration for an LLM service (compatibility with existing code)."""
    url: str
    model: str
    timeout: int
    is_tinyollama: bool = False
    disabled_features: List[str] = field(default_factory=list)
    provider: str = "ollama"  # 'ollama' or 'anthropic'


class ModelAvailabilityChecker:
    """
    Checks model availability and provides fallback logic.

    This class integrates with ModelRegistry for dynamic models
    and falls back to tinyollama if needed.
    """

    def __init__(self, config_manager, model_registry: ModelRegistry = None, secrets_manager=None):
        """
        Initialize the model availability checker.

        Args:
            config_manager: ConfigManager instance with loaded configuration
            model_registry: Optional ModelRegistry instance
            secrets_manager: Optional SecretsManager for API keys (needed for Anthropic)
        """
        self.config = config_manager
        self.model_registry = model_registry or ModelRegistry()
        self.secrets_manager = secrets_manager
        self._active_llm: Optional[LLMConfig] = None

    def check_ollama_available(self, url: str, timeout: int = 5) -> bool:
        """
        Check if an Ollama service is reachable.

        Args:
            url: Ollama service URL
            timeout: Connection timeout in seconds

        Returns:
            True if service is reachable, False otherwise
        """
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            return False
        except Exception as e:
            capture_exception(e)
            return False

    def check_anthropic_available(self, api_key: str = None, timeout: int = 5) -> bool:
        """
        Check if Anthropic API is accessible with valid credentials.

        Args:
            api_key: Anthropic API key (uses env var if not provided)
            timeout: Connection timeout in seconds

        Returns:
            True if API is accessible, False otherwise
        """
        # Import at top level of method to avoid scoping issues in exception handlers
        try:
            from anthropic import Anthropic
            from anthropic import AuthenticationError as AnthropicAuthError
            from anthropic import APIConnectionError as AnthropicAPIError
            from anthropic import BadRequestError as AnthropicBadRequestError
        except ImportError:
            # anthropic package not installed
            return False

        try:
            # Create client (uses ANTHROPIC_API_KEY env var if api_key is None)
            client = Anthropic(api_key=api_key, timeout=float(timeout))

            # Try a minimal API call to verify credentials
            # Using messages.create with max_tokens=1 to minimize cost
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            return True

        except AnthropicAuthError:
            # Invalid API key
            return False
        except AnthropicAPIError:
            # Network issues
            return False
        except AnthropicBadRequestError:
            # API key is valid but request had issues - still means API is accessible
            return True
        except Exception as e:
            capture_exception(e)
            return False

    def check_model_availability(self, model_id: str, secrets_manager=None) -> bool:
        """
        Check if a specific model is available and update its status.

        Args:
            model_id: ID of the model to check
            secrets_manager: SecretsManager for API keys (needed for Anthropic).
                           Falls back to self.secrets_manager if not provided.

        Returns:
            True if model is available, False otherwise
        """
        model = self.model_registry.get_model(model_id)
        if not model:
            return False

        provider = getattr(model, 'provider', 'ollama')

        if provider == 'anthropic':
            # Get API key from secrets manager (use provided or fall back to instance)
            sm = secrets_manager or self.secrets_manager
            api_key = None
            if sm:
                api_key = sm.get_anthropic_api_key()
            is_available = self.check_anthropic_available(api_key=api_key, timeout=5)
        else:
            # Default to Ollama
            is_available = self.check_ollama_available(model.url, timeout=5)

        self.model_registry.update_availability(model_id, is_available)
        return is_available

    def get_available_model(self, model_type: str, force_recheck: bool = False) -> Optional[ModelConfig]:
        """
        Get the active model for a type if it's available.

        Args:
            model_type: Type of model ('general' or 'coder')
            force_recheck: Force availability recheck

        Returns:
            ModelConfig if available, None otherwise
        """
        active_model = self.model_registry.get_active_model(model_type)
        if not active_model:
            return None

        # Check availability if forced or not previously checked
        if force_recheck or active_model.is_available is None:
            is_available = self.check_model_availability(active_model.model_id)
            if not is_available:
                return None
            # Get updated model with availability status
            active_model = self.model_registry.get_model(active_model.model_id)
            if not active_model:
                return None

        # Return if available (or if we just checked and it's available)
        if active_model.is_available is True:
            return active_model
        elif active_model.is_available is None:
            # Not checked yet, check now
            is_available = self.check_model_availability(active_model.model_id)
            if is_available:
                # Get updated model
                return self.model_registry.get_model(active_model.model_id)

        return None

    def get_available_llm(self, force_recheck: bool = False) -> LLMConfig:
        """
        Get the best available LLM configuration (backward compatibility).

        Tries dynamic general model first, falls back to tinyollama if not reachable.

        Args:
            force_recheck: Force recheck even if already cached

        Returns:
            LLMConfig for the available LLM
        """
        if self._active_llm is not None and not force_recheck:
            return self._active_llm

        # Try dynamic general model first
        general_model = self.get_available_model('general', force_recheck=force_recheck)
        if general_model:
            provider = getattr(general_model, 'provider', 'ollama')
            self._active_llm = LLMConfig(
                url=general_model.url,
                model=general_model.model_name,
                timeout=general_model.timeout,
                is_tinyollama=False,
                disabled_features=[],
                provider=provider
            )
            return self._active_llm

        # Fall back to tinyollama if configured
        if self.config.has_tinyollama_config():
            tinyollama_url = self.config.get_tinyollama_url()
            if self.check_ollama_available(tinyollama_url):
                self._active_llm = LLMConfig(
                    url=tinyollama_url,
                    model=self.config.get_tinyollama_model(),
                    timeout=self.config.get_tinyollama_timeout(),
                    is_tinyollama=True,
                    disabled_features=self.config.get_tinyollama_disabled_features()
                )
                return self._active_llm

        # If nothing is available, return None config
        # (graceful degradation - CLI won't exit)
        self._active_llm = LLMConfig(
            url='',
            model='',
            timeout=120,
            is_tinyollama=False,
            disabled_features=['all']  # Disable everything
        )
        return self._active_llm

    def is_using_tinyollama(self) -> bool:
        """Check if currently using tinyollama fallback."""
        if self._active_llm is None:
            self.get_available_llm()
        return self._active_llm.is_tinyollama if self._active_llm else False

    def is_feature_disabled(self, feature: str) -> bool:
        """
        Check if a feature is disabled for the current LLM.

        Args:
            feature: Feature name to check (e.g., 'code_mode', 'coder_model')

        Returns:
            True if feature is disabled, False otherwise
        """
        if self._active_llm is None:
            self.get_available_llm()
        return feature in self._active_llm.disabled_features if self._active_llm else True

    def has_general_model(self) -> bool:
        """Check if a general model is available."""
        return self.get_available_model('general') is not None

    def has_coder_model(self) -> bool:
        """Check if a coder model is available."""
        return self.get_available_model('coder') is not None

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about current model configuration.

        Returns:
            Dictionary with status information
        """
        general_model = self.get_available_model('general')
        coder_model = self.get_available_model('coder')
        embedding_model = self.model_registry.get_active_embedding_model()

        status = {
            'general_model': general_model.to_dict() if general_model else None,
            'coder_model': coder_model.to_dict() if coder_model else None,
            'embedding_model': embedding_model.to_dict() if embedding_model else None,
            'tinyollama_available': False,
            'registry_status': self.model_registry.get_status()
        }

        # Check tinyollama availability
        if self.config.has_tinyollama_config():
            tinyollama_url = self.config.get_tinyollama_url()
            status['tinyollama_available'] = self.check_ollama_available(tinyollama_url)
            status['tinyollama_config'] = {
                'url': tinyollama_url,
                'model': self.config.get_tinyollama_model()
            }

        return status

    def reset(self):
        """Reset cached LLM configuration, forcing recheck on next use."""
        self._active_llm = None
