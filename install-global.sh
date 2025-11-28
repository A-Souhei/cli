#!/bin/bash
# Install AI CLI globally
# This script creates a symlink in ~/.local/bin to allow running 'ai-cli' from anywhere

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Installation target directory
INSTALL_DIR="${HOME}/.local/bin"
CLI_NAME="ai-cli"

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

echo ""
echo -e "${BLUE}=================================="
echo "  AI CLI - Global Installation"
echo -e "==================================${NC}"
echo ""

# Update the CLI_DIR in the wrapper script
WRAPPER_SCRIPT="$SCRIPT_DIR/ai-cli"

if [ ! -f "$WRAPPER_SCRIPT" ]; then
    print_error "Wrapper script not found: $WRAPPER_SCRIPT"
    exit 1
fi

# Update the CLI_DIR path in the wrapper script
sed -i "s|^CLI_DIR=.*|CLI_DIR=\"$SCRIPT_DIR\"|" "$WRAPPER_SCRIPT"
print_success "Updated CLI_DIR path in wrapper script"

# Make the wrapper script executable
chmod +x "$WRAPPER_SCRIPT"
print_success "Made wrapper script executable"

# Create ~/.local/bin if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    print_success "Created directory: $INSTALL_DIR"
fi

# Remove existing symlink if it exists
if [ -L "$INSTALL_DIR/$CLI_NAME" ]; then
    rm "$INSTALL_DIR/$CLI_NAME"
    print_info "Removed existing symlink"
elif [ -f "$INSTALL_DIR/$CLI_NAME" ]; then
    print_error "A file named '$CLI_NAME' already exists in $INSTALL_DIR"
    print_info "Please remove it manually and run this script again"
    exit 1
fi

# Create symlink
ln -s "$WRAPPER_SCRIPT" "$INSTALL_DIR/$CLI_NAME"
print_success "Created symlink: $INSTALL_DIR/$CLI_NAME -> $WRAPPER_SCRIPT"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    print_info "~/.local/bin is not in your PATH"
    echo ""
    echo "Add the following line to your shell configuration file:"
    echo ""
    echo -e "  ${GREEN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo ""
    echo "For bash, add it to ~/.bashrc:"
    echo -e "  ${YELLOW}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc${NC}"
    echo -e "  ${YELLOW}source ~/.bashrc${NC}"
    echo ""
    echo "For zsh, add it to ~/.zshrc:"
    echo -e "  ${YELLOW}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc${NC}"
    echo -e "  ${YELLOW}source ~/.zshrc${NC}"
    echo ""
else
    print_success "~/.local/bin is already in your PATH"
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "You can now run the AI CLI from any directory using:"
echo -e "  ${BLUE}$CLI_NAME${NC}"
echo ""
echo "Or with arguments:"
echo -e "  ${BLUE}$CLI_NAME --help${NC}"
echo -e "  ${BLUE}$CLI_NAME -m \"your message\"${NC}"
echo ""
