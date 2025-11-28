#!/bin/bash
# Test runner for Ollama API service
# Usage: ./tests/run_api_tests.sh [test_type]
#   test_type: unit, integration, all, smoke (default: all)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default test type
TEST_TYPE="${1:-all}"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Ollama++ API Test Runner${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Function to check if API is running
check_api_running() {
    echo -e "${YELLOW}Checking if API is running...${NC}"
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is running${NC}"
        return 0
    else
        echo -e "${RED}✗ API is not running${NC}"
        return 1
    fi
}

# Function to run unit tests
run_unit_tests() {
    echo -e "${BLUE}Running unit tests...${NC}"
    cd "$PROJECT_DIR"
    pytest tests/test_ollama_api_models.py -v -m "not integration" --tb=short
}

# Function to run integration tests
run_integration_tests() {
    echo -e "${BLUE}Running integration tests...${NC}"

    if ! check_api_running; then
        echo -e "${YELLOW}Starting API service...${NC}"
        echo -e "${YELLOW}Please run: docker compose --profile ollama --profile app --profile api up -d${NC}"
        exit 1
    fi

    cd "$PROJECT_DIR"
    pytest tests/test_ollama_api_integration.py -v -m "integration" --tb=short
}

# Function to run smoke tests
run_smoke_tests() {
    echo -e "${BLUE}Running smoke tests...${NC}"

    if ! check_api_running; then
        echo -e "${RED}API service is not running!${NC}"
        exit 1
    fi

    # Quick smoke tests
    echo -e "${YELLOW}1. Testing /health endpoint...${NC}"
    curl -f -s http://localhost:8080/health | jq '.' || exit 1
    echo -e "${GREEN}✓ Health check passed${NC}"

    echo -e "${YELLOW}2. Testing /api/tags endpoint...${NC}"
    curl -f -s http://localhost:8080/api/tags | jq '.' || exit 1
    echo -e "${GREEN}✓ Model listing passed${NC}"

    echo -e "${YELLOW}3. Testing /api/tools/list endpoint...${NC}"
    curl -f -s http://localhost:8080/api/tools/list | jq '.' || exit 1
    echo -e "${GREEN}✓ Tools listing passed${NC}"

    echo -e "${GREEN}All smoke tests passed!${NC}"
}

# Main test execution
case "$TEST_TYPE" in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    smoke)
        run_smoke_tests
        ;;
    all)
        echo -e "${BLUE}Running all tests...${NC}"
        run_unit_tests
        echo ""
        run_integration_tests
        echo ""
        run_smoke_tests
        ;;
    *)
        echo -e "${RED}Invalid test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|integration|smoke|all]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}All tests completed successfully!${NC}"
echo -e "${GREEN}======================================${NC}"
