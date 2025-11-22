#!/bin/bash
# Test script for spin_the_roulette feature
# Tests both the backend endpoint and the complete workflow

set -e

echo "==================================="
echo "spin_the_roulette Feature Tests"
echo "==================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Simple text splitting
echo -e "${YELLOW}Test 1: Simple text splitting${NC}"
echo "Testing: /mcp-tools/text-to-sequence endpoint"
echo ""

RESPONSE=$(curl -X POST http://localhost:15000/mcp-tools/text-to-sequence \
  -H "Content-Type: application/json" \
  -d '{"text": "Run Python code. Create a file.", "model": "tinyllama", "max_iterations": 1}' \
  -s -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Test 1 PASSED${NC}"
    echo "Response:"
    echo "$BODY" | python3 -m json.tool | head -20
else
    echo -e "${RED}✗ Test 1 FAILED (HTTP $HTTP_CODE)${NC}"
    echo "$BODY"
fi

echo ""
echo "-----------------------------------"
echo ""

# Test 2: Error handling - empty text
echo -e "${YELLOW}Test 2: Error handling - empty text${NC}"
echo ""

RESPONSE=$(curl -X POST http://localhost:15000/mcp-tools/text-to-sequence \
  -H "Content-Type: application/json" \
  -d '{"text": ""}' \
  -s -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "400" ]; then
    echo -e "${GREEN}✓ Test 2 PASSED${NC}"
    echo "Correctly rejected empty text"
    echo "$BODY" | python3 -m json.tool
else
    echo -e "${RED}✗ Test 2 FAILED (Expected 400, got HTTP $HTTP_CODE)${NC}"
    echo "$BODY"
fi

echo ""
echo "-----------------------------------"
echo ""

# Test 3: Error handling - missing text parameter
echo -e "${YELLOW}Test 3: Error handling - missing text parameter${NC}"
echo ""

RESPONSE=$(curl -X POST http://localhost:15000/mcp-tools/text-to-sequence \
  -H "Content-Type: application/json" \
  -d '{"model": "tinyllama"}' \
  -s -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "400" ]; then
    echo -e "${GREEN}✓ Test 3 PASSED${NC}"
    echo "Correctly rejected missing text parameter"
    echo "$BODY" | python3 -m json.tool
else
    echo -e "${RED}✗ Test 3 FAILED (Expected 400, got HTTP $HTTP_CODE)${NC}"
    echo "$BODY"
fi

echo ""
echo "-----------------------------------"
echo ""

# Test 4: Service availability checks
echo -e "${YELLOW}Test 4: Service availability checks${NC}"
echo ""

echo -n "Checking Ollama service... "
if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Available${NC}"
else
    echo -e "${RED}✗ Not available${NC}"
fi

echo -n "Checking PostgreSQL API... "
if curl -s http://localhost:15000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Available${NC}"
else
    echo -e "${RED}✗ Not available${NC}"
fi

echo -n "Checking Transformer service... "
if curl -s http://localhost:16050/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Available${NC}"
else
    echo -e "${RED}✗ Not available${NC}"
fi

echo ""
echo "==================================="
echo "Test Summary Complete"
echo "==================================="
echo ""
echo "Note: The text-to-sequence endpoint may take 30-180 seconds for complex texts."
echo "Tinyllama model may return verbose explanations instead of clean steps."
echo "Consider using llama3.1:8b or other models for better results."
