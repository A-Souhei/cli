"""Unit tests for MCP tools loader utilities."""

import pytest
import yaml
from pathlib import Path
import tempfile
import shutil

from src.utils.mcp_tools_loader import (
    get_valid_coding_tools,
    get_meta_tools,
    get_tool_category,
    get_tools_requiring_file_path,
)
from src.utils.shared_mcp_tools_loader import (
    get_tools_requiring_file_path as shared_get_tools_requiring_file_path,
    get_file_path_tools_cached,
)


class TestMCPToolsLoader:
    """Test the main MCP tools loader for CLI."""

    @pytest.fixture
    def temp_system_mcps(self):
        """Create a temporary system_mcps directory with test tools.yaml files."""
        temp_dir = tempfile.mkdtemp()
        system_mcps = Path(temp_dir) / "system_mcps"
        system_mcps.mkdir()

        # Create test coder MCP
        coder_dir = system_mcps / "coder"
        coder_dir.mkdir()
        coder_tools = {
            'categories': {
                'valid_coding': {
                    'tools': ['run_python_code', 'write_python_code', 'detect_code']
                },
                'meta': {
                    'tools': ['retrieve_all_tools', 'roll_the_dice']
                }
            },
            'tools': {
                'run_python_code': {'requires_file_path': True},
                'write_python_code': {'requires_file_path': True},
                'detect_code': {'requires_file_path': False},
                'retrieve_all_tools': {'is_meta': True},
                'roll_the_dice': {'is_meta': True}
            }
        }
        with open(coder_dir / "tools.yaml", 'w') as f:
            yaml.dump(coder_tools, f)

        # Create test data-engineer MCP
        data_eng_dir = system_mcps / "data-engineer"
        data_eng_dir.mkdir()
        data_eng_tools = {
            'categories': {
                'data_generation': {
                    'tools': ['generate_fake_data']
                },
                'valid_coding': {
                    'tools': ['generate_ast']
                }
            },
            'tools': {
                'generate_fake_data': {'requires_file_path': True},
                'generate_ast': {'requires_file_path': True}
            }
        }
        with open(data_eng_dir / "tools.yaml", 'w') as f:
            yaml.dump(data_eng_tools, f)

        yield system_mcps

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_get_valid_coding_tools(self, temp_system_mcps):
        """Test loading valid coding tools from multiple MCPs."""
        tools = get_valid_coding_tools(temp_system_mcps)
        
        assert 'run_python_code' in tools
        assert 'write_python_code' in tools
        assert 'detect_code' in tools
        assert 'generate_ast' in tools
        assert len(tools) == 4

    def test_get_meta_tools(self, temp_system_mcps):
        """Test loading meta tools from multiple MCPs."""
        tools = get_meta_tools(temp_system_mcps)
        
        assert 'retrieve_all_tools' in tools
        assert 'roll_the_dice' in tools
        assert len(tools) == 2

    def test_get_tool_category(self, temp_system_mcps):
        """Test loading tools from a specific category."""
        tools = get_tool_category('data_generation', temp_system_mcps)
        
        assert 'generate_fake_data' in tools
        assert len(tools) == 1

    def test_get_tools_requiring_file_path(self, temp_system_mcps):
        """Test loading tools that require file_path parameter."""
        tools = get_tools_requiring_file_path(temp_system_mcps)
        
        assert 'run_python_code' in tools
        assert 'write_python_code' in tools
        assert 'generate_fake_data' in tools
        assert 'generate_ast' in tools
        assert 'detect_code' not in tools  # This one doesn't require file_path
        assert len(tools) == 4

    def test_nonexistent_directory(self):
        """Test handling of nonexistent system_mcps directory."""
        nonexistent = Path("/tmp/nonexistent_mcps_dir_12345")
        
        assert get_valid_coding_tools(nonexistent) == []
        assert get_meta_tools(nonexistent) == []
        assert get_tools_requiring_file_path(nonexistent) == []

    def test_missing_tools_yaml(self, temp_system_mcps):
        """Test handling of MCP directory without tools.yaml."""
        # Create an MCP directory without tools.yaml
        empty_mcp = temp_system_mcps / "empty-mcp"
        empty_mcp.mkdir()
        
        # Should not raise error, just skip that MCP
        tools = get_valid_coding_tools(temp_system_mcps)
        assert isinstance(tools, list)

    def test_invalid_yaml(self, temp_system_mcps):
        """Test handling of invalid YAML syntax."""
        invalid_mcp = temp_system_mcps / "invalid-mcp"
        invalid_mcp.mkdir()
        
        # Write invalid YAML
        with open(invalid_mcp / "tools.yaml", 'w') as f:
            f.write("invalid: yaml: syntax: [[[")
        
        # Should not raise error, just skip that MCP and print warning
        tools = get_valid_coding_tools(temp_system_mcps)
        assert isinstance(tools, list)


