"""Model registry manager for dynamic model configuration."""

import os
import redis
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from src.sentry_config import capture_exception


@dataclass
class ModelConfig:
    """Configuration for a dynamically registered model."""
    model_id: str          # Unique identifier
    model_type: str        # 'general' or 'coder'
    url: str               # Ollama service URL
    model_name: str        # Model name (e.g., 'llama3.1:8b')
    timeout: int           # Request timeout
    is_active: bool        # Whether this is the active model for its type
    added_at: str          # When the model was registered (ISO format)
    last_checked: Optional[str] = None  # Last availability check (ISO format)
    is_available: Optional[bool] = None  # Current availability status

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        """Create from dictionary retrieved from Redis."""
        return cls(**data)


class ModelRegistry:
    """Manages dynamic model registration with Redis persistence."""

    VALID_MODEL_TYPES = ['general', 'coder']

    def __init__(self, redis_host: str = None, redis_port: int = None):
        """
        Initialize the ModelRegistry.

        Args:
            redis_host: Redis host (defaults to env var or localhost)
            redis_port: Redis port (defaults to env var or 26379)
        """
        self.redis_host = redis_host or os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = redis_port or int(os.getenv('REDIS_HOST_PORT', '26379'))

        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self._redis_available = True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            self._redis_available = False
            # Fallback to in-memory storage
            self._memory_storage: Dict[str, Dict[str, Any]] = {}
            self._memory_active: Dict[str, str] = {}

    def _generate_model_id(self) -> str:
        """Generate a unique model ID."""
        return f"model_{uuid.uuid4().hex[:12]}"

    def _validate_model_type(self, model_type: str) -> bool:
        """Validate that model_type is valid."""
        return model_type in self.VALID_MODEL_TYPES

    def _get_active_key(self, model_type: str) -> str:
        """Get Redis key for active model of a type."""
        return f"models:{model_type}:active"

    def _get_model_key(self, model_id: str) -> str:
        """Get Redis key for a model's data."""
        return f"models:{model_id}"

    def _get_index_key(self, model_type: str) -> str:
        """Get Redis key for model type index."""
        return f"models:index:{model_type}"

    def add_model(
        self,
        model_type: str,
        url: str,
        model_name: str,
        timeout: int = 120,
        set_active: bool = True
    ) -> ModelConfig:
        """
        Add a new model to the registry.

        Args:
            model_type: Type of model ('general' or 'coder')
            url: Ollama service URL
            model_name: Name of the model
            timeout: Request timeout in seconds
            set_active: Whether to set this as the active model for its type

        Returns:
            The created ModelConfig

        Raises:
            ValueError: If model_type is invalid
        """
        if not self._validate_model_type(model_type):
            raise ValueError(f"Invalid model_type: {model_type}. Must be one of {self.VALID_MODEL_TYPES}")

        model_id = self._generate_model_id()
        now = datetime.now().isoformat()

        model_config = ModelConfig(
            model_id=model_id,
            model_type=model_type,
            url=url,
            model_name=model_name,
            timeout=timeout,
            is_active=set_active,
            added_at=now,
            last_checked=None,
            is_available=None
        )

        try:
            if self._redis_available:
                # Store model data (convert to Redis-compatible format)
                model_dict = model_config.to_dict()
                # Convert booleans and None to strings for Redis
                redis_dict = {}
                for key, value in model_dict.items():
                    if value is None:
                        redis_dict[key] = ''
                    elif isinstance(value, bool):
                        redis_dict[key] = str(value)
                    else:
                        redis_dict[key] = str(value)

                self.redis_client.hset(
                    self._get_model_key(model_id),
                    mapping=redis_dict
                )

                # Add to type index
                self.redis_client.sadd(self._get_index_key(model_type), model_id)

                # Set as active if requested
                if set_active:
                    self._set_active_internal(model_id, model_type)
            else:
                # In-memory fallback
                self._memory_storage[model_id] = model_config.to_dict()
                if set_active:
                    self._memory_active[model_type] = model_id

            return model_config
        except Exception as e:
            capture_exception(e)
            raise

    def _set_active_internal(self, model_id: str, model_type: str) -> None:
        """Internal method to set active model (updates is_active flags)."""
        if self._redis_available:
            # Get all models of this type
            model_ids = self.redis_client.smembers(self._get_index_key(model_type))

            # Deactivate all models of this type
            for mid in model_ids:
                self.redis_client.hset(self._get_model_key(mid), 'is_active', 'False')

            # Activate the specified model
            self.redis_client.hset(self._get_model_key(model_id), 'is_active', 'True')
            self.redis_client.set(self._get_active_key(model_type), model_id)
        else:
            # In-memory fallback
            for mid, data in self._memory_storage.items():
                if data['model_type'] == model_type:
                    data['is_active'] = False
            if model_id in self._memory_storage:
                self._memory_storage[model_id]['is_active'] = True
            self._memory_active[model_type] = model_id

    def remove_model(self, model_id: str) -> bool:
        """
        Remove a model from the registry.

        Args:
            model_id: ID of the model to remove

        Returns:
            True if model was removed, False if not found
        """
        try:
            if self._redis_available:
                # Get model data to find its type
                model_data = self.redis_client.hgetall(self._get_model_key(model_id))
                if not model_data:
                    return False

                model_type = model_data['model_type']

                # Remove from type index
                self.redis_client.srem(self._get_index_key(model_type), model_id)

                # Check if this was the active model
                was_active = model_data.get('is_active') == 'True'

                # Delete model data
                self.redis_client.delete(self._get_model_key(model_id))

                # If this was active, clear the active key
                if was_active:
                    self.redis_client.delete(self._get_active_key(model_type))

                return True
            else:
                # In-memory fallback
                if model_id not in self._memory_storage:
                    return False

                model_type = self._memory_storage[model_id]['model_type']
                was_active = self._memory_storage[model_id]['is_active']

                del self._memory_storage[model_id]

                if was_active and model_type in self._memory_active:
                    del self._memory_active[model_type]

                return True
        except Exception as e:
            capture_exception(e)
            return False

    def list_models(self, model_type: str = None) -> List[ModelConfig]:
        """
        List all models, optionally filtered by type.

        Args:
            model_type: Optional filter by model type

        Returns:
            List of ModelConfig objects
        """
        try:
            models = []

            if self._redis_available:
                if model_type:
                    # Get models of specific type
                    model_ids = self.redis_client.smembers(self._get_index_key(model_type))
                else:
                    # Get all models
                    model_ids = []
                    for mtype in self.VALID_MODEL_TYPES:
                        model_ids.extend(self.redis_client.smembers(self._get_index_key(mtype)))

                for model_id in model_ids:
                    model_data = self.redis_client.hgetall(self._get_model_key(model_id))
                    if model_data:
                        # Convert string booleans to actual booleans
                        model_data['is_active'] = model_data['is_active'] == 'True'
                        # Handle is_available (empty string = None)
                        if model_data.get('is_available') == '':
                            model_data['is_available'] = None
                        elif model_data.get('is_available') is not None:
                            model_data['is_available'] = model_data['is_available'] == 'True'
                        # Handle last_checked (empty string = None)
                        if model_data.get('last_checked') == '':
                            model_data['last_checked'] = None
                        model_data['timeout'] = int(model_data['timeout'])
                        models.append(ModelConfig.from_dict(model_data))
            else:
                # In-memory fallback
                for model_data in self._memory_storage.values():
                    if model_type is None or model_data['model_type'] == model_type:
                        models.append(ModelConfig.from_dict(model_data))

            return models
        except Exception as e:
            capture_exception(e)
            return []

    def get_active_model(self, model_type: str) -> Optional[ModelConfig]:
        """
        Get the active model for a specific type.

        Args:
            model_type: Type of model ('general' or 'coder')

        Returns:
            ModelConfig if an active model exists, None otherwise
        """
        if not self._validate_model_type(model_type):
            return None

        try:
            if self._redis_available:
                # Get active model ID
                model_id = self.redis_client.get(self._get_active_key(model_type))
                if not model_id:
                    return None

                # Get model data
                model_data = self.redis_client.hgetall(self._get_model_key(model_id))
                if not model_data:
                    return None

                # Convert string booleans to actual booleans
                model_data['is_active'] = model_data['is_active'] == 'True'
                # Handle is_available (empty string = None)
                if model_data.get('is_available') == '':
                    model_data['is_available'] = None
                elif model_data.get('is_available') is not None:
                    model_data['is_available'] = model_data['is_available'] == 'True'
                # Handle last_checked (empty string = None)
                if model_data.get('last_checked') == '':
                    model_data['last_checked'] = None
                model_data['timeout'] = int(model_data['timeout'])

                return ModelConfig.from_dict(model_data)
            else:
                # In-memory fallback
                model_id = self._memory_active.get(model_type)
                if model_id and model_id in self._memory_storage:
                    return ModelConfig.from_dict(self._memory_storage[model_id])
                return None
        except Exception as e:
            capture_exception(e)
            return None

    def set_active_model(self, model_id: str) -> bool:
        """
        Set a model as the active model for its type.

        Args:
            model_id: ID of the model to activate

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._redis_available:
                # Get model data
                model_data = self.redis_client.hgetall(self._get_model_key(model_id))
                if not model_data:
                    return False

                model_type = model_data['model_type']
                self._set_active_internal(model_id, model_type)
                return True
            else:
                # In-memory fallback
                if model_id not in self._memory_storage:
                    return False

                model_type = self._memory_storage[model_id]['model_type']
                self._set_active_internal(model_id, model_type)
                return True
        except Exception as e:
            capture_exception(e)
            return False

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """
        Get a specific model by ID.

        Args:
            model_id: ID of the model

        Returns:
            ModelConfig if found, None otherwise
        """
        try:
            if self._redis_available:
                model_data = self.redis_client.hgetall(self._get_model_key(model_id))
                if not model_data:
                    return None

                # Convert string booleans to actual booleans
                model_data['is_active'] = model_data['is_active'] == 'True'
                # Handle is_available (empty string = None)
                if model_data.get('is_available') == '':
                    model_data['is_available'] = None
                elif model_data.get('is_available') is not None:
                    model_data['is_available'] = model_data['is_available'] == 'True'
                # Handle last_checked (empty string = None)
                if model_data.get('last_checked') == '':
                    model_data['last_checked'] = None
                model_data['timeout'] = int(model_data['timeout'])

                return ModelConfig.from_dict(model_data)
            else:
                # In-memory fallback
                if model_id in self._memory_storage:
                    return ModelConfig.from_dict(self._memory_storage[model_id])
                return None
        except Exception as e:
            capture_exception(e)
            return None

    def update_availability(self, model_id: str, is_available: bool) -> bool:
        """
        Update the availability status of a model.

        Args:
            model_id: ID of the model
            is_available: Whether the model is currently available

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now().isoformat()

            if self._redis_available:
                # Check if model exists
                if not self.redis_client.exists(self._get_model_key(model_id)):
                    return False

                self.redis_client.hset(
                    self._get_model_key(model_id),
                    mapping={
                        'is_available': str(is_available),
                        'last_checked': now
                    }
                )
                return True
            else:
                # In-memory fallback
                if model_id not in self._memory_storage:
                    return False

                self._memory_storage[model_id]['is_available'] = is_available
                self._memory_storage[model_id]['last_checked'] = now
                return True
        except Exception as e:
            capture_exception(e)
            return False

    def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis_available

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about the model registry.

        Returns:
            Dictionary with status information
        """
        status = {
            'redis_available': self._redis_available,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'models': {}
        }

        for model_type in self.VALID_MODEL_TYPES:
            active_model = self.get_active_model(model_type)
            all_models = self.list_models(model_type)

            status['models'][model_type] = {
                'active': active_model.to_dict() if active_model else None,
                'count': len(all_models),
                'all': [m.to_dict() for m in all_models]
            }

        return status
