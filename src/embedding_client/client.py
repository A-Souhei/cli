"""EmbeddingClient - Abstraction for embedding services with fallback support."""

import os
import requests
import warnings
import numpy as np
from typing import List, Optional, Dict, Any

from src.sentry_config import capture_exception
from src.model_registry.manager import ModelRegistry


class EmbeddingClient:
    """
    Client for embedding generation with support for external services and local fallback.
    
    Automatically falls back to local transformer service when no external model is configured.
    Auto-detects embedding dimensions on first successful call.
    """

    def __init__(self, model_registry: ModelRegistry, fallback_url: str = None):
        """
        Initialize the EmbeddingClient.

        Args:
            model_registry: ModelRegistry instance for accessing embedding model configuration
            fallback_url: URL of local transformer service (defaults to env var or localhost:16050)
        """
        self.model_registry = model_registry
        self.fallback_url = fallback_url or os.getenv('TRANSFORMER_API_URL', 'http://localhost:16050')
        self._last_dimensions = None

    def _get_active_embedding_config(self) -> Optional[tuple]:
        """
        Get active embedding model configuration.

        Returns:
            Tuple of (url, timeout, dimensions) if active model exists, None otherwise
        """
        active_model = self.model_registry.get_active_embedding_model()
        if active_model:
            return (active_model.url, active_model.timeout, active_model.embedding_dimensions)
        return None

    def _call_external_service(self, url: str, timeout: int, texts: List[str]) -> Dict[str, Any]:
        """
        Call external embedding service.

        Args:
            url: Service URL
            timeout: Request timeout
            texts: List of texts to embed

        Returns:
            Response dictionary with 'embeddings' and optionally 'dimensions'

        Raises:
            requests.RequestException: If the request fails
        """
        try:
            # Support both batch and single text
            if len(texts) == 1:
                payload = {'text': texts[0]}
            else:
                payload = {'texts': texts}

            response = requests.post(
                f"{url}/embed",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()

            # Handle both single and batch responses
            if 'embedding' in data:
                embeddings = [data['embedding']]
            elif 'embeddings' in data:
                embeddings = data['embeddings']
            else:
                raise ValueError("Response missing 'embedding' or 'embeddings' field")

            return {
                'embeddings': embeddings,
                'dimensions': data.get('dimensions')
            }
        except Exception as e:
            capture_exception(e)
            raise

    def _call_local_service(self, texts: List[str]) -> Dict[str, Any]:
        """
        Call local transformer service (fallback).

        Args:
            texts: List of texts to embed

        Returns:
            Response dictionary with 'embeddings' and 'dimensions'

        Raises:
            requests.RequestException: If the request fails
        """
        try:
            embeddings = []
            dimensions = None

            for text in texts:
                response = requests.get(
                    f"{self.fallback_url}/embed",
                    params={'text': text},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                if data.get('status') == 'success':
                    embeddings.append(data['embedding'])
                    if dimensions is None:
                        dimensions = data.get('dimension')
                else:
                    raise ValueError(f"Local service returned error: {data.get('message')}")

            return {
                'embeddings': embeddings,
                'dimensions': dimensions
            }
        except Exception as e:
            capture_exception(e)
            raise

    def _auto_detect_dimensions(self, model_id: str, embedding: List[float]) -> int:
        """
        Auto-detect and store embedding dimensions.

        Args:
            model_id: Model ID to update
            embedding: Sample embedding vector

        Returns:
            Number of dimensions
        """
        dimensions = len(embedding)
        
        # Store dimensions in model registry
        self.model_registry.set_embedding_dimensions(model_id, dimensions)
        
        # Cache for quick access
        self._last_dimensions = dimensions
        
        return dimensions

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            RuntimeError: If both external service and fallback fail
        """
        embeddings = self.embed_batch([text])
        return embeddings[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If both external service and fallback fail
        """
        if not texts:
            return []

        # Try external service first
        config = self._get_active_embedding_config()
        
        if config:
            url, timeout, stored_dimensions = config
            try:
                result = self._call_external_service(url, timeout, texts)
                embeddings = result['embeddings']
                
                # Auto-detect dimensions on first call if not set
                if stored_dimensions is None and embeddings and len(embeddings) > 0:
                    active_model = self.model_registry.get_active_embedding_model()
                    if active_model:
                        detected_dims = self._auto_detect_dimensions(active_model.model_id, embeddings[0])
                        print(f"Auto-detected embedding dimensions: {detected_dims}")
                
                # Warn if dimensions changed
                elif stored_dimensions and embeddings and len(embeddings) > 0:
                    actual_dims = len(embeddings[0])
                    if actual_dims != stored_dimensions:
                        warnings.warn(
                            f"Embedding dimension mismatch! Expected {stored_dimensions}, got {actual_dims}. "
                            f"This may cause issues with existing stored embeddings.",
                            RuntimeWarning
                        )
                
                return embeddings
                
            except Exception as e:
                # Silently fall through to fallback - this is expected behavior
                # when external service is unavailable
                capture_exception(e)

        # Fallback to local transformer service
        try:
            result = self._call_local_service(texts)
            embeddings = result['embeddings']
            
            # Cache dimensions from local service
            if result['dimensions']:
                self._last_dimensions = result['dimensions']
            
            return embeddings
            
        except Exception as e:
            error_msg = f"Both external and local embedding services failed: {e}"
            capture_exception(e)
            raise RuntimeError(error_msg)

    def get_similarity(self, text1: str, text2: str, metric: str = "cosine") -> float:
        """
        Calculate similarity between two texts.

        Args:
            text1: First text
            text2: Second text
            metric: Similarity metric ('cosine', 'euclidean', 'dot')

        Returns:
            Similarity score

        Raises:
            ValueError: If metric is not supported
            RuntimeError: If embedding generation fails
        """
        # Generate embeddings for both texts
        embeddings = self.embed_batch([text1, text2])
        emb1, emb2 = embeddings[0], embeddings[1]

        # Calculate similarity based on metric
        if metric == "cosine":
            # Cosine similarity
            emb1_arr = np.array(emb1)
            emb2_arr = np.array(emb2)
            
            dot_product = np.dot(emb1_arr, emb2_arr)
            norm1 = np.linalg.norm(emb1_arr)
            norm2 = np.linalg.norm(emb2_arr)
            
            return float(dot_product / (norm1 * norm2))
            
        elif metric == "euclidean":
            # Euclidean distance (inverted for similarity)
            emb1_arr = np.array(emb1)
            emb2_arr = np.array(emb2)
            distance = np.linalg.norm(emb1_arr - emb2_arr)
            # Convert distance to similarity (0-1 range, higher is more similar)
            return float(1 / (1 + distance))
            
        elif metric == "dot":
            # Dot product
            return float(np.dot(emb1, emb2))
            
        else:
            raise ValueError(f"Unsupported metric: {metric}. Use 'cosine', 'euclidean', or 'dot'")

    def get_dimensions(self) -> Optional[int]:
        """
        Get embedding dimensions.

        Returns:
            Number of dimensions if known, None otherwise
        """
        # Try to get from active model
        config = self._get_active_embedding_config()
        if config and config[2] is not None:
            return config[2]
        
        # Return cached value if available
        return self._last_dimensions

    def is_using_fallback(self) -> bool:
        """
        Check if client is using fallback (local transformer) service.

        Returns:
            True if using fallback, False if using external service
        """
        return self._get_active_embedding_config() is None
