#!/bin/bash

# Test script for PyPI server functionality

echo "Building and starting PyPI server..."
docker compose build pypi-server
docker compose up -d pypi-server

echo "Waiting for PyPI server to be ready..."
sleep 10

echo "Testing PyPI server endpoints..."
echo "1. Testing root endpoint:"
curl -f http://localhost:8080/ || echo "Root endpoint failed"

echo -e "\n2. Testing simple index:"
curl -f http://localhost:8080/simple/ || echo "Simple index failed"

echo -e "\n3. Checking for torch packages:"
curl -f http://localhost:8080/simple/torch/ || echo "Torch packages not found"

echo -e "\n4. Listing available packages:"
curl -s http://localhost:8080/simple/ | grep -o 'href="[^"]*"' | head -10

echo -e "\nPyPI server test completed!"