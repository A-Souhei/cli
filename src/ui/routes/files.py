"""
Files API routes for the UI.

Provides endpoints for:
- Listing directory contents
- Reading file contents
- Getting file metadata
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.sentry_config import capture_exception

files_bp = Blueprint('files', __name__)


def get_file_icon(name: str, is_dir: bool) -> str:
    """Get an appropriate icon for a file type."""
    if is_dir:
        return "folder"
    
    ext = Path(name).suffix.lower()
    
    # Map extensions to icon types
    icon_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'react',
        '.tsx': 'react',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'css',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.md': 'markdown',
        '.txt': 'text',
        '.sh': 'shell',
        '.bash': 'shell',
        '.sql': 'database',
        '.git': 'git',
        '.gitignore': 'git',
        '.env': 'env',
        '.dockerfile': 'docker',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
        '.svg': 'image',
        '.pdf': 'pdf',
        '.zip': 'archive',
        '.tar': 'archive',
        '.gz': 'archive',
    }
    
    # Check for special filenames
    name_lower = name.lower()
    if name_lower == 'dockerfile':
        return 'docker'
    if name_lower == 'makefile':
        return 'makefile'
    if name_lower.startswith('.git'):
        return 'git'
    
    return icon_map.get(ext, 'file')


def format_size(size: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_time(timestamp: float) -> str:
    """Format timestamp to readable format."""
    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    
    if dt.date() == now.date():
        return dt.strftime("Today %H:%M")
    elif (now - dt).days == 1:
        return dt.strftime("Yesterday %H:%M")
    elif (now - dt).days < 7:
        return dt.strftime("%A %H:%M")
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


@files_bp.route('/list')
def list_directory():
    """
    List contents of a directory.
    
    Query params:
        path: Relative path from working directory (default: '')
        show_hidden: Show hidden files (default: false)
    """
    try:
        # Get explorer root (original directory where CLI was opened)
        working_dir = current_app.config.get('EXPLORER_ROOT', os.getcwd())
        rel_path = request.args.get('path', '')
        show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
        
        # Resolve the full path
        if rel_path:
            full_path = os.path.normpath(os.path.join(working_dir, rel_path))
        else:
            full_path = working_dir
        
        # Security check - prevent directory traversal
        if not full_path.startswith(working_dir):
            return jsonify({
                'status': 'error',
                'message': 'Access denied: Path outside working directory'
            }), 403
        
        if not os.path.exists(full_path):
            return jsonify({
                'status': 'error',
                'message': f'Path not found: {rel_path}'
            }), 404
        
        if not os.path.isdir(full_path):
            return jsonify({
                'status': 'error',
                'message': 'Path is not a directory'
            }), 400
        
        items = []
        try:
            entries = os.listdir(full_path)
        except PermissionError:
            return jsonify({
                'status': 'error',
                'message': 'Permission denied'
            }), 403
        
        for name in entries:
            # Skip hidden files if not requested
            if not show_hidden and name.startswith('.'): 
                continue
            
            item_path = os.path.join(full_path, name)
            
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                
                items.append({
                    'name': name,
                    'path': os.path.join(rel_path, name) if rel_path else name,
                    'full_path': item_path,  # Add absolute path for operations
                    'is_dir': is_dir,
                    'size': stat.st_size if not is_dir else None,
                    'size_formatted': format_size(stat.st_size) if not is_dir else None,
                    'modified': stat.st_mtime,
                    'modified_formatted': format_time(stat.st_mtime),
                    'icon': get_file_icon(name, is_dir)
                })
            except (OSError, PermissionError):
                # Skip files we can't access
                continue
        
        # Sort: directories first, then by name
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
        # Build breadcrumb
        breadcrumb = [{'name': 'Root', 'path': ''}]
        if rel_path:
            parts = rel_path.split(os.sep)
            current = ''
            for part in parts:
                current = os.path.join(current, part) if current else part
                breadcrumb.append({'name': part, 'path': current})
        
        return jsonify({
            'status': 'success',
            'path': rel_path,
            'full_path': full_path,
            'breadcrumb': breadcrumb,
            'items': items,
            'total': len(items),
            'show_hidden': show_hidden
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@files_bp.route('/read', methods=['GET'])
def read_file():
    """
    Read contents of a file.
    
    Query params:
        path: Relative path to file
        max_size: Maximum size to read in bytes (default: 1MB)
    """
    try:
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())
        rel_path = request.args.get('path', '')
        max_size = int(request.args.get('max_size', 1024 * 1024))  # 1MB default
        
        if not rel_path:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400
        
        full_path = os.path.normpath(os.path.join(working_dir, rel_path))
        
        # Security check
        if not full_path.startswith(working_dir):
            return jsonify({
                'status': 'error',
                'message': 'Access denied: Path outside working directory'
            }), 403
        
        if not os.path.exists(full_path):
            return jsonify({
                'status': 'error',
                'message': f'File not found: {rel_path}'
            }), 404
        
        if os.path.isdir(full_path):
            return jsonify({
                'status': 'error',
                'message': 'Cannot read directory'
            }), 400
        
        stat = os.stat(full_path)
        
        # Check if file is too large
        if stat.st_size > max_size:
            return jsonify({
                'status': 'error',
                'message': f'File too large ({format_size(stat.st_size)}). Max: {format_size(max_size)}',
                'size': stat.st_size,
                'max_size': max_size
            }), 413
        
        # Try to read file
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            is_binary = False
        except UnicodeDecodeError:
            # Binary file
            content = None
            is_binary = True
        
        # Get language for syntax highlighting
        ext = Path(full_path).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.sh': 'bash',
            '.bash': 'bash',
            '.sql': 'sql',
            '.xml': 'xml',
            '.txt': 'text',
        }
        language = language_map.get(ext, 'text')
        
        return jsonify({
            'status': 'success',
            'path': rel_path,
            'name': os.path.basename(full_path),
            'content': content,
            'is_binary': is_binary,
            'size': stat.st_size,
            'size_formatted': format_size(stat.st_size),
            'modified': stat.st_mtime,
            'modified_formatted': format_time(stat.st_mtime),
            'language': language,
            'line_count': content.count('\n') + 1 if content else 0
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@files_bp.route('/info', methods=['GET'])
def file_info():
    """
    Get metadata about a file or directory.
    
    Query params:
        path: Relative path to file/directory
    """
    try:
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())
        rel_path = request.args.get('path', '')
        
        if not rel_path:
            # Info about working directory
            full_path = working_dir
            rel_path = ''
        else:
            full_path = os.path.normpath(os.path.join(working_dir, rel_path))
        
        # Security check
        if not full_path.startswith(working_dir):
            return jsonify({
                'status': 'error',
                'message': 'Access denied'
            }), 403
        
        if not os.path.exists(full_path):
            return jsonify({
                'status': 'error',
                'message': 'Path not found'
            }), 404
        
        stat = os.stat(full_path)
        is_dir = os.path.isdir(full_path)
        name = os.path.basename(full_path) or os.path.basename(working_dir)
        
        info = {
            'status': 'success',
            'name': name,
            'path': rel_path,
            'full_path': full_path,
            'is_dir': is_dir,
            'size': stat.st_size,
            'size_formatted': format_size(stat.st_size),
            'modified': stat.st_mtime,
            'modified_formatted': format_time(stat.st_mtime),
            'created': stat.st_ctime,
            'created_formatted': format_time(stat.st_ctime),
            'icon': get_file_icon(name, is_dir)
        }
        
        if is_dir:
            # Count items in directory
            try:
                items = os.listdir(full_path)
                info['item_count'] = len(items)
                info['dir_count'] = sum(1 for i in items if os.path.isdir(os.path.join(full_path, i)))
                info['file_count'] = info['item_count'] - info['dir_count']
            except PermissionError:
                info['item_count'] = None
        
        return jsonify(info)
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@files_bp.route('/set-working-dir', methods=['POST'])
def set_working_directory():
    """Set the working directory for the UI."""
    try:
        data = request.get_json()
        new_path = data.get('path')
        
        if not new_path:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400
        
        # Validate path exists and is a directory
        if not os.path.exists(new_path):
            return jsonify({
                'status': 'error',
                'message': 'Path does not exist'
            }), 400
        
        if not os.path.isdir(new_path):
            return jsonify({
                'status': 'error',
                'message': 'Path is not a directory'
            }), 400
        
        # Update the environment variable and app config for chat context
        # Note: This does NOT change the explorer root, only the working directory for LLM
        os.environ['AI_CLI_CWD'] = new_path
        current_app.config['WORKING_DIR'] = new_path
        
        return jsonify({
            'status': 'success',
            'message': 'Working directory updated for chat context',
            'working_dir': new_path
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
