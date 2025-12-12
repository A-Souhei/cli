#!/bin/bash
# Build PostgreSQL service with BuildKit for optimal caching

set -e  # Exit on first error

echo "🚀 Building PostgreSQL service with BuildKit cache optimization..."
echo ""
echo "This build uses:"
echo "  - Apt cache mounts (system packages cached between builds)"
echo "  - Pip cache mounts (Python packages cached between builds)"
echo "  - Layer caching (unchanged layers reused)"
echo ""

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1

# Build with docker
docker build -f src/postgresql/Dockerfile -t cli-postgres:latest .

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Cache info:"
echo "  - PostgreSQL and system packages are cached"
echo "  - Flask and Python dependencies are cached"
echo ""
echo "💡 To rebuild without cache: docker build --no-cache -f src/postgresql/Dockerfile -t cli-postgres:latest ."
