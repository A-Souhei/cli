"""LLM availability checker and fallback logic for the AI CLI."""

import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from src.sentry_config import capture_exception


@dataclass
class LLMConfig:
    """Configuration for an LLM service."""
    url: str
    model: str
    timeout: int
    is_tinyollama: bool = False
    disabled_features: List[str] = field(default_factory=list)


class LLMAvailabilityChecker:
    """
    Checks LLM availability and provides fallback logic.

    This class manages checking if the remote ollama server is reachable,
    and falls back to local tinyollama if not.
    """

    def __init__(self, config_manager):
        """
        Initialize the LLM availability checker.

        Args:
            config_manager: ConfigManager instance with loaded configuration
        """
        self.config = config_manager
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

    def get_available_llm(self, force_recheck: bool = False) -> LLMConfig:
        """
        Get the best available LLM configuration.

        Tries primary ollama first, falls back to tinyollama if not reachable.

        Args:
            force_recheck: Force recheck even if already cached

        Returns:
            LLMConfig for the available LLM
        """
        if self._active_llm is not None and not force_recheck:
            return self._active_llm

        # Try primary ollama first
        primary_url = self.config.get_ollama_url()
        if self.check_ollama_available(primary_url):
            self._active_llm = LLMConfig(
                url=primary_url,
                model=self.config.get_ollama_model(),
                timeout=self.config.get_ollama_timeout(),
                is_tinyollama=False,
                disabled_features=[]
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

        # If nothing is available, return primary config anyway
        # (will fail on first use, but that's expected behavior)
        self._active_llm = LLMConfig(
            url=primary_url,
            model=self.config.get_ollama_model(),
            timeout=self.config.get_ollama_timeout(),
            is_tinyollama=False,
            disabled_features=[]
        )
        return self._active_llm

    def is_using_tinyollama(self) -> bool:
        """Check if currently using tinyollama fallback."""
        if self._active_llm is None:
            self.get_available_llm()
        return self._active_llm.is_tinyollama

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
        return feature in self._active_llm.disabled_features

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about current LLM configuration.

        Returns:
            Dictionary with status information
        """
        if self._active_llm is None:
            self.get_available_llm()

        return {
            'url': self._active_llm.url,
            'model': self._active_llm.model,
            'is_tinyollama': self._active_llm.is_tinyollama,
            'disabled_features': self._active_llm.disabled_features,
            'timeout': self._active_llm.timeout
        }

    def reset(self):
        """Reset cached LLM configuration, forcing recheck on next use."""
        self._active_llm = None
