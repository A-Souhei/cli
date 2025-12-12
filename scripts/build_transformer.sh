#!/bin/bash
# Build transformer service with BuildKit for optimal caching
# This ensures pip cache mounts work properly and heavy packages aren't re-downloaded

set -e  # Exit on first error

echo "🚀 Building transformer service with BuildKit cache optimization..."
echo ""
echo "This build uses:"
echo "  - Pip cache mounts (packages cached between builds)"
echo "  - HuggingFace model cache (models cached in Docker layer)"
echo "  - Layer caching (unchanged layers reused)"
echo ""

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with docker compose
docker compose build transformer

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Cache info:"
echo "  - Torch (~800MB) is cached and won't be re-downloaded on next build"
echo "  - Transformers (~400MB) is cached"
echo "  - CodeBERT model (~500MB) is pre-downloaded in the image"
echo "  - Sentence transformers model is pre-downloaded in the image"
echo ""
echo "💡 To rebuild without cache: docker compose build --no-cache transformer"
