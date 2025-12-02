"""
Sessions API routes for the UI.

Provides endpoints for:
- Listing sessions for current working directory
- Getting session details
- Creating new sessions
- Restoring sessions
- Deleting sessions
"""

import os
from flask import Blueprint, jsonify, request, current_app
import httpx

from src.sentry_config import capture_exception

sessions_bp = Blueprint('sessions', __name__)


def get_redis_api_url() -> str:
    """Get Redis API URL from environment or use default."""
    return os.getenv('REDIS_API_URL', 'http://localhost:17000')


def get_session_manager():
    """Get the shared SessionManager instance from chat module."""
    try:
        from src.ui.routes.chat import get_session_manager as get_chat_session_manager
        return get_chat_session_manager()
    except ImportError:
        return None


@sessions_bp.route('/', methods=['GET'])
def list_sessions():
    """
    List all sessions for the current working directory.
    
    Query params:
        all: If 'true', return all sessions regardless of working directory
    """
    try:
        redis_api_url = get_redis_api_url()
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())
        show_all = request.args.get('all', 'false').lower() == 'true'
        
        sessions = []
        
        # First try to get sessions from the SessionManager (which uses Redis API internally)
        session_manager = get_session_manager()
        if session_manager:
            try:
                sessions = session_manager.list_saved_sessions()
            except Exception:
                sessions = []
        
        # If that fails or returns empty, try direct Redis API call
        if not sessions:
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        f"{redis_api_url}/session/list",
                        params={"prefix": "cli:session:"}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        sessions = data.get('sessions', [])
            except Exception:
                # Redis API not available, return empty list
                sessions = []
        
        # Filter by working directory if not showing all
        if not show_all and sessions:
            sessions = [
                s for s in sessions 
                if s.get('working_dir') == working_dir
            ]
        
        return jsonify({
            'status': 'success',
            'count': len(sessions),
            'sessions': sessions,
            'working_dir': working_dir,
            'filtered': not show_all
        })
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'sessions': [],
            'count': 0
        }), 500


@sessions_bp.route('/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get details of a specific session."""
    try:
        redis_api_url = get_redis_api_url()
        key = f"cli:session:{session_id}"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{redis_api_url}/session/retrieve",
                params={"key": key}
            )
            
            if response.status_code == 200:
                session_data = response.json()
                return jsonify({
                    'status': 'success',
                    'session': session_data
                })
            elif response.status_code == 404:
                return jsonify({
                    'status': 'error',
                    'message': 'Session not found'
                }), 404
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to fetch session: {response.status_code}'
                }), response.status_code
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@sessions_bp.route('/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a specific session."""
    try:
        redis_api_url = get_redis_api_url()
        key = f"cli:session:{session_id}"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.delete(
                f"{redis_api_url}/session/delete",
                params={"key": key}
            )
            
            if response.status_code == 200:
                return jsonify({
                    'status': 'success',
                    'message': f'Session {session_id} deleted'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to delete session: {response.status_code}'
                }), response.status_code
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@sessions_bp.route('/clear', methods=['DELETE'])
def clear_sessions():
    """Clear all sessions for the current working directory."""
    try:
        redis_api_url = get_redis_api_url()
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())
        
        # First, get all sessions
        with httpx.Client(timeout=10.0) as client:
            list_response = client.get(
                f"{redis_api_url}/session/list",
                params={"prefix": "cli:session:"}
            )
            
            if list_response.status_code != 200:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to list sessions'
                }), list_response.status_code
            
            sessions = list_response.json().get('sessions', [])
            
            # Filter by working directory
            sessions_to_delete = [
                s for s in sessions 
                if s.get('working_dir') == working_dir
            ]
            
            deleted_count = 0
            for session in sessions_to_delete:
                session_id = session.get('session_id')
                if session_id:
                    key = f"cli:session:{session_id}"
                    del_response = client.delete(
                        f"{redis_api_url}/session/delete",
                        params={"key": key}
                    )
                    if del_response.status_code == 200:
                        deleted_count += 1
            
            return jsonify({
                'status': 'success',
                'message': f'Deleted {deleted_count} sessions',
                'deleted_count': deleted_count
            })
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
