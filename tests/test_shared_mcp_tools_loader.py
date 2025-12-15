"""Tests for shared_mcp_tools_loader module."""

import pytest
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'utils'))

from shared_mcp_tools_loader import (
    get_all_tools_metadata,
    get_all_tools_metadata_cached
)


class TestToolsMetadataLoader:
    """Test loading tools metadata from tools.yaml files."""

    def test_get_all_tools_metadata(self):
        """Test loading all tools metadata from system_mcps directory."""
        # Get the system_mcps directory path
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / 'system_mcps'
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        # Load all tools metadata
        tools_metadata = get_all_tools_metadata(str(system_mcps_dir))
        
        # Verify we got some tools
        assert len(tools_metadata) > 0, "Should load at least some tools"
        
        # Check for coder tools
        coder_tools = ['run_python_code', 'run_r_code', 'write_python_code', 
                       'edit_python_code', 'add_file_context']
        for tool_name in coder_tools:
            assert tool_name in tools_metadata, f"Should find {tool_name}"
            assert 'mcp_name' in tools_metadata[tool_name]
            assert 'categories' in tools_metadata[tool_name]
            assert 'metadata' in tools_metadata[tool_name]
        
        # Check for data-engineer tools
        data_engineer_tools = ['generate_fake_data', 'generate_fake_data_ctgan', 
                               'generate_ast', 'compare_code_similarity']
        for tool_name in data_engineer_tools:
            assert tool_name in tools_metadata, f"Should find {tool_name}"
            tool_data = tools_metadata[tool_name]
            assert tool_data['mcp_name'] == 'data-engineer'
            assert 'categories' in tool_data
            assert len(tool_data['categories']) > 0
    
    def test_meta_tools_identification(self):
        """Test that meta tools are correctly identified by category."""
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / 'system_mcps'
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        tools_metadata = get_all_tools_metadata(str(system_mcps_dir))
        
        # Check meta tools
        meta_tools = ['spin_the_roulette', 'retrieve_all_tools', 'roll_the_dice', 'execute_plan']
        for tool_name in meta_tools:
            if tool_name in tools_metadata:
                categories = tools_metadata[tool_name]['categories']
                assert 'meta' in categories, f"{tool_name} should be in 'meta' category"
    
    def test_data_generation_tools_have_proper_metadata(self):
        """Test that data generation tools have proper metadata."""
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / 'system_mcps'
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        tools_metadata = get_all_tools_metadata(str(system_mcps_dir))
        
        # Check generate_fake_data
        if 'generate_fake_data' in tools_metadata:
            tool_data = tools_metadata['generate_fake_data']
            assert 'data_generation' in tool_data['categories']
            assert tool_data['metadata'].get('requires_file_path') == True
            assert tool_data['metadata'].get('generates_file') == True
            assert 'description' in tool_data
    
    def test_cached_version_returns_same_data(self):
        """Test that cached version returns the same data."""
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / 'system_mcps'
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        # Get data twice using cached version
        data1 = get_all_tools_metadata_cached(str(system_mcps_dir))
        data2 = get_all_tools_metadata_cached(str(system_mcps_dir))
        
        # Should be the same object (cached)
        assert data1 is data2
        assert len(data1) == len(data2)
    
    def test_tool_descriptions_exist(self):
        """Test that tools have descriptions."""
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / 'system_mcps'
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        tools_metadata = get_all_tools_metadata(str(system_mcps_dir))
        
        # Check that data-engineer tools have descriptions
        data_tools = ['generate_fake_data', 'generate_fake_data_ctgan']
        for tool_name in data_tools:
            if tool_name in tools_metadata:
                tool_data = tools_metadata[tool_name]
                # Description can be in the metadata dict or as a separate field
                desc = tool_data.get('description', '') or tool_data.get('metadata', {}).get('description', '')
                assert desc, f"{tool_name} should have a description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
