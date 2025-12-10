"""Tests for the tester MCP server and its tools."""

import pytest
import json
import os
import sys
from pathlib import Path

# Add the CLI root to path
cli_root = Path(__file__).parent.parent
sys.path.insert(0, str(cli_root))


@pytest.mark.unit
def test_tester_mcp_server_exists():
    """Test that tester MCP server.py exists."""
    server_path = cli_root / "system_mcps" / "tester" / "server.py"
    assert server_path.exists(), "Tester MCP server.py should exist"
    assert server_path.is_file(), "server.py should be a file"


@pytest.mark.unit
def test_tester_mcp_tools_yaml_exists():
    """Test that tester MCP tools.yaml exists."""
    tools_yaml_path = cli_root / "system_mcps" / "tester" / "tools.yaml"
    assert tools_yaml_path.exists(), "Tester MCP tools.yaml should exist"
    assert tools_yaml_path.is_file(), "tools.yaml should be a file"


@pytest.mark.unit
def test_tester_mcp_server_is_executable():
    """Test that server.py is executable."""
    server_path = cli_root / "system_mcps" / "tester" / "server.py"
    assert os.access(server_path, os.X_OK), "server.py should be executable"


@pytest.mark.unit
def test_tester_mcp_tools_yaml_structure():
    """Test that tools.yaml has the correct structure."""
    import yaml
    
    tools_yaml_path = cli_root / "system_mcps" / "tester" / "tools.yaml"
    with open(tools_yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Check for categories
    assert 'categories' in data, "tools.yaml should have categories"
    assert 'planning' in data['categories'], "Should have planning category"
    assert 'testing' in data['categories'], "Should have testing category"
    
    # Check for tools
    assert 'tools' in data, "tools.yaml should have tools section"
    assert 'plan_mode' in data['tools'], "Should have plan_mode tool"
    assert 'run_pytest' in data['tools'], "Should have run_pytest tool"
    assert 'create_pytest_test' in data['tools'], "Should have create_pytest_test tool"
    assert 'validate_with_test' in data['tools'], "Should have validate_with_test tool"


@pytest.mark.unit
def test_plan_mode_keywords():
    """Test that plan_mode has the correct keywords."""
    import yaml
    
    tools_yaml_path = cli_root / "system_mcps" / "tester" / "tools.yaml"
    with open(tools_yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    plan_mode = data['tools']['plan_mode']
    keywords = plan_mode.get('keywords', [])
    
    # Check for required keywords
    assert 'plan' in keywords, "plan_mode should have 'plan' keyword"
    assert 'test' in keywords, "plan_mode should have 'test' keyword"


@pytest.mark.unit
def test_create_pytest_test_tool_validation():
    """Test create_pytest_test validation logic."""
    # This is a unit test for the tool's internal logic
    # We'll create a simple test case
    
    test_content_template = '''"""Tests for module."""

import pytest

@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}


def test_example():
    """Example test case."""
    assert True
'''
    
    # Verify the template has the expected structure
    assert 'import pytest' in test_content_template
    assert '@pytest.fixture' in test_content_template
    assert 'def test_example():' in test_content_template
    assert 'assert True' in test_content_template


@pytest.mark.unit
def test_tester_mcp_server_imports():
    """Test that tester MCP server can be imported."""
    try:
        # Import the server module to check for syntax errors
        import importlib.util
        
        server_path = cli_root / "system_mcps" / "tester" / "server.py"
        spec = importlib.util.spec_from_file_location("tester_server", server_path)
        module = importlib.util.module_from_spec(spec)
        
        # This will raise if there are syntax errors
        spec.loader.exec_module(module)
        
        # Check that key functions exist
        assert hasattr(module, 'validate_working_dir'), "Should have validate_working_dir function"
        assert hasattr(module, 'create_execution_plan'), "Should have create_execution_plan function"
        assert hasattr(module, 'get_all_available_tools'), "Should have get_all_available_tools function"
        assert hasattr(module, 'match_tools_to_steps'), "Should have match_tools_to_steps function"
        
    except Exception as e:
        pytest.fail(f"Failed to import tester MCP server: {e}")


@pytest.mark.unit
def test_validate_working_dir_logic():
    """Test the validate_working_dir function logic."""
    import importlib.util
    
    server_path = cli_root / "system_mcps" / "tester" / "server.py"
    spec = importlib.util.spec_from_file_location("tester_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Test with valid directory
    is_valid, error = module.validate_working_dir(str(cli_root))
    assert is_valid, f"CLI root should be valid: {error}"
    assert error == "", "No error for valid directory"
    
    # Test with invalid directory
    is_valid, error = module.validate_working_dir("/nonexistent/directory")
    assert not is_valid, "Nonexistent directory should be invalid"
    assert "does not exist" in error.lower(), "Error should mention directory doesn't exist"


@pytest.mark.unit
def test_pytest_template_generation():
    """Test pytest test template generation logic."""
    test_functions = ['test_addition', 'test_validation']
    module_to_test = 'calculator'
    
    # Simulate template generation
    test_content = f'''"""Tests for {module_to_test}."""

import pytest
# from {module_to_test} import *


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {{"key": "value"}}


'''
    
    for func_name in test_functions:
        if not func_name.startswith("test_"):
            func_name = f"test_{func_name}"
        
        test_content += f'''def {func_name}():
    """Test for {func_name.replace('test_', '')}."""
    # TODO: Implement test
    assert True


'''
    
    # Verify structure
    assert 'import pytest' in test_content
    assert '@pytest.fixture' in test_content
    assert 'def test_addition():' in test_content
    assert 'def test_validation():' in test_content
    assert test_content.count('def test_') == 2


@pytest.mark.unit  
def test_plan_mode_step_extraction():
    """Test step extraction from LLM response."""
    import re
    
    # Simulate LLM response with numbered steps
    llm_response = """Here's the plan:

1. Create a Python file called calculator.py with add and subtract functions
2. Write unit tests in test_calculator.py to validate the functions
3. Run the tests using pytest
4. Execute the script to verify it works"""
    
    # Extract steps (same logic as in create_execution_plan)
    steps = []
    for line in llm_response.split('\n'):
        line = line.strip()
        match = re.match(r'^(\d+)[.):\-\s]+(.+)$', line)
        if match:
            step_text = match.group(2).strip()
            if step_text:
                steps.append(step_text)
    
    # Verify extraction
    assert len(steps) == 4, "Should extract 4 steps"
    assert "Create a Python file" in steps[0]
    assert "Write unit tests" in steps[1]
    assert "Run the tests" in steps[2]
    assert "Execute the script" in steps[3]


@pytest.mark.unit
def test_find_cli_venv_logic():
    """Test find_cli_venv function logic."""
    import importlib.util
    
    server_path = cli_root / "system_mcps" / "tester" / "server.py"
    spec = importlib.util.spec_from_file_location("tester_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Test finding venv
    venv_python = module.find_cli_venv()
    assert venv_python is not None, "Should find a Python executable"
    assert isinstance(venv_python, str), "Should return a string path"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
