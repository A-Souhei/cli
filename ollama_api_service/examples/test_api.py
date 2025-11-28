#!/usr/bin/env python3
"""
Test script for Ollama++ API Service

This script demonstrates basic usage of all API endpoints.
"""

import requests
import json
import sys


API_BASE = "http://localhost:8080"


def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("Testing /health endpoint...")
    print("=" * 60)

    response = requests.get(f"{API_BASE}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def test_list_models():
    """Test model listing (Ollama format)."""
    print("=" * 60)
    print("Testing /api/tags (List Models)...")
    print("=" * 60)

    response = requests.get(f"{API_BASE}/api/tags")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def test_chat_non_streaming():
    """Test chat endpoint (non-streaming)."""
    print("=" * 60)
    print("Testing /api/chat (non-streaming)...")
    print("=" * 60)

    data = {
        "model": "llama3.1:8b",
        "messages": [
            {"role": "user", "content": "Say 'Hello from Ollama++ API!' and nothing else."}
        ],
        "stream": False
    }

    response = requests.post(f"{API_BASE}/api/chat", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def test_chat_streaming():
    """Test chat endpoint (streaming)."""
    print("=" * 60)
    print("Testing /api/chat (streaming)...")
    print("=" * 60)

    data = {
        "model": "llama3.1:8b",
        "messages": [
            {"role": "user", "content": "Count from 1 to 5."}
        ],
        "stream": True
    }

    response = requests.post(f"{API_BASE}/api/chat", json=data, stream=True)
    print(f"Status: {response.status_code}")
    print("Streaming response:")

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                print(content, end="", flush=True)
            if chunk.get("done"):
                print("\n[DONE]")
                break

    print()
    return response.status_code == 200


def test_openai_compatibility():
    """Test OpenAI-compatible endpoint."""
    print("=" * 60)
    print("Testing /v1/chat/completions (OpenAI)...")
    print("=" * 60)

    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Say 'OpenAI compatibility works!'"}
        ],
        "stream": False
    }

    response = requests.post(f"{API_BASE}/v1/chat/completions", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def test_tools_list():
    """Test MCP tools listing."""
    print("=" * 60)
    print("Testing /api/tools/list...")
    print("=" * 60)

    response = requests.get(f"{API_BASE}/api/tools/list")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {data.get('count', 0)} tools:")
    for tool in data.get('tools', []):
        print(f"  - {tool.get('name')}: {tool.get('description')}")
    print()

    return response.status_code == 200


def test_code_execution():
    """Test code execution."""
    print("=" * 60)
    print("Testing /api/code/execute...")
    print("=" * 60)

    data = {
        "code": "print('Hello from Python!')\nprint(2 + 2)",
        "language": "python"
    }

    response = requests.post(f"{API_BASE}/api/code/execute", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def test_file_upload():
    """Test file upload with @ prefix."""
    print("=" * 60)
    print("Testing /api/files/upload...")
    print("=" * 60)

    # Create a temporary test file
    files = {
        'files': ('test.txt', 'This is a test file content.', 'text/plain')
    }
    data = {
        'auto_inject': 'true'
    }

    response = requests.post(f"{API_BASE}/api/files/upload", files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

    return response.status_code == 200


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OLLAMA++ API SERVICE TEST SUITE")
    print("=" * 60 + "\n")

    tests = [
        ("Health Check", test_health),
        ("List Models", test_list_models),
        ("Chat (Non-Streaming)", test_chat_non_streaming),
        ("Chat (Streaming)", test_chat_streaming),
        ("OpenAI Compatibility", test_openai_compatibility),
        ("Tools List", test_tools_list),
        ("Code Execution", test_code_execution),
        ("File Upload", test_file_upload),
    ]

    results = {}

    for name, test_func in tests:
        try:
            success = test_func()
            results[name] = "✅ PASS" if success else "❌ FAIL"
        except Exception as e:
            print(f"ERROR: {e}\n")
            results[name] = f"❌ ERROR: {e}"

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        print(f"{name:<30} {result}")

    # Return exit code
    failures = [r for r in results.values() if "❌" in r]
    sys.exit(len(failures))


if __name__ == "__main__":
    main()
