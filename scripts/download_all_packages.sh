#!/bin/bash
set -e

# Script to download all Python packages needed by all services
# This creates a local wheelhouse that Docker builds can use
# Smart caching: Only downloads new/missing packages

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGES_DIR="$PROJECT_ROOT/packages"
MANIFEST_FILE="$PACKAGES_DIR/.manifest"

echo "=========================================="
echo "Smart Python Package Downloader"
echo "=========================================="

# Create packages directory
mkdir -p "$PACKAGES_DIR"

# Initialize counters
NEW_PACKAGES=0
SKIPPED_PACKAGES=0

# Function to normalize package name (converts to lowercase, replaces _ with -)
normalize_package_name() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g' | sed 's/\[.*\]//g'
}

# Function to check if package wheel exists in directory
package_exists() {
    local pkg="$1"
    local normalized=$(normalize_package_name "$pkg")
    
    # Check for wheel files matching this package
    # Format: package_name-version-*.whl
    if ls "$PACKAGES_DIR"/${normalized}-*.whl 2>/dev/null | grep -q .; then
        return 0  # exists
    fi
    return 1  # doesn't exist
}

# Function to download packages
download_packages() {
    local package_list="$1"
    local category="$2"
    
    echo ""
    echo "📦 Processing $category packages..."
    echo "------------------------------------------"
    
    local packages_to_download=""
    
    if [ -f "$package_list" ]; then
        # Read from requirements file
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip comments and empty lines
            [[ "$line" =~ ^#.*$ ]] && continue
            [[ -z "$line" ]] && continue
            
            # Extract package name (before ==, >=, etc.)
            local pkg_name=$(echo "$line" | sed 's/[>=<\[].*//g' | tr -d ' ')
            
            if package_exists "$pkg_name"; then
                echo "  ✓ $pkg_name (cached)"
                SKIPPED_PACKAGES=$((SKIPPED_PACKAGES + 1))
            else
                echo "  ↓ $pkg_name (downloading)"
                packages_to_download="$packages_to_download $line"
                NEW_PACKAGES=$((NEW_PACKAGES + 1))
            fi
        done < "$package_list"
    else
        # Direct package list
        for pkg in $package_list; do
            local pkg_name=$(echo "$pkg" | sed 's/[>=<\[].*//g' | tr -d ' ')
            
            if package_exists "$pkg_name"; then
                echo "  ✓ $pkg_name (cached)"
                SKIPPED_PACKAGES=$((SKIPPED_PACKAGES + 1))
            else
                echo "  ↓ $pkg_name (downloading)"
                packages_to_download="$packages_to_download $pkg"
                NEW_PACKAGES=$((NEW_PACKAGES + 1))
            fi
        done
    fi
    
    # Download only new packages (with dependencies to ensure completeness)
    if [ -n "$packages_to_download" ]; then
        echo "$packages_to_download" | xargs -n1 pip download -d "$PACKAGES_DIR" 2>&1 | grep -E "(Collecting|Saved|File was already downloaded)" || true
    fi
}

# Download transformer service packages
if [ -f "$PROJECT_ROOT/src/transformer/requirements.txt" ]; then
    download_packages "$PROJECT_ROOT/src/transformer/requirements.txt" "Transformer Service"
fi

# Download ollama API service packages
if [ -f "$PROJECT_ROOT/ollama_api_service/requirements.txt" ]; then
    download_packages "$PROJECT_ROOT/ollama_api_service/requirements.txt" "Ollama API Service"
fi

# Download main CLI requirements
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    download_packages "$PROJECT_ROOT/requirements.txt" "Main CLI"
fi

# Download packages from postgresql service (inline in Dockerfile)
download_packages "flask flask-sqlalchemy psycopg2-binary python-dotenv pgvector sentry-sdk pyyaml" "PostgreSQL Service"

# Download packages from redis-api service (inline in Dockerfile)
download_packages "Flask==2.3.2 redis==5.0.1 requests==2.31.0 sentry-sdk[flask]==1.29.2" "Redis API Service"

# Download packages from postgresql flask-app (inline in Dockerfile)
download_packages "Flask==2.3.2 Flask-SQLAlchemy==3.0.5 psycopg2-binary==2.9.6 sentry-sdk[flask]==1.29.2 requests==2.31.0 pyyaml==6.0" "PostgreSQL Flask App"

# Download heavy packages explicitly (PyTorch, transformers, etc.)
echo ""
echo "📦 Downloading heavy ML packages..."
echo "------------------------------------------"
download_packages "torch==2.1.2 transformers==4.36.2 sentence-transformers==2.7.0" "Heavy ML Packages"

echo ""
echo "=========================================="
echo "✅ Package download complete!"
echo "=========================================="
echo "📊 Summary:"
echo "  - New packages downloaded: $NEW_PACKAGES"
echo "  - Cached packages reused: $SKIPPED_PACKAGES"
echo "  - Total packages in wheelhouse: $(ls -1 "$PACKAGES_DIR"/*.whl 2>/dev/null | wc -l)"
echo ""
echo "💾 Wheelhouse size: $(du -sh "$PACKAGES_DIR" | cut -f1)"
echo "📁 Location: $PACKAGES_DIR"
echo ""
if [ $NEW_PACKAGES -eq 0 ]; then
    echo "🎉 All packages were already cached - no downloads needed!"
else
    echo "⚡ Smart caching saved time by skipping $SKIPPED_PACKAGES existing packages"
fi
