#!/usr/bin/env python3
"""
Standalone UI server script for background execution.
This script is launched by the --show-ui flag in detached mode.
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ui.server import create_app


def main():
    """Run the UI server."""
    parser = argparse.ArgumentParser(description="AI CLI UI Server")
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose mode'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=18080,
        help='Port to listen on (default: 18080)'
    )
    args = parser.parse_args()

    # Create Flask app
    app = create_app(verbose=args.verbose)

    # Run server
    app.run(
        host=args.host,
        port=args.port,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    main()
