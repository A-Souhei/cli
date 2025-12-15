"""Utility for loading MCP tool categories from tools.yaml files.

This module is designed for the CLI application and uses Path objects.
For Docker services, see shared_mcp_tools_loader.py which uses string paths
for better compatibility with container environments.
"""

import yaml
from pathlib import Path
from typing import List


def get_valid_coding_tools(system_mcps_dir: Path) -> List[str]:
    """
    Load all tools from the 'valid_coding' category across all MCP servers.
    
    Args:
        system_mcps_dir: Path to the system_mcps directory
        
    Returns:
        List of tool names that are valid for /code command execution
    """
    valid_tools = []
    
    if not system_mcps_dir.exists():
        return valid_tools
    
    # Iterate through all MCP directories
    for mcp_dir in system_mcps_dir.iterdir():
        if not mcp_dir.is_dir():
            continue
            
        tools_yaml = mcp_dir / "tools.yaml"
        if not tools_yaml.exists():
            continue
            
        try:
            with open(tools_yaml, 'r') as f:
                data = yaml.safe_load(f)
                
            # Extract tools from valid_coding category
            categories = data.get('categories', {})
            valid_coding = categories.get('valid_coding', {})
            tools = valid_coding.get('tools', [])
            
            valid_tools.extend(tools)
            
        except Exception as e:
            # Log error but continue with other MCPs
            print(f"Warning: Failed to load tools.yaml from {mcp_dir.name}: {e}")
            continue
    
    return valid_tools


def get_meta_tools(system_mcps_dir: Path) -> List[str]:
    """
    Load all tools from the 'meta' category across all MCP servers.
    
    Meta tools are orchestration tools that should not be executed directly
    in /code command steps.
    
    Args:
        system_mcps_dir: Path to the system_mcps directory
        
    Returns:
        List of meta tool names
    """
    meta_tools = []
    
    if not system_mcps_dir.exists():
        return meta_tools
    
    # Iterate through all MCP directories
    for mcp_dir in system_mcps_dir.iterdir():
        if not mcp_dir.is_dir():
            continue
            
        tools_yaml = mcp_dir / "tools.yaml"
        if not tools_yaml.exists():
            continue
            
        try:
            with open(tools_yaml, 'r') as f:
                data = yaml.safe_load(f)
                
            # Extract tools from meta category
            categories = data.get('categories', {})
            meta = categories.get('meta', {})
            tools = meta.get('tools', [])
            
            meta_tools.extend(tools)
            
        except Exception as e:
            # Log error but continue with other MCPs
            print(f"Warning: Failed to load tools.yaml from {mcp_dir.name}: {e}")
            continue
    
    return meta_tools


def get_code_generation_tools(system_mcps_dir: Path) -> List[str]:
    """
    Load all tools from the 'code_generation' category across all MCP servers.
    
    Code generation tools require LLM to generate code before execution.
    
    Args:
        system_mcps_dir: Path to the system_mcps directory
        
    Returns:
        List of code generation tool names
    """
    return get_tool_category('code_generation', system_mcps_dir)


def get_tool_category(category_name: str, system_mcps_dir: Path) -> List[str]:
    """
    Load all tools from a specific category across all MCP servers.
    
    Args:
        category_name: Name of the category (e.g., 'valid_coding', 'meta', 'execution')
        system_mcps_dir: Path to the system_mcps directory
        
    Returns:
        List of tool names in the specified category
    """
    tools_in_category = []
    
    if not system_mcps_dir.exists():
        return tools_in_category
    
    # Iterate through all MCP directories
    for mcp_dir in system_mcps_dir.iterdir():
        if not mcp_dir.is_dir():
            continue
            
        tools_yaml = mcp_dir / "tools.yaml"
        if not tools_yaml.exists():
            continue
            
        try:
            with open(tools_yaml, 'r') as f:
                data = yaml.safe_load(f)
                
            # Extract tools from specified category
            categories = data.get('categories', {})
            category = categories.get(category_name, {})
            tools = category.get('tools', [])
            
            tools_in_category.extend(tools)
            
        except Exception as e:
            # Log error but continue with other MCPs
            print(f"Warning: Failed to load tools.yaml from {mcp_dir.name}: {e}")
            continue
    
    return tools_in_category


def get_tools_requiring_file_path(system_mcps_dir: Path) -> List[str]:
    """
    Load all tools that require a file_path parameter across all MCP servers.
    
    This reads the 'requires_file_path' attribute from tool metadata in tools.yaml files.
    
    Args:
        system_mcps_dir: Path to the system_mcps directory
        
    Returns:
        List of tool names that require file_path parameter
    """
    file_path_tools = []
    
    if not system_mcps_dir.exists():
        return file_path_tools
    
    # Iterate through all MCP directories
    for mcp_dir in system_mcps_dir.iterdir():
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
