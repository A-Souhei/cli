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


def get_ui_sessions_from_chat():
    """Get UI sessions from the chat module's in-memory store."""
    try:
        from src.ui.routes.chat import get_ui_sessions
        return get_ui_sessions()
    except ImportError:
        return []


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
        
        # First, get sessions from the UI in-memory store (always available)
        ui_sessions = get_ui_sessions_from_chat()
        if ui_sessions:
            sessions.extend(ui_sessions)
        
        # Also try to get sessions from the SessionManager (which uses Redis API internally)
        session_manager = get_session_manager()
        if session_manager:
            try:
                redis_sessions = session_manager.list_saved_sessions()
                # Merge without duplicates (by session_id)
                existing_ids = {s.get('session_id') for s in sessions}
                for rs in redis_sessions:
                    if rs.get('session_id') not in existing_ids:
                        sessions.append(rs)
            except Exception:
                pass  # Redis not available, continue with UI sessions
        
        # If still empty, try direct Redis API call as last resort
        if not sessions:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(
                        f"{redis_api_url}/session/list",
                        params={"prefix": "cli:session:"}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        sessions = data.get('sessions', [])
            except Exception:
                # Redis API not available, sessions stays empty
                pass
        
        # Filter by working directory if not showing all
        if not show_all and sessions:
            sessions = [
                s for s in sessions 
                if s.get('working_dir') == working_dir
            ]
        
        # Sort by saved_at or start_time (most recent first)
        sessions.sort(
            key=lambda s: s.get('saved_at') or s.get('start_time') or '',
            reverse=True
        )
        
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
        # First check UI store
        ui_sessions = get_ui_sessions_from_chat()
        for session in ui_sessions:
            if session.get('session_id') == session_id:
                return jsonify({
                    'status': 'success',
                    'session': session
                })
        
        # Try Redis API
        redis_api_url = get_redis_api_url()
        key = f"cli:session:{session_id}"
        
        try:
            with httpx.Client(timeout=5.0) as client:
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
        except Exception as e:
            capture_exception(e)
        
        return jsonify({
            'status': 'error',
            'message': 'Session not found'
        }), 404
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def delete_ui_session_by_id(session_id: str) -> bool:
    """Delete a session from the UI store."""
    try:
        from src.ui.routes.chat import delete_ui_session
        return delete_ui_session(session_id)
    except ImportError:
        return False


@sessions_bp.route('/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a specific session."""
    try:
        deleted = False
        
        # Delete from UI store
        if delete_ui_session_by_id(session_id):
            deleted = True
        
        # Also try to delete from Redis
        redis_api_url = get_redis_api_url()
        key = f"cli:session:{session_id}"
        
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.delete(
                    f"{redis_api_url}/session/delete",
                    params={"key": key}
                )
                
                if response.status_code == 200:
                    deleted = True
        except Exception as e:
            capture_exception(e)
        
        if deleted:
            return jsonify({
                'status': 'success',
                'message': f'Session {session_id} deleted'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Session not found'
            }), 404
                
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def clear_ui_sessions_store() -> int:
    """Clear all sessions from the UI store."""
    try:
        from src.ui.routes.chat import clear_ui_sessions
        return clear_ui_sessions()
    except ImportError:
        return 0


@sessions_bp.route('/clear', methods=['DELETE'])
def clear_sessions():
    """Clear all sessions for the current working directory."""
    try:
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())
        deleted_count = 0
        
        # Clear from UI store (clears all, but that's ok for now)
        deleted_count += clear_ui_sessions_store()
        
        # Also try to clear from Redis
        redis_api_url = get_redis_api_url()
        
        try:
            with httpx.Client(timeout=10.0) as client:
                list_response = client.get(
                    f"{redis_api_url}/session/list",
                    params={"prefix": "cli:session:"}
                )
                
                if list_response.status_code == 200:
                    sessions = list_response.json().get('sessions', [])
                    
                    # Filter by working directory
                    sessions_to_delete = [
                        s for s in sessions 
                        if s.get('working_dir') == working_dir
                    ]
                    
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
        except Exception:
            pass  # Redis not available
        
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
