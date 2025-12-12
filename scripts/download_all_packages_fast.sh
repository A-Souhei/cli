#!/bin/bash
set -e

# Fast package downloader using wget instead of pip download
# This is MUCH faster as it downloads directly from PyPI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGES_DIR="$PROJECT_ROOT/packages"

echo "=========================================="
echo "⚡ Fast Python Package Downloader (wget)"
echo "=========================================="

mkdir -p "$PACKAGES_DIR"

NEW_PACKAGES=0
SKIPPED_PACKAGES=0

# Function to download with ALL dependencies (no --no-deps) for offline builds
download_with_deps() {
    local package_spec="$1"
    local indent="${2:-  }"
    local pkg_name=$(echo "$package_spec" | sed 's/[>=<\[].*//g' | tr -d ' ')
    
    echo "${indent}📦 $pkg_name (downloading with all dependencies)"
    
    # Download with pip to get ALL dependencies, matching Docker's Python 3.11
    # Remove --no-deps to ensure ALL transitive dependencies are downloaded for offline use
    python3 -m pip download -d "$PACKAGES_DIR" \
        --python-version 311 \
        --only-binary=:all: \
        --progress-bar on \
        "$package_spec" 2>&1 | while IFS= read -r line; do
        if [[ "$line" =~ Collecting ]]; then
            echo "${indent}  $line"
        elif [[ "$line" =~ Downloading ]]; then
            echo "${indent}  ⬇ $line"
        elif [[ "$line" =~ Saved|Successfully ]]; then
            echo "${indent}  ✓ $line"
        fi
    done
    
    NEW_PACKAGES=$((NEW_PACKAGES + 1))
}

# Function to get download URL from PyPI JSON API (for direct wget)
get_wheel_url() {
    local package_spec="$1"
    local pkg_name=$(echo "$package_spec" | sed 's/[>=<\[].*//g' | tr -d ' ')
    local version=$(echo "$package_spec" | grep -oP '==\K[^,\]]+' || echo "")
    
    if [ -z "$version" ]; then
        # Get latest version
        local url="https://pypi.org/pypi/$pkg_name/json"
    else
        local url="https://pypi.org/pypi/$pkg_name/$version/json"
    fi
    
    # Get the wheel URL for the current platform (prefer cp311 for Python 3.11 in Dockerfile)
    curl -s "$url" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    urls = data.get('urls', [])
    
    # Priority order: cp311-manylinux > cp311-any > py3-none-any > any wheel
    # First try: cp311 with manylinux (matches python:3.11-slim in Dockerfile)
    for url_data in urls:
        filename = url_data['filename']
        if filename.endswith('.whl') and 'cp311' in filename and 'manylinux' in filename:
            print(url_data['url'])
            sys.exit(0)
    
    # Second try: cp311 any platform
    for url_data in urls:
        filename = url_data['filename']
        if filename.endswith('.whl') and 'cp311' in filename:
            print(url_data['url'])
            sys.exit(0)
    
    # Third try: py3-none-any (universal wheels)
    for url_data in urls:
        filename = url_data['filename']
        if filename.endswith('.whl') and 'py3-none-any' in filename:
            print(url_data['url'])
            sys.exit(0)
    
    # Fallback: any wheel
    for url_data in urls:
        if url_data['filename'].endswith('.whl'):
            print(url_data['url'])
            sys.exit(0)
except:
    pass
" 2>/dev/null
}

# Function to check if package exists
package_exists() {
    local pkg="$1"
    local normalized=$(echo "$pkg" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g' | sed 's/\[.*\]//g')
    if ls "$PACKAGES_DIR"/${normalized}-*.whl 2>/dev/null | grep -q .; then
        return 0
    fi
    return 1
}

# Function to download package
download_package() {
    local package_spec="$1"
    local pkg_name=$(echo "$package_spec" | sed 's/[>=<\[].*//g' | tr -d ' ')
    
    if package_exists "$pkg_name"; then
        echo "  ✓ $pkg_name (cached)"
        SKIPPED_PACKAGES=$((SKIPPED_PACKAGES + 1))
        return
    fi
    
    echo "  ↓ $pkg_name (downloading)"
    local wheel_url=$(get_wheel_url "$package_spec")
    
    if [ -n "$wheel_url" ]; then
        # Show progress bar with wget
        wget --progress=bar:force -P "$PACKAGES_DIR" "$wheel_url" 2>&1 | grep -E "%" && NEW_PACKAGES=$((NEW_PACKAGES + 1)) || echo "    ⚠ Failed to download $pkg_name"
    else
        echo "    ⚠ Could not find wheel URL for $pkg_name, falling back to pip"
        echo "    📦 Using pip (with dependencies)..."
        pip download -d "$PACKAGES_DIR" --progress-bar on "$package_spec" 2>&1 | grep -E "(Collecting|Downloading|Saved)" && NEW_PACKAGES=$((NEW_PACKAGES + 1)) || true
    fi
}

# Download from requirements files
download_from_file() {
    local file="$1"
    local category="$2"
    
    echo ""
    echo "📦 Processing $category..."
    echo "------------------------------------------"
    
    if [ ! -f "$file" ]; then
        return
    fi
    
    while IFS= read -r line || [ -n "$line" ]; do
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        download_package "$line"
    done < "$file"
}

# Download from inline package list
download_from_list() {
    local packages="$1"
    local category="$2"
    
    echo ""
    echo "📦 Processing $category..."
    echo "------------------------------------------"
    
    for pkg in $packages; do
        download_package "$pkg"
    done
}

# Process all services
download_from_file "$PROJECT_ROOT/src/transformer/requirements.txt" "Transformer Service"
download_from_file "$PROJECT_ROOT/ollama_api_service/requirements.txt" "Ollama API Service"
download_from_file "$PROJECT_ROOT/requirements.txt" "Main CLI"

download_from_list "flask flask-sqlalchemy psycopg2-binary python-dotenv pgvector sentry-sdk pyyaml" "PostgreSQL Service"
download_from_list "Flask==2.3.2 redis==5.0.1 requests==2.31.0 sentry-sdk==1.29.2" "Redis API Service"
download_from_list "Flask==2.3.2 Flask-SQLAlchemy==3.0.5 psycopg2-binary==2.9.6 sentry-sdk==1.29.2 requests==2.31.0 pyyaml==6.0" "PostgreSQL Flask App"

# Heavy packages - download with dependencies visible
echo ""
echo "📦 Processing Heavy ML Packages (with dependencies)..."
echo "------------------------------------------"
echo "  ℹ️  Note: Downloading exact versions to match Docker Python 3.11"
echo ""

# Download torch with all CUDA dependencies from requirements-torch.txt
if [ -f "$PROJECT_ROOT/requirements-torch.txt" ]; then
    echo "  📦 Downloading PyTorch + CUDA dependencies from requirements-torch.txt..."
    python3 -m pip download -r "$PROJECT_ROOT/requirements-torch.txt" \
        --python-version 311 \
        --only-binary=:all: \
        --dest "$PACKAGES_DIR" 2>&1 | grep -E "(Downloading|Saved|Successfully)" | while IFS= read -r line; do
        echo "    $line"
    done
    NEW_PACKAGES=$((NEW_PACKAGES + $(ls -1 "$PACKAGES_DIR"/*.whl 2>/dev/null | wc -l)))
else
    echo "  ⚠️  requirements-torch.txt not found, using individual download"
    download_with_deps "torch==2.1.2" "  "
fi

download_with_deps "transformers==4.36.2" "  "
download_with_deps "sentence-transformers==2.7.0" "  "

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
    echo "⚡ Fast wget downloads saved significant time!"
fi