class TestSharedMCPToolsLoader:
    """Test the shared MCP tools loader for Docker services."""

    @pytest.fixture
    def temp_system_mcps_str(self):
        """Create a temporary system_mcps directory and return path as string."""
        temp_dir = tempfile.mkdtemp()
        system_mcps = Path(temp_dir) / "system_mcps"
        system_mcps.mkdir()

        # Create test MCP
        coder_dir = system_mcps / "coder"
        coder_dir.mkdir()
        coder_tools = {
            'tools': {
                'run_python_code': {'requires_file_path': True},
                'write_python_code': {'requires_file_path': True},
                'detect_code': {'requires_file_path': False}
            }
        }
        with open(coder_dir / "tools.yaml", 'w') as f:
            yaml.dump(coder_tools, f)

        yield str(system_mcps)

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_shared_get_tools_requiring_file_path(self, temp_system_mcps_str):
        """Test shared loader for file_path tools."""
        tools = shared_get_tools_requiring_file_path(temp_system_mcps_str)
        
        assert 'run_python_code' in tools
        assert 'write_python_code' in tools
        assert 'detect_code' not in tools
        assert len(tools) == 2

    def test_shared_nonexistent_directory(self):
        """Test shared loader with nonexistent directory."""
        tools = shared_get_tools_requiring_file_path("/tmp/nonexistent_12345")
        assert tools == []


class TestRealSystemMCPs:
    """Test with the actual system_mcps directory in the repository."""

    def test_coder_tools_yaml_exists(self):
        """Test that coder tools.yaml exists and is valid."""
        repo_root = Path(__file__).parent.parent
        coder_tools_yaml = repo_root / "system_mcps" / "coder" / "tools.yaml"
        
        assert coder_tools_yaml.exists(), "coder/tools.yaml should exist"
        
        with open(coder_tools_yaml) as f:
            data = yaml.safe_load(f)
        
        assert 'categories' in data
        assert 'tools' in data
        assert 'valid_coding' in data['categories']
        assert 'meta' in data['categories']

    def test_data_engineer_tools_yaml_exists(self):
        """Test that data-engineer tools.yaml exists and is valid."""
        repo_root = Path(__file__).parent.parent
        de_tools_yaml = repo_root / "system_mcps" / "data-engineer" / "tools.yaml"
        
        assert de_tools_yaml.exists(), "data-engineer/tools.yaml should exist"
        
        with open(de_tools_yaml) as f:
            data = yaml.safe_load(f)
        
        assert 'categories' in data
        assert 'tools' in data

    def test_all_data_engineer_tools_have_file_path(self):
        """Test that all data-engineer tools use requires_file_path (not requires_file)."""
        repo_root = Path(__file__).parent.parent
        de_tools_yaml = repo_root / "system_mcps" / "data-engineer" / "tools.yaml"
        
        with open(de_tools_yaml) as f:
            data = yaml.safe_load(f)
        
        tools = data.get('tools', {})
        for tool_name, metadata in tools.items():
            # Check that if the tool requires a file, it uses 'requires_file_path' not 'requires_file'
            if metadata:
                assert 'requires_file' not in metadata, \
                    f"Tool {tool_name} uses 'requires_file' - should use 'requires_file_path' instead"
                
                # If it has requires_file_path, it should be boolean
                if 'requires_file_path' in metadata:
                    assert isinstance(metadata['requires_file_path'], bool), \
                        f"Tool {tool_name} requires_file_path should be boolean"

    def test_real_system_mcps_loading(self):
        """Test loading from the actual system_mcps directory."""
        repo_root = Path(__file__).parent.parent
        system_mcps_dir = repo_root / "system_mcps"
        
        if not system_mcps_dir.exists():
            pytest.skip("system_mcps directory not found")
        
        # Test valid_coding tools
        valid_coding = get_valid_coding_tools(system_mcps_dir)
        assert len(valid_coding) > 0, "Should have at least some valid coding tools"
        assert 'run_python_code' in valid_coding
        assert 'write_python_code' in valid_coding
        
        # Test meta tools
        meta = get_meta_tools(system_mcps_dir)
        assert len(meta) > 0, "Should have at least some meta tools"
        assert 'retrieve_all_tools' in meta
        
        # Test file_path tools
        file_path_tools = get_tools_requiring_file_path(system_mcps_dir)
        assert len(file_path_tools) > 0, "Should have tools requiring file_path"
        assert 'run_python_code' in file_path_tools
        assert 'write_python_code' in file_path_tools
        assert 'generate_fake_data' in file_path_tools
        assert 'generate_ast' in file_path_tools
        
        print(f"\n✓ Loaded {len(valid_coding)} valid coding tools")
        print(f"✓ Loaded {len(meta)} meta tools")
        print(f"✓ Loaded {len(file_path_tools)} tools requiring file_path")
        print(f"  File path tools: {file_path_tools}")
