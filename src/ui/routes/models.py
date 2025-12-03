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
        type: Optional filter by model type ('general' or 'coder')
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
        model_type: Type of model ('general' or 'coder')
        url: Ollama service URL
        model_name: Name of the model
        timeout: Optional timeout in seconds (default: 120)
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
        model_name = data.get('model_name')
        timeout = data.get('timeout', 120)
        set_active = data.get('set_active', True)

        if not model_type or not url or not model_name:
            return jsonify({
                'status': 'error',
                'message': 'model_type, url, and model_name are required'
            }), 400

        # Check availability first
        config = ConfigManager()
        registry = ModelRegistry()
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
