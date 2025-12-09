"""Anthropic client adapter matching OllamaClient interface."""

from typing import List, Dict, Any, Generator, Optional

from src.sentry_config import capture_exception


class AnthropicClient:
    """
    Client for interacting with the Anthropic API.

    This client provides the same interface as OllamaClient, converting
    between Ollama-style message formats and Anthropic's API format.
    """

    def __init__(self, model: str, api_key: str = None, timeout: int = 120):
        """
        Initialize the Anthropic client.

        Args:
            model: Anthropic model name (e.g., 'claude-sonnet-4-20250514')
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env if not provided)
            timeout: Request timeout in seconds
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for Anthropic models. "
                "Install it with: pip install anthropic"
            )

        self.model = model
        self.timeout = timeout
        self.host = "https://api.anthropic.com"  # For compatibility with OllamaClient interface

        # Initialize Anthropic client
        # If api_key is None, Anthropic will look for ANTHROPIC_API_KEY env var
        self.client = Anthropic(
            api_key=api_key,
            timeout=float(timeout)
        )

    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple:
        """
        Convert Ollama-style messages to Anthropic format.

        Anthropic expects system prompt as a separate parameter,
        not as a message with role='system'.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Tuple of (system_prompt, anthropic_messages)
        """
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'system':
                # Collect system messages into system prompt
                if system_prompt:
                    system_prompt += "\n\n" + content
                else:
                    system_prompt = content
            else:
                # Map 'assistant' and 'user' roles directly
                anthropic_messages.append({
                    'role': role,
                    'content': content
                })

        return system_prompt, anthropic_messages

    def _convert_response(self, response) -> Dict[str, Any]:
        """
        Convert Anthropic response to Ollama-compatible format.

        Args:
            response: Anthropic Message response object

        Returns:
            Dict in Ollama format: {'message': {'role': 'assistant', 'content': '...'}}
        """
        # Extract text from content blocks
        content_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content_text += block.text

        return {
            'message': {
                'role': 'assistant',
                'content': content_text
            },
            'model': response.model,
            'done': True
        }

    def _stream_response(self, stream) -> Generator[str, None, None]:
        """
        Convert Anthropic stream to yield content strings.

        Yields content chunks in the same format as OllamaClient._stream_response.

        Args:
            stream: Anthropic MessageStream object

        Yields:
            String chunks of the response content
        """
        try:
            with stream as s:
                for event in s:
                    # Handle different event types
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_delta':
                            if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                                yield event.delta.text
                        elif event.type == 'message_delta':
                            # End of message, nothing to yield
                            pass
        except Exception as e:
            capture_exception(e)
            raise Exception(f"Error streaming from Anthropic: {str(e)}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        temperature: float = 0.7,
        num_predict: int = None,
        model: str = None
    ) -> Generator[str, None, None] | Dict[str, Any]:
        """
        Send a chat request to Anthropic.

        This method matches the OllamaClient.chat() interface.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            stream: Whether to stream the response
            temperature: Temperature for response generation
            num_predict: Maximum number of tokens to predict (maps to max_tokens)
            model: Override the default model for this request

        Returns:
            Generator of response chunks if streaming, otherwise complete response
        """
        try:
            # Convert messages to Anthropic format
            system_prompt, anthropic_messages = self._convert_messages(messages)

            # Use provided model or fall back to default
            use_model = model if model else self.model

            # Anthropic requires max_tokens, default to 4096 if not specified
            max_tokens = num_predict if num_predict else 4096

            if stream:
                # Create streaming response
                response = self.client.messages.stream(
                    model=use_model,
                    system=system_prompt if system_prompt else None,
                    messages=anthropic_messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return self._stream_response(response)
            else:
                # Create non-streaming response
                response = self.client.messages.create(
                    model=use_model,
                    system=system_prompt if system_prompt else None,
                    messages=anthropic_messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return self._convert_response(response)

        except Exception as e:
            capture_exception(e)
            raise Exception(f"Error communicating with Anthropic: {str(e)}")

    def list_models(self) -> List[str]:
        """
        List available Anthropic models.

        Note: Unlike Ollama, Anthropic doesn't have a models list API.
        Returns a static list of commonly available models.

        Returns:
            List of model names
        """
        # Anthropic doesn't have a list models API, return known models
        return [
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
