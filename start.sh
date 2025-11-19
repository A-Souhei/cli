#!/bin/bash
# Startup script for AI CLI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Virtual environment directory
VENV_DIR="venv"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        exit 1
    fi
    
    echo "Virtual environment created successfully."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

# Check if requirements are installed
if [ ! -f "$VENV_DIR/.requirements_installed" ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        deactivate
        exit 1
    fi
    
    # Mark requirements as installed
    touch "$VENV_DIR/.requirements_installed"
    echo "Dependencies installed successfully."
fi

# Run the main application
echo "Starting AI CLI..."
echo ""
python main.py

# Deactivate virtual environment on exit
deactivate
