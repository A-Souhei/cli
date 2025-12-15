"""Shared utility for loading MCP tool metadata from tools.yaml files.

This module can be used by both the main CLI and Docker services (like PostgreSQL API).
"""

import yaml
import threading
from pathlib import Path
from typing import List, Dict, Any


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


def get_all_tools_metadata(system_mcps_dir: str = "/app/system_mcps") -> Dict[str, Dict[str, Any]]:
    """
    Load metadata for all tools from tools.yaml files across all MCP servers.
    
    Returns a dictionary mapping tool names to their metadata including:
    - description (from tools.yaml if available)
    - category (which categories the tool belongs to)
    - mcp_name (which MCP server provides this tool)
    - metadata (all other metadata like requires_file_path, languages, etc.)
    
    Args:
        system_mcps_dir: Path to system_mcps directory
        
    Returns:
        Dict mapping tool_name to metadata dict
    """
    all_tools = {}
    
    system_mcps_path = Path(system_mcps_dir)
    if not system_mcps_path.exists():
        print(f"Warning: system_mcps directory not found: {system_mcps_dir}")
        return all_tools
    
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
            
            mcp_name = mcp_dir.name
            categories = data.get('categories', {})
            tools_metadata = data.get('tools', {})
            
            # Build tool-to-categories mapping
            tool_categories = {}
            for category_name, category_data in categories.items():
                tools_in_category = category_data.get('tools', [])
                for tool_name in tools_in_category:
                    if tool_name not in tool_categories:
                        tool_categories[tool_name] = []
                    tool_categories[tool_name].append(category_name)
            
            # Process each tool
            for tool_name, metadata in tools_metadata.items():
                all_tools[tool_name] = {
                    'mcp_name': mcp_name,
                    'categories': tool_categories.get(tool_name, []),
                    'metadata': metadata or {},
                    'description': metadata.get('description', '') if metadata else ''
                }
            
        except Exception as e:
            print(f"Warning: Failed to load tools.yaml from {mcp_dir.name}: {e}")
            continue
    
    return all_tools


# Cache for all tools metadata
_all_tools_cache = None
_all_tools_lock = threading.Lock()


def get_all_tools_metadata_cached(system_mcps_dir: str = "/app/system_mcps") -> Dict[str, Dict[str, Any]]:
    """
    Get all tools metadata with caching for performance.
    
    Thread-safe implementation using a lock to prevent race conditions.
    
    Args:
        system_mcps_dir: Path to system_mcps directory
        
    Returns:
        Cached dict of tool metadata
    """
    global _all_tools_cache
    
    if _all_tools_cache is None:
        with _all_tools_lock:
            if _all_tools_cache is None:
                _all_tools_cache = get_all_tools_metadata(system_mcps_dir)
                print(f"Loaded metadata for {len(_all_tools_cache)} tools from tools.yaml files")
    
    return _all_tools_cache
