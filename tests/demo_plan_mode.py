#!/usr/bin/env python3
"""
Demonstration of the tester MCP plan_mode tool.

This script shows how the plan_mode tool works without requiring
the full CLI or Docker services to be running.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add the CLI root to path
cli_root = Path(__file__).parent.parent
sys.path.insert(0, str(cli_root))


async def demo_plan_mode():
    """Demonstrate plan_mode functionality."""
    print("=" * 60)
    print("  Tester MCP Plan Mode Demonstration")
    print("=" * 60)
    print()
    
    # Import the server module
    import importlib.util
    server_path = cli_root / "system_mcps" / "tester" / "server.py"
    spec = importlib.util.spec_from_file_location("tester_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    print("✓ Tester MCP server module loaded successfully")
    print()
    
    # Demo 1: Create execution plan
    print("Demo 1: Creating an execution plan")
    print("-" * 60)
    
    test_prompt = "Create a calculator.py with add and subtract functions, then create tests and run them"
    print(f"Prompt: {test_prompt}")
    print()
    
    # Create the plan (without calling Ollama)
    print("📝 Generating execution plan...")
    print()
    
    # Simulate what would happen
    expected_steps = [
        "Create a Python file called calculator.py with add and subtract functions",
        "Write unit tests in test_calculator.py to validate the functions",
        "Run the tests using pytest",
        "Execute the script to verify it works"
    ]
    
    print("Generated execution steps:")
    for i, step in enumerate(expected_steps, 1):
        print(f"  {i}. {step}")
    print()
    
    # Demo 2: Show tool metadata
    print("Demo 2: Tool Metadata")
    print("-" * 60)
    
    import yaml
    tools_yaml_path = cli_root / "system_mcps" / "tester" / "tools.yaml"
    with open(tools_yaml_path, 'r') as f:
        tools_data = yaml.safe_load(f)
    
    print("Available tools in tester MCP:")
    for tool_name, tool_info in tools_data['tools'].items():
        category = tool_info.get('category', 'unknown')
        requires_llm = tool_info.get('requires_llm', False)
        keywords = tool_info.get('keywords', [])
        print(f"\n  • {tool_name}")
        print(f"    Category: {category}")
        print(f"    Requires LLM: {requires_llm}")
        print(f"    Keywords: {', '.join(keywords)}")
    print()
    
    # Demo 3: Show validation function
    print("Demo 3: Working Directory Validation")
    print("-" * 60)
    
    # Test with valid directory
    is_valid, error = module.validate_working_dir(str(cli_root))
    print(f"Validating CLI root directory: {cli_root}")
    print(f"  Valid: {is_valid}")
    if error:
        print(f"  Error: {error}")
    else:
        print(f"  ✓ No errors")
    print()
    
    # Test with invalid directory
    is_valid, error = module.validate_working_dir("/nonexistent/path")
    print(f"Validating nonexistent directory: /nonexistent/path")
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error}")
    print()
    
    # Demo 4: Show pytest template generation
    print("Demo 4: Pytest Test Template Generation")
    print("-" * 60)
    
    module_name = "calculator"
    test_functions = ["test_add", "test_subtract"]
    
    print(f"Generating test template for module: {module_name}")
    print(f"Test functions: {test_functions}")
    print()
    
    test_template = f'''"""Tests for {module_name}."""

import pytest
# from {module_name} import *


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {{"key": "value"}}


def test_add():
    """Test for add."""
    # TODO: Implement test
    assert True


def test_subtract():
    """Test for subtract."""
    # TODO: Implement test
    assert True
'''
    
    print("Generated template:")
    print("-" * 40)
    print(test_template)
    print("-" * 40)
    print()
    
    # Summary
    print("=" * 60)
    print("  Summary")
    print("=" * 60)
    print()
    print("The tester MCP provides:")
    print("  1. ✓ Intelligent plan generation from prompts")
    print("  2. ✓ Automatic tool matching for each step")
    print("  3. ✓ Pytest test execution capabilities")
    print("  4. ✓ Test template scaffolding")
    print("  5. ✓ Code validation with unit tests")
    print()
    print("Keywords that trigger plan_mode:")
    print("  • plan, test, testing, validate")
    print("  • plan and test, create and test")
    print("  • build and validate")
    print()
    print("✓ Demo completed successfully!")
    print()


if __name__ == "__main__":
    asyncio.run(demo_plan_mode())
