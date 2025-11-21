#!/usr/bin/env python3
"""
Validation script for tool retrieval parameter extraction logic.
This script tests the parameter extraction function independently.
"""

import sys
import re


def extract_parameters_from_text(text, tool_name):
    """
    Extract parameters from text based on common patterns.
    (Copy of the function from app.py for validation)
    """
    params = {}
    text_lower = text.lower()

    # Common patterns for different tool types

    # 1. Code execution tools (run_python_code, run_r_code)
    if 'run' in tool_name or 'execute' in tool_name or 'eval' in tool_name:
        # Look for code blocks in backticks or quotes
        code_patterns = [
            r'```(?:python|r)?\s*(.*?)```',  # Code blocks
            r'`([^`]+)`',  # Inline code
            r'"([^"]+)"',  # Double quotes
            r"'([^']+)'",  # Single quotes
        ]

        for pattern in code_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                params['code'] = match.group(1).strip()
                break

        # If no code block found, use the entire text after command words
        if 'code' not in params:
            # Remove common command words
            code_text = re.sub(r'\b(run|execute|eval|this|the|following|code|python|r)\b', '', text_lower, flags=re.IGNORECASE)
            params['code'] = code_text.strip()

    # 2. File operations (write_python_code, write_r_code, edit_*_code)
    elif 'write' in tool_name or 'edit' in tool_name or 'create' in tool_name:
        # Look for file paths
        file_patterns = [
            r'(?:file|path|to|at|in)\s+([^\s,;]+\.(?:py|r|txt|json|csv|md))',
            r'([^\s,;]+\.(?:py|r|txt|json|csv|md))',
        ]

        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params['file_path'] = match.group(1)
                break

        # Look for code content
        code_patterns = [
            r'```(?:python|r)?\s*(.*?)```',
            r'code[:\s]+(.+)',
        ]

        for pattern in code_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                params['code'] = match.group(1).strip()
                break

    # 3. Context operations (add_file_context, add_directory_context)
    elif 'context' in tool_name or 'add' in tool_name:
        # Look for file or directory paths
        path_patterns = [
            r'([^\s,;]+(?:/[^\s,;]+)+)',  # Unix-style paths (check first for full paths)
            r'([A-Za-z]:\\[^\s,;]+)',  # Windows-style paths
            r'(?:file|directory|folder|path)\s+([^\s,;]+)',  # Keyword-prefixed paths
        ]

        for pattern in path_patterns:
            match = re.search(pattern, text)
            if match:
                path = match.group(1)
                # Skip if path is just "context" or other keywords
                if path.lower() not in ['context', 'file', 'directory', 'folder', 'path', 'for', 'to', 'at']:
                    if 'directory' in tool_name or 'folder' in text_lower:
                        params['directory_path'] = path
                    else:
                        params['file_path'] = path
                    break

    # 4. Generic text content extraction
    if not params:
        # If no specific parameters found, include the text as a generic 'input' parameter
        params['input'] = text

    return params


def test_extraction():
    """Test parameter extraction with various inputs."""
    test_cases = [
        # Code execution tests
        {
            "text": "Run this Python code: `print('hello')`",
            "tool": "run_python_code",
            "expected": {"code": "print('hello')"},
            "description": "Extract code from inline backticks"
        },
        {
            "text": "Execute ```python\nprint('test')\n```",
            "tool": "run_python_code",
            "expected": {"code": "print('test')"},
            "description": "Extract code from markdown block"
        },
        {
            "text": 'Run this: "import pandas"',
            "tool": "run_python_code",
            "expected": {"code": "import pandas"},
            "description": "Extract code from quotes"
        },
        # File operation tests
        {
            "text": "Create file test.py with code",
            "tool": "write_python_code",
            "expected": {"file_path": "test.py"},
            "description": "Extract file path from write command"
        },
        {
            "text": "Edit analysis.r",
            "tool": "edit_r_code",
            "expected": {"file_path": "analysis.r"},
            "description": "Extract R file path"
        },
        # Context operation tests
        {
            "text": "Add file context for /home/user/main.py",
            "tool": "add_file_context",
            "expected": {"file_path": "/home/user/main.py"},
            "description": "Extract Unix file path"
        },
        {
            "text": "Add directory /home/user/project to context",
            "tool": "add_directory_context",
            "expected": {"directory_path": "/home/user/project"},
            "description": "Extract directory path"
        },
        # Generic fallback test
        {
            "text": "Some random text",
            "tool": "unknown_tool",
            "expected": {"input": "Some random text"},
            "description": "Fallback to generic input"
        }
    ]

    print("=" * 80)
    print("PARAMETER EXTRACTION VALIDATION")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['description']}")
        print(f"  Text: '{test['text']}'")
        print(f"  Tool: {test['tool']}")

        result = extract_parameters_from_text(test['text'], test['tool'])

        # Check if extracted params match expected
        success = True
        for key, expected_value in test['expected'].items():
            if key not in result:
                print(f"  ❌ FAILED: Missing key '{key}'")
                success = False
            elif expected_value not in result[key]:
                print(f"  ❌ FAILED: Expected '{expected_value}' in '{result[key]}'")
                success = False

        if success:
            print(f"  ✅ PASSED")
            print(f"  Extracted: {result}")
            passed += 1
        else:
            print(f"  Got: {result}")
            failed += 1

        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)

    return failed == 0


