"""
Commands API routes for the UI.

Provides endpoints for:
- Executing code commands
- Running MCP tools
- Text-to-sequence conversion
"""

import os
from flask import Blueprint, jsonify, request
import requests

from src.sentry_config import capture_exception

commands_bp = Blueprint('commands', __name__)


def get_postgres_api_url() -> str:
    """Get PostgreSQL API URL from environment or use default."""
    return os.getenv('POSTGRES_API_URL', 'http://localhost:15000')


@commands_bp.route('/code', methods=['POST'])
def execute_code_command():
    """
    Execute a code command using the simplified endpoint.
    
    Request body:
        text: The code command text
        session_id: Optional session ID
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400
        
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Text is required'
            }), 400
        
        session_id = data.get('session_id', 'ui-session')
        postgres_api_url = get_postgres_api_url()
        
        # Call the code-command-simple endpoint
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/code-command-simple",
            json={
                'text': text,
                'session_id': session_id
            },
            headers={"Content-Type": "application/json"},
            timeout=180
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to execute code command: {response.status_code}',
                'response': response.text
            }), response.status_code
        
        return jsonify(response.json())
        
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Request timed out'
        }), 504
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@commands_bp.route('/text-to-sequence', methods=['POST'])
def text_to_sequence():
    """
    Convert text to a sequence of steps.
    
    Request body:
        text: The text to convert
        model: Optional model name
        max_iterations: Optional max iterations
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400
        
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Text is required'
            }), 400
        
        postgres_api_url = get_postgres_api_url()
        
        # Call the text-to-sequence endpoint
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/text-to-sequence",
            json={
                'text': text,
                'model': data.get('model', 'tinyllama'),
                'max_iterations': data.get('max_iterations', 3)
            },
            headers={"Content-Type": "application/json"},
            timeout=180
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to convert text: {response.status_code}',
                'response': response.text
            }), response.status_code
        
        return jsonify(response.json())
        
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Request timed out'
        }), 504
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@commands_bp.route('/retrieve-tools', methods=['POST'])
def retrieve_tools():
    """
    Retrieve matching tools for given prompts.
    
    Request body:
        prompts: List of prompts
        threshold: Optional similarity threshold
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400
        
        prompts = data.get('prompts')
        if not prompts or not isinstance(prompts, list):
            return jsonify({
                'status': 'error',
                'message': 'Prompts list is required'
            }), 400
        
        postgres_api_url = get_postgres_api_url()
        
        # Call the retrieve endpoint
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/retrieve",
            json={
                'prompts': prompts,
                'threshold': data.get('threshold', 0.5)
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to retrieve tools: {response.status_code}',
                'response': response.text
            }), response.status_code
        
        return jsonify(response.json())
        
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Request timed out'
        }), 504
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
