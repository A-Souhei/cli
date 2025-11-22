"""Anthropic client for interacting with Claude models."""

import anthropic
from typing import List, Dict, Any, Generator


class AnthropicClient:
    """Client for interacting with Anthropic Claude models."""

    # Available Claude models
    AVAILABLE_MODELS = [
        "claude-sonnet-4-5-20250929",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    def __init__(self, api_key: str, model: str, timeout: int = 120):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        temperature: float = 0.7
    ) -> Generator[str, None, None] | Dict[str, Any]:
        """
        Send a chat request to Anthropic Claude.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            stream: Whether to stream the response
            temperature: Temperature for response generation

        Returns:
            Generator of response chunks if streaming, otherwise complete response
        """
        try:
            # Extract system message if present (Anthropic uses separate system parameter)
            system_message = None
            api_messages = []

            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    api_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            # Prepare request parameters
            request_params = {
                'model': self.model,
                'messages': api_messages,
                'max_tokens': 4096,
                'temperature': temperature,
            }

            if system_message:
                request_params['system'] = system_message

            if stream:
                # Streaming response
                with self.client.messages.stream(**request_params) as stream:
                    for text in stream.text_stream:
                        yield text
            else:
                # Non-streaming response
                response = self.client.messages.create(**request_params)
                return {
                    'message': {
                        'role': 'assistant',
                        'content': response.content[0].text
                    }
                }

        except Exception as e:
            raise Exception(f"Error communicating with Anthropic: {str(e)}")

    def list_models(self) -> List[str]:
        """
        List available Claude models.

        Returns:
            List of model names
        """
        return self.AVAILABLE_MODELS.copy()