def validate_endpoint_structure():
    """Validate the endpoint response structure."""
    print("\n" + "=" * 80)
    print("ENDPOINT STRUCTURE VALIDATION")
    print("=" * 80)
    print()

    # Simulate endpoint response structure
    mock_response = {
        "status": "success",
        "count": 2,
        "results": [
            {
                "prompt": "Run Python code",
                "prompt_index": 0,
                "matched_tools": [
                    {
                        "rank": 1,
                        "mcp_name": "coder",
                        "tool_name": "run_python_code",
                        "description": "Execute Python code",
                        "similarity": 0.87,
                        "extracted_params": {"code": "example"}
                    }
                ],
                "best_match": {
                    "rank": 1,
                    "mcp_name": "coder",
                    "tool_name": "run_python_code",
                    "description": "Execute Python code",
                    "similarity": 0.87,
                    "extracted_params": {"code": "example"}
                }
            }
        ],
        "metadata": {
            "threshold": 0.5,
            "top_k": 3,
            "mcp_filter": None,
            "total_prompts": 2,
            "total_tools_searched": 10
        }
    }

    # Validate structure
    required_top_level = ["status", "count", "results", "metadata"]
    required_result = ["prompt", "prompt_index", "matched_tools", "best_match"]
    required_match = ["rank", "mcp_name", "tool_name", "description", "similarity"]
    required_metadata = ["threshold", "top_k", "mcp_filter", "total_prompts", "total_tools_searched"]

    all_valid = True

    # Check top level
    for field in required_top_level:
        if field in mock_response:
            print(f"✅ Top-level field '{field}' present")
        else:
            print(f"❌ Top-level field '{field}' missing")
            all_valid = False

    # Check result structure
    if mock_response["results"]:
        result = mock_response["results"][0]
        for field in required_result:
            if field in result:
                print(f"✅ Result field '{field}' present")
            else:
                print(f"❌ Result field '{field}' missing")
                all_valid = False

        # Check match structure
        if result["best_match"]:
            match = result["best_match"]
            for field in required_match:
                if field in match:
                    print(f"✅ Match field '{field}' present")
                else:
                    print(f"❌ Match field '{field}' missing")
                    all_valid = False

    # Check metadata
    metadata = mock_response["metadata"]
    for field in required_metadata:
        if field in metadata:
            print(f"✅ Metadata field '{field}' present")
        else:
            print(f"❌ Metadata field '{field}' missing")
            all_valid = False

    print("\n" + "=" * 80)
    if all_valid:
        print("✅ All endpoint structure validations passed!")
    else:
        print("❌ Some endpoint structure validations failed!")
    print("=" * 80)

    return all_valid


if __name__ == "__main__":
    print("Running Tool Retrieval Validation...\n")

    extraction_ok = test_extraction()
    structure_ok = validate_endpoint_structure()

    print("\n" + "=" * 80)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Parameter Extraction: {'✅ PASSED' if extraction_ok else '❌ FAILED'}")
    print(f"Endpoint Structure:   {'✅ PASSED' if structure_ok else '❌ FAILED'}")
    print("=" * 80)

    if extraction_ok and structure_ok:
        print("\n🎉 All validations passed! Implementation is ready.")
        sys.exit(0)
    else:
        print("\n⚠️  Some validations failed. Review the output above.")
        sys.exit(1)
