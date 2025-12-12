#!/bin/bash
# Build Redis API service with BuildKit for optimal caching

set -e  # Exit on first error

echo "🚀 Building Redis API service with BuildKit cache optimization..."
echo ""
echo "This build uses:"
echo "  - Pip cache mounts (packages cached between builds)"
echo "  - Layer caching (unchanged layers reused)"
echo ""

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with docker compose
docker compose build redis-api

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Cache info:"
echo "  - Flask and dependencies are cached and won't be re-downloaded"
echo ""
echo "💡 To rebuild without cache: docker compose build --no-cache redis-api"
