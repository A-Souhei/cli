#!/bin/bash
# Build all services with BuildKit for optimal caching

set -e  # Exit on first error

echo "🚀 Building all services with pre-downloaded packages..."
echo ""

# Download all packages first
echo "📥 Downloading all Python packages..."
./scripts/download_all_packages.sh

echo ""
echo "🚀 Building services with BuildKit..."
echo ""

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build each service
echo "📦 Building PostgreSQL service..."
./scripts/build_postgres.sh

echo ""
echo "📦 Building Transformer service..."
./scripts/build_transformer.sh

echo ""
echo "📦 Building Redis API service..."
./scripts/build_redis.sh

echo ""
echo "📦 Building Ollama API service..."
./scripts/build_ollama_api.sh

echo ""
echo "✅ All services built successfully!"
echo ""
echo "💡 All services use BuildKit caching to avoid re-downloading packages"
echo "💡 Using pre-built images: ollama/ollama:latest, redis:7-alpine"
