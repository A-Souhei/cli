#!/usr/bin/env python3
"""
Test script to verify the tabular-gmd API integration.

This script tests:
1. Configuration loading
2. API endpoint health check
3. Fallback mechanism
"""

import sys
import os
import yaml
import requests
from pathlib import Path

# Add the system_mcps directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "system_mcps" / "data-engineer"))

def test_config_loading():
    """Test loading the tabular-gmd configuration."""
    print("=" * 60)
    print("TEST 1: Configuration Loading")
    print("=" * 60)
    
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if 'tabular_gmd' not in config:
        print("❌ tabular_gmd configuration not found")
        return False
    
    url = config['tabular_gmd'].get('url')
    timeout = config['tabular_gmd'].get('timeout')
    
    print(f"✅ Configuration loaded:")
    print(f"   URL: {url}")
    print(f"   Timeout: {timeout}s")
    print()
    
    return url, timeout


def test_api_health(url):
    """Test the API endpoint health check."""
    print("=" * 60)
    print("TEST 2: API Health Check")
    print("=" * 60)
    
    try:
        response = requests.get(f"{url}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API is healthy:")
            print(f"   Status: {data.get('status')}")
            print(f"   GPU Available: {data.get('gpu_available')}")
            print(f"   GPU Count: {data.get('gpu_count')}")
            print(f"   GPU Name: {data.get('gpu_name')}")
            print()
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            print()
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API is not reachable: {str(e)}")
        print()
        return False


def test_fallback_mechanism():
    """Test the fallback mechanism."""
    print("=" * 60)
    print("TEST 3: Fallback Mechanism")
    print("=" * 60)
    
    # Try importing the local tabular-gmd library
    tabular_gmd_path = Path(__file__).parent.parent / "system_mcps" / "data-engineer" / "tabular-gmd"
    
    if not tabular_gmd_path.exists():
        print(f"❌ Local tabular-gmd not found: {tabular_gmd_path}")
        return False
    
    sys.path.insert(0, str(tabular_gmd_path))
    
    try:
        from tabular_gmd import TabularGMD, DiffusionConfig
        print("✅ Local tabular-gmd library is available")
        print(f"   Path: {tabular_gmd_path}")
        print()
        return True
    except ImportError as e:
        print(f"❌ Failed to import tabular-gmd: {str(e)}")
        print()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TABULAR-GMD API INTEGRATION TESTS")
    print("=" * 60 + "\n")
    
    # Test 1: Configuration
    result = test_config_loading()
    if not result:
        print("\n❌ Configuration test failed!")
        return 1
    
    url, timeout = result
    
    # Test 2: API Health
    api_healthy = test_api_health(url)
    
    # Test 3: Fallback
    fallback_available = test_fallback_mechanism()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Configuration: ✅")
    print(f"API Endpoint:  {'✅' if api_healthy else '⚠️ (will use fallback)'}")
    print(f"Local Fallback: {'✅' if fallback_available else '❌'}")
    print()
    
    if api_healthy:
        print("✅ All tests passed! The API endpoint is available.")
    elif fallback_available:
        print("⚠️  API endpoint unavailable, but fallback is ready.")
    else:
        print("❌ Both API and fallback are unavailable!")
        return 1
    
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
