"""Ollama client for interacting with the Ollama service."""

import ollama
from typing import List, Dict, Any, Generator


class OllamaClient:
    """Client for interacting with the Ollama service."""
    
    def __init__(self, host: str, model: str, timeout: int = 120):
        """
        Initialize the Ollama client.
        
        Args:
            host: Ollama service URL
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.host = host
        self.model = model
        self.timeout = timeout
        self.client = ollama.Client(host=host, timeout=timeout)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        temperature: float = 0.7
    ) -> Generator[str, None, None] | Dict[str, Any]:
        """
        Send a chat request to Ollama.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            stream: Whether to stream the response
            temperature: Temperature for response generation
        
        Returns:
            Generator of response chunks if streaming, otherwise complete response
        """
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                stream=stream,
                options={'temperature': temperature}
            )
            
            if stream:
                for chunk in response:
                    if 'message' in chunk and 'content' in chunk['message']:
                        yield chunk['message']['content']
            else:
                return response
                
        except Exception as e:
            raise Exception(f"Error communicating with Ollama: {str(e)}")
    
    def list_models(self) -> List[str]:
        """
        List available models from Ollama.
        
        Returns:
            List of model names
        """
        try:
            response = self.client.list()
            # Handle both dict response and ModelResponse object
            if isinstance(response, dict):
                models = response.get('models', [])
            else:
                models = getattr(response, 'models', [])
            
            # Extract model names, handling both dict and object formats
            result = []
            for model in models:
                if isinstance(model, dict):
                    name = model.get('name', model.get('model', ''))
                else:
                    name = getattr(model, 'name', getattr(model, 'model', ''))
                if name:
                    result.append(name)
            return result
        except Exception as e:
            raise Exception(f"Error listing models: {str(e)}")
