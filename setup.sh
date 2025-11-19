#!/bin/bash
# Setup script for AI CLI
# This script sets up the entire environment including venv and Docker containers

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================="
echo "  AI CLI - Setup Script"
echo "=================================="
echo ""

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi
print_success "Python 3 found: $(python3 --version)"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker to use containerized Ollama."
    print_info "You can still use the CLI with a local Ollama installation."
else
    print_success "Docker found: $(docker --version)"
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    if command -v docker &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose."
        print_info "You can still use the CLI with a local Ollama installation."
    fi
else
    print_success "Docker Compose found"
fi

echo ""
print_info "Setting up Python virtual environment..."

# Virtual environment directory
VENV_DIR="venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
print_info "Installing Python dependencies..."
pip install -r requirements.txt -q

if [ $? -eq 0 ]; then
    print_success "Python dependencies installed"
else
    print_error "Failed to install dependencies"
    deactivate
    exit 1
fi

# Mark requirements as installed
touch "$VENV_DIR/.requirements_installed"

deactivate

echo ""
print_info "Setting up Docker environment..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env file from .env.example"
    else
        print_info "No .env.example found, skipping .env creation"
    fi
else
    print_info ".env file already exists"
fi

# Start Docker containers if Docker is available
if command -v docker compose &> /dev/null; then
    echo ""
    read -p "Do you want to start the Ollama Docker containers now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Starting Ollama containers..."
        docker compose --profile ollama up -d
        
        if [ $? -eq 0 ]; then
            print_success "Ollama containers started"
            echo ""
            print_info "Waiting for model download (this may take a few minutes on first run)..."
            print_info "You can monitor progress with: docker compose logs -f ollama-setup"
        else
            print_error "Failed to start containers"
        fi
    fi
fi

echo ""
echo "=================================="
print_success "Setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. If you started Docker containers, wait for model download:"
echo "     docker compose logs -f ollama-setup"
echo ""
echo "  2. Run the CLI:"
echo "     ./start.sh"
echo "     or use: make run"
echo ""
echo "  3. For more commands, see:"
echo "     make help"
echo ""
