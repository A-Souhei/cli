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

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "tinyllama",
        timeout: int = 30
    ):
        """
        Initialize the session title generator.

        Args:
            ollama_url: URL of the ollama service
            model: Model name to use for title generation
            timeout: Request timeout in seconds
        """
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout

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

        # Truncate very long prompts to avoid token limits
        truncated_prompt = first_prompt[:500] if len(first_prompt) > 500 else first_prompt

        # Create a simple prompt for title generation
        title_prompt = f"""Generate a short, descriptive title (maximum 50 characters) for a conversation that starts with this user message:

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
                            "num_predict": 60  # Short response for title
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

        # Truncate to 50 characters if needed
        if len(title) > 50:
            title = title[:47] + "..."

        # If title is too short or just whitespace, return empty
        if len(title.strip()) < 3:
            return ""

        return title.strip()
