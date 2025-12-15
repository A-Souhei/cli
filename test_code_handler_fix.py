#!/usr/bin/env python3
"""
Test to verify that handle_code_file_writing is called with correct parameters.
"""

import sys
from pathlib import Path
import inspect

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.code_handlers import handle_code_file_writing, handle_code_execution, display_execution_result


def test_function_signatures():
    """Verify function signatures match expected parameters."""
    print("Testing function signatures...")
    
    # Check handle_code_file_writing signature
    sig = inspect.signature(handle_code_file_writing)
    params = list(sig.parameters.keys())
    
    expected_params = ['mcp_client', 'response_text', 'target_file', 'get_working_dir_func', 'console', 'debug_print_func']
    assert params == expected_params, f"handle_code_file_writing params mismatch. Expected: {expected_params}, Got: {params}"
    
    # Check that get_working_dir_func is a required parameter (no default value)
    assert sig.parameters['get_working_dir_func'].default == inspect.Parameter.empty, "get_working_dir_func should be required"
    
    print("✓ handle_code_file_writing signature is correct")
    
    # Check handle_code_execution signature
    sig = inspect.signature(handle_code_execution)
    params = list(sig.parameters.keys())
    
    expected_params = ['mcp_client', 'response_text', 'selector_class', 'console', 'debug_print_func']
    assert params == expected_params, f"handle_code_execution params mismatch. Expected: {expected_params}, Got: {params}"
    
    print("✓ handle_code_execution signature is correct")
    
    # Check display_execution_result signature
    sig = inspect.signature(display_execution_result)
    params = list(sig.parameters.keys())
    
    expected_params = ['result', 'console', 'debug_print_func']
    assert params == expected_params, f"display_execution_result params mismatch. Expected: {expected_params}, Got: {params}"
    
    print("✓ display_execution_result signature is correct")
    
    print("\n✓ All function signature tests passed!")


if __name__ == "__main__":
    try:
        test_function_signatures()
        print("\n✓ ALL TESTS PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        sys.exit(1)
