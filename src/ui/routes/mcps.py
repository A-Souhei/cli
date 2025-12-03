"""
MCPs API routes for the UI.

Provides endpoints for:
- Listing all MCPs
- Getting MCP details and tools
- Discovering available tools with descriptions
"""

import os
from pathlib import Path
from flask import Blueprint, jsonify
import requests

from src.sentry_config import capture_exception

mcps_bp = Blueprint('mcps', __name__)


def get_system_mcps_dir() -> Path:
    """Get the system MCPs directory."""
    # Navigate from src/ui/routes/ to project root
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "system_mcps"


def get_postgres_api_url() -> str:
    """Get PostgreSQL API URL from environment or use default."""
    return os.getenv('POSTGRES_API_URL', 'http://localhost:15000')


@mcps_bp.route('/', methods=['GET'])
def list_mcps():
    """List all available MCPs."""
    try:
        mcps_dir = get_system_mcps_dir()
        
        if not mcps_dir.exists():
            return jsonify({
                'status': 'error',
                'message': 'MCPs directory not found'
            }), 404
        
        mcps = []
        for item in mcps_dir.iterdir():
            if item.is_dir() and (item / "server.py").exists():
                mcp_info = {
                    'name': item.name,
                    'path': str(item),
                    'has_readme': (item / "README.md").exists(),
                    'has_requirements': (item / "requirements.txt").exists()
                }
                
                # Try to read README for description
                readme_path = item / "README.md"
                if readme_path.exists():
                    try:
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Extract first paragraph as description
                            lines = content.strip().split('\n\n')
                            if len(lines) > 1:
                                # Skip the title line
                                mcp_info['description'] = lines[1].strip()[:200]
                            else:
                                mcp_info['description'] = content[:200]
                    except Exception:
                        mcp_info['description'] = None
                
                mcps.append(mcp_info)
        
        return jsonify({
            'status': 'success',
            'count': len(mcps),
            'mcps': mcps
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@mcps_bp.route('/<mcp_name>', methods=['GET'])
def get_mcp_details(mcp_name: str):
    """Get details of a specific MCP."""
    try:
        mcps_dir = get_system_mcps_dir()
        mcp_path = mcps_dir / mcp_name
        
        if not mcp_path.exists() or not (mcp_path / "server.py").exists():
            return jsonify({
                'status': 'error',
                'message': f'MCP "{mcp_name}" not found'
            }), 404
        
        mcp_info = {
            'name': mcp_name,
            'path': str(mcp_path),
            'has_readme': (mcp_path / "README.md").exists(),
            'has_requirements': (mcp_path / "requirements.txt").exists(),
            'readme': None,
            'requirements': None
        }
        
        # Read README if exists
        readme_path = mcp_path / "README.md"
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    mcp_info['readme'] = f.read()
            except Exception as e:
                capture_exception(e)
        
        # Read requirements if exists
        req_path = mcp_path / "requirements.txt"
        if req_path.exists():
            try:
                with open(req_path, 'r', encoding='utf-8') as f:
                    mcp_info['requirements'] = f.read()
            except Exception as e:
                # Log the exception but continue, as requirements.txt is optional
                capture_exception(e)
        
        return jsonify({
            'status': 'success',
            'mcp': mcp_info
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@mcps_bp.route('/<mcp_name>/tools', methods=['GET'])
def get_mcp_tools(mcp_name: str):
    """Get tools for a specific MCP from the database."""
    try:
        postgres_api_url = get_postgres_api_url()
        
        # Get tools from PostgreSQL database
        response = requests.get(
            f"{postgres_api_url}/mcp-tools",
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch tools: {response.status_code}'
            }), response.status_code
        
        data = response.json()
        all_tools = data.get('tools', [])
        
        # Filter by MCP name
        mcp_tools = [
            t for t in all_tools 
            if t.get('mcp_name') == mcp_name
        ]
        
        return jsonify({
            'status': 'success',
            'mcp_name': mcp_name,
            'count': len(mcp_tools),
            'tools': mcp_tools
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@mcps_bp.route('/tools', methods=['GET'])
def list_all_tools():
    """List all tools from all MCPs."""
    try:
        postgres_api_url = get_postgres_api_url()
        
        # Get tools from PostgreSQL database
        response = requests.get(
            f"{postgres_api_url}/mcp-tools",
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch tools: {response.status_code}'
            }), response.status_code
        
        data = response.json()
        tools = data.get('tools', [])
        
        # Group by MCP
        tools_by_mcp = {}
        for tool in tools:
            mcp_name = tool.get('mcp_name', 'unknown')
            if mcp_name not in tools_by_mcp:
                tools_by_mcp[mcp_name] = []
            tools_by_mcp[mcp_name].append(tool)
        
        return jsonify({
            'status': 'success',
            'total_count': len(tools),
            'mcps_count': len(tools_by_mcp),
            'tools_by_mcp': tools_by_mcp,
            'tools': tools
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
