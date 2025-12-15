"""Shared utility for loading MCP tool metadata from tools.yaml files.

This module can be used by both the main CLI and Docker services (like PostgreSQL API).
"""

import yaml
import threading
from pathlib import Path
from typing import List


def get_tools_requiring_file_path(system_mcps_dir: str) -> List[str]:
    """
    Load all tools that require a file_path parameter across all MCP servers.
    
    This reads the 'requires_file_path' attribute from tool metadata in tools.yaml files.
    
    Args:
        system_mcps_dir: Path to the system_mcps directory (as string for compatibility)
        
    Returns:
        List of tool names that require file_path parameter
    """
    file_path_tools = []
    
    system_mcps_path = Path(system_mcps_dir)
    if not system_mcps_path.exists():
        print(f"Warning: system_mcps directory not found: {system_mcps_dir}")
        return file_path_tools
    
    # Iterate through all MCP directories
    for mcp_dir in system_mcps_path.iterdir():
        if not mcp_dir.is_dir():
            continue
            
        tools_yaml = mcp_dir / "tools.yaml"
        if not tools_yaml.exists():
            continue
            
        try:
            with open(tools_yaml, 'r') as f:
                data = yaml.safe_load(f)
                
            # Extract tools with requires_file_path attribute
            tools_metadata = data.get('tools', {})
            for tool_name, metadata in tools_metadata.items():
                if metadata and metadata.get('requires_file_path', False):
                    file_path_tools.append(tool_name)
            
        except Exception as e:
            # Log error but continue with other MCPs
            print(f"Warning: Failed to load tools.yaml from {mcp_dir.name}: {e}")
            continue
    
    return file_path_tools


# Cache for file_path_tools to avoid repeated file I/O
_file_path_tools_cache = None
_cache_lock = threading.Lock()


def get_file_path_tools_cached(system_mcps_dir: str = "/app/system_mcps") -> List[str]:
    """
    Get tools requiring file_path with caching for performance.
    
    Thread-safe implementation using a lock to prevent race conditions
    in Flask applications with multiple workers or threads.
    
    Args:
        system_mcps_dir: Path to system_mcps directory
        
    Returns:
        Cached list of tool names requiring file_path
    """
    global _file_path_tools_cache
    
    # Double-checked locking pattern for thread-safe lazy initialization
    if _file_path_tools_cache is None:
        with _cache_lock:
            # Check again inside the lock to prevent race condition
            if _file_path_tools_cache is None:
                _file_path_tools_cache = get_tools_requiring_file_path(system_mcps_dir)
                print(f"Loaded {len(_file_path_tools_cache)} tools requiring file_path: {_file_path_tools_cache}")
    
    return _file_path_tools_cache
