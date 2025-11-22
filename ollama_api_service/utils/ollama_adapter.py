"""
Adapter for Ollama client to match API expectations.

This adapter wraps the existing OllamaClient to provide additional methods
needed by the API routes, without modifying the CLI code.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import AsyncIterator, Dict, Any
import ollama


class OllamaAPIAdapter:
    """
    Adapter that wraps the Ollama Python library directly.

    This provides async methods and full API compatibility for the routes.
    """

    def __init__(self, base_url: str, timeout: int = 120):
        """Initialize the adapter with Ollama client."""
        self.base_url = base_url
        self.timeout = timeout
        self.client = ollama.Client(host=base_url, timeout=timeout)

    async def chat(
        self,
        model: str,
        messages: list,
        stream: bool = False,
        format: str = None,
        options: dict = None
    ) -> Dict[str, Any]:
        """
        Non-streaming chat request.
        """
        response = self.client.chat(
            model=model,
            messages=messages,
            stream=False,
            format=format,
            options=options or {}
        )
        return response

    async def chat_stream(
        self,
        model: str,
        messages: list,
        options: dict = None,
        format: str = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming chat request.
        """
        response = self.client.chat(
            model=model,
            messages=messages,
            stream=True,
            format=format,
            options=options or {}
        )

        for chunk in response:
            yield chunk

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = None,
        stream: bool = False,
        format: str = None,
        options: dict = None,
        images: list = None,
        context: list = None
    ) -> Dict[str, Any]:
        """
        Non-streaming generate request.
        """
        response = self.client.generate(
            model=model,
            prompt=prompt,
            system=system,
            stream=False,
            format=format,
            options=options or {},
            images=images,
            context=context
        )
        return response

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        system: str = None,
        options: dict = None,
        format: str = None,
        images: list = None,
        context: list = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming generate request.
        """
        response = self.client.generate(
            model=model,
            prompt=prompt,
            system=system,
            stream=True,
            format=format,
            options=options or {},
            images=images,
            context=context
        )

        for chunk in response:
            yield chunk

    async def list_models(self) -> Dict[str, Any]:
        """
        List available models.
        """
        response = self.client.list()

        # Convert to dict format if needed
        if isinstance(response, dict):
            return response
        else:
            # Convert ModelResponse object to dict
            models = getattr(response, 'models', [])
            models_list = []

            for model in models:
                if isinstance(model, dict):
                    models_list.append(model)
                else:
                    # Convert model object to dict
                    models_list.append({
                        'name': getattr(model, 'name', ''),
                        'modified_at': getattr(model, 'modified_at', ''),
                        'size': getattr(model, 'size', 0),
                        'digest': getattr(model, 'digest', ''),
                        'details': getattr(model, 'details', None)
                    })

            return {'models': models_list}
