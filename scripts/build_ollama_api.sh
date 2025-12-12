#!/bin/bash
# Build Ollama API service with BuildKit for optimal caching

echo "🚀 Building Ollama API service with BuildKit cache optimization..."
echo ""
echo "This build uses:"
echo "  - Apt cache mounts (system packages cached between builds)"
echo "  - Pip cache mounts (Python packages cached between builds)"
echo "  - Layer caching (unchanged layers reused)"
echo ""

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with docker compose
docker compose build ollama-api

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Cache info:"
echo "  - FastAPI, uvicorn, and dependencies are cached"
echo ""
echo "💡 To rebuild without cache: docker compose build --no-cache ollama-api"
