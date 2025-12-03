"""Session title generator using tinyollama for the AI CLI."""

import httpx
from typing import Optional

from src.sentry_config import capture_exception


class SessionTitleGenerator:
    """
    Generates session titles using tinyollama (local lightweight LLM).

    This class uses the local tinyollama model to generate a concise title
    for a session based on the first user prompt.
    """

    # Configuration constants
    MAX_PROMPT_LENGTH = 500  # Maximum characters of prompt to send for title generation
    MAX_TITLE_LENGTH = 50   # Maximum characters for generated title
    MAX_TOKENS = 60         # Maximum tokens for LLM response

    def __init__(self, ollama_url: str, model: str, timeout: int):
        """
        Initialize the session title generator.

        Args:
            ollama_url: URL of the ollama service (from config)
            model: Model name to use for title generation (from config)
            timeout: Request timeout in seconds
        """
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout

    def is_ollama_reachable(self) -> bool:
        """
        Check if the Ollama service is reachable.

        Returns:
            True if Ollama is reachable, False otherwise
        """
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.ollama_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            return False
        except Exception as e:
            capture_exception(e)
            return False

    def generate_title(self, first_prompt: str) -> Optional[str]:
        """
        Generate a session title based on the first user prompt.

        Args:
            first_prompt: The first user prompt in the session

        Returns:
            Generated title string, or None if generation failed
        """
        if not first_prompt or not first_prompt.strip():
            return None

        # Check if Ollama is reachable before attempting to generate title
        if not self.is_ollama_reachable():
            return None

        # Truncate very long prompts to avoid token limits
        truncated_prompt = first_prompt[:self.MAX_PROMPT_LENGTH] if len(first_prompt) > self.MAX_PROMPT_LENGTH else first_prompt

        # Create a simple prompt for title generation
        title_prompt = f"""Generate a short, descriptive title (maximum {self.MAX_TITLE_LENGTH} characters) for a conversation that starts with this user message:

"{truncated_prompt}"

Respond with ONLY the title, no quotes, no explanation. The title should be concise and capture the main topic."""

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": title_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": self.MAX_TOKENS
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    title = data.get('response', '').strip()

                    # Clean up the title
                    title = self._clean_title(title)

                    return title if title else None

                return None

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            # Silently fail - title generation is non-critical
            return None
        except Exception as e:
            capture_exception(e)
            return None

    def _clean_title(self, title: str) -> str:
        """
        Clean up the generated title.

        Args:
            title: Raw title from LLM

        Returns:
            Cleaned title string
        """
        if not title:
            return ""

        # Remove quotes if present
        title = title.strip('"\'')

        # Remove common prefixes LLM might add
        prefixes_to_remove = [
            "Title:",
            "title:",
            "Session:",
            "session:",
            "Topic:",
            "topic:",
        ]
        for prefix in prefixes_to_remove:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()

        # Truncate to max length if needed
        if len(title) > self.MAX_TITLE_LENGTH:
            title = title[:self.MAX_TITLE_LENGTH - 3] + "..."

        # If title is too short or just whitespace, return empty
        if len(title.strip()) < 3:
            return ""

        return title.strip()
