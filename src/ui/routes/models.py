"""
Model management API routes for the UI.

Provides endpoints for:
- Listing registered models
- Adding new models
- Removing models
- Setting active models
- Checking model status
"""

from flask import Blueprint, jsonify, request
from src.model_registry import ModelRegistry
from src.model_registry.availability import ModelAvailabilityChecker
from src.config.manager import ConfigManager
from src.sentry_config import capture_exception

models_bp = Blueprint('models', __name__)


@models_bp.route('/status', methods=['GET'])
def get_model_status():
    """
    Get status of all registered models.

    Returns:
        JSON with general, coder, and fallback model status
    """
    try:
        config = ConfigManager()
        registry = ModelRegistry()
        checker = ModelAvailabilityChecker(config, registry)

        status = checker.get_status()

        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/list', methods=['GET'])
def list_models():
    """
    List all registered models.

    Query params:
        type: Optional filter by model type ('general', 'coder', or 'embedding')
    """
    try:
        registry = ModelRegistry()
        model_type = request.args.get('type')

        models = registry.list_models(model_type)

        return jsonify({
            'status': 'success',
            'models': [m.to_dict() for m in models]
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/add', methods=['POST'])
def add_model():
    """
    Add a new model to the registry.

    Request body:
        model_type: Type of model ('general', 'coder', or 'embedding')
        url: Ollama service URL (or embedding service URL for embedding type)
        model_name: Name of the model (not required for embedding type)
        timeout: Optional timeout in seconds (default: 120 for general/coder, 60 for embedding)
        set_active: Optional whether to set as active (default: true)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400

        model_type = data.get('model_type')
        url = data.get('url')
        model_name = data.get('model_name', '')
        timeout = data.get('timeout')
        set_active = data.get('set_active', True)

        # Initialize registry early
        registry = ModelRegistry()

        # Set default timeout based on model type
        if timeout is None:
            timeout = 60 if model_type == 'embedding' else 120

        # Validate required fields
        if not model_type or not url:
            return jsonify({
                'status': 'error',
                'message': 'model_type and url are required'
            }), 400

        # For non-embedding models, model_name is required
        if model_type in ['general', 'coder'] and not model_name:
            return jsonify({
                'status': 'error',
                'message': 'model_name is required for general and coder models'
            }), 400

        # Validate URL format and scheme
        from urllib.parse import urlparse
        try:
            parsed_url = urlparse(url)
            if parsed_url.scheme not in ['http', 'https']:
                return jsonify({
                    'status': 'error',
                    'message': 'URL must use http or https scheme'
                }), 400
            if not parsed_url.netloc:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid URL format'
                }), 400
        except Exception:
            return jsonify({
                'status': 'error',
                'message': 'Invalid URL format'
            }), 400

        # Validate timeout range (10-600 seconds)
        try:
            timeout = int(timeout)
            if timeout < 10 or timeout > 600:
                return jsonify({
                    'status': 'error',
                    'message': 'Timeout must be between 10 and 600 seconds'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'status': 'error',
                'message': 'Timeout must be a valid integer'
            }), 400

        # For embedding models, test the service
        if model_type == 'embedding':
            import requests as req
            try:
                test_response = req.post(
                    f"{url}/embed",
                    json={"text": "test"},
                    timeout=10
                )
                if test_response.status_code != 200:
                    return jsonify({
                        'status': 'error',
                        'message': f'Embedding service returned status {test_response.status_code}'
                    }), 400
                
                test_data = test_response.json()
                if 'embedding' not in test_data and 'embeddings' not in test_data:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid response format from embedding service'
                    }), 400
                
                # Auto-detect dimensions
                embedding = None
                if 'embedding' in test_data:
                    embedding = test_data['embedding']
                elif 'embeddings' in test_data and test_data['embeddings']:
                    embedding = test_data['embeddings'][0]
                
                dimensions = len(embedding) if (embedding and isinstance(embedding, list) and len(embedding) > 0) else None
                
                # Add embedding model with dimensions
                model = registry.add_model(
                    model_type=model_type,
                    url=url,
                    model_name='',  # Empty for embedding models
                    timeout=timeout,
                    set_active=set_active,
                    embedding_dimensions=dimensions
                )
                
                return jsonify({
                    'status': 'success',
                    'model': model.to_dict(),
                    'message': f'Embedding service added successfully (dimensions: {dimensions})'
                })
                
            except req.exceptions.RequestException as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Cannot reach embedding service at {url}'
                }), 400
        else:
            # Check availability for general/coder models
            config = ConfigManager()
            checker = ModelAvailabilityChecker(config, registry)

            if not checker.check_ollama_available(url):
                return jsonify({
                    'status': 'error',
                    'message': f'Cannot reach Ollama service at {url}'
                }), 400

            # Add model
            model = registry.add_model(
                model_type=model_type,
                url=url,
                model_name=model_name,
                timeout=timeout,
                set_active=set_active
            )

            return jsonify({
                'status': 'success',
                'model': model.to_dict(),
                'message': f'Model {model_name} added successfully'
            })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/remove/<model_id>', methods=['DELETE'])
def remove_model(model_id):
    """
    Remove a model from the registry.

    Path params:
        model_id: ID of the model to remove
    """
    try:
        registry = ModelRegistry()

        success = registry.remove_model(model_id)

        if success:
            return jsonify({
                'status': 'success',
                'message': f'Model {model_id} removed successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Model {model_id} not found'
            }), 404
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/activate/<model_id>', methods=['PUT'])
def activate_model(model_id):
    """
    Set a model as the active model for its type.

    Path params:
        model_id: ID of the model to activate
    """
    try:
        registry = ModelRegistry()

        success = registry.set_active_model(model_id)

        if success:
            model = registry.get_model(model_id)
            return jsonify({
                'status': 'success',
                'message': f'Model {model.model_name} is now active',
                'model': model.to_dict()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Model {model_id} not found'
            }), 404
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/check/<model_id>', methods=['GET'])
def check_model_availability(model_id):
    """
    Check if a specific model is available.

    Path params:
        model_id: ID of the model to check
    """
    try:
        config = ConfigManager()
        registry = ModelRegistry()
        checker = ModelAvailabilityChecker(config, registry)

        model = registry.get_model(model_id)
        if not model:
            return jsonify({
                'status': 'error',
                'message': f'Model {model_id} not found'
            }), 404

        is_available = checker.check_model_availability(model_id)

        return jsonify({
            'status': 'success',
            'model_id': model_id,
            'is_available': is_available,
            'model': model.to_dict()
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
