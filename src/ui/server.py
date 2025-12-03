"""
Flask-based UI Server for AI CLI.

This module provides a web-based interface for the AI CLI, featuring:
- Session management (list, create, restore, delete)
- MCP tools discovery and details
- Code command execution
- Documentation viewer

The UI opens in a browser when the CLI is started with --show-ui flag.
"""

import os
import sys
import webbrowser
import threading
from pathlib import Path
from flask import Flask, render_template, jsonify

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.sentry_config import capture_exception
from src.ui.routes.sessions import sessions_bp
from src.ui.routes.mcps import mcps_bp
from src.ui.routes.commands import commands_bp
from src.ui.routes.docs import docs_bp
from src.ui.routes.chat import chat_bp
from src.ui.routes.files import files_bp


def create_app(verbose: bool = False) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        verbose: Enable verbose logging
        
    Returns:
        Configured Flask application
    """
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static")
    )
    
    # Store verbose flag in app config
    app.config['VERBOSE'] = verbose
    app.config['SECRET_KEY'] = os.urandom(24)
    
    # Working directory for session filtering and chat context
    app.config['WORKING_DIR'] = os.environ.get('AI_CLI_CWD', os.getcwd())
    
    # Original directory where CLI was opened (for explorer root - never changes)
    # This is set in main.py at startup to capture the true original directory
    app.config['EXPLORER_ROOT'] = os.environ.get('AI_CLI_ORIGINAL_DIR', os.getcwd())
    
    # Register blueprints
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    app.register_blueprint(mcps_bp, url_prefix='/api/mcps')
    app.register_blueprint(commands_bp, url_prefix='/api/commands')
    app.register_blueprint(docs_bp, url_prefix='/api/docs')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(files_bp, url_prefix='/api/files')
    
    @app.route('/')
    def index():
        """Main page - redirect to chat."""
        return render_template('chat.html', working_dir=app.config['WORKING_DIR'])
    
    @app.route('/dashboard')
    def dashboard_page():
        """Dashboard page."""
        return render_template('index.html', working_dir=app.config['WORKING_DIR'])
    
    @app.route('/chat')
    def chat_page():
        """Chat page for sending prompts."""
        return render_template('chat.html', working_dir=app.config['WORKING_DIR'])
    
    @app.route('/sessions')
    def sessions_page():
        """Sessions management page."""
        return render_template('sessions.html', working_dir=app.config['WORKING_DIR'])
    
    @app.route('/mcps')
    def mcps_page():
        """MCPs page."""
        return render_template('mcps.html')
    
    @app.route('/mcps/<mcp_name>')
    def mcp_tools_page(mcp_name):
        """MCP tools page."""
        return render_template('mcp_tools.html', mcp_name=mcp_name)
    
    @app.route('/docs')
    def docs_page():
        """Documentation page."""
        return render_template('docs.html')
    
    @app.route('/explorer')
    def explorer_page():
        """File explorer page."""
        return render_template('explorer.html', working_dir=app.config['WORKING_DIR'])
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'ai-cli-ui',
            'working_dir': app.config['WORKING_DIR']
        })
    
    @app.errorhandler(Exception)
    def handle_error(e):
        """Global error handler."""
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
    return app


def start_ui_server(host: str = '127.0.0.1', port: int = 18080, verbose: bool = False):
    """
    Start the UI server and open browser.
    
    This function blocks until the server is stopped (Ctrl+C).
    The CLI is not available while the UI is running.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        verbose: Enable verbose logging
    """
    from rich.console import Console
    
    console = Console()
    
    console.print("\n🌐 [bold cyan]Starting AI CLI Web Interface...[/bold cyan]\n")
    console.print("  [yellow]⚠️  CLI is blocked while UI is running[/yellow]")
    
    app = create_app(verbose=verbose)
    
    url = f"http://{host}:{port}"
    console.print(f"  📍 Server: [green]{url}[/green]")
    console.print(f"  📂 Working Directory: [dim]{app.config['WORKING_DIR']}[/dim]")
    
    if verbose:
        console.print("  🔍 [dim]Verbose mode enabled[/dim]")
    
    console.print()
    console.print("  [dim]Press Ctrl+C to stop the server and return to terminal[/dim]\n")
    
    # Open browser in a separate thread after a short delay
    def open_browser():
        import time
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open(url)
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        # Run Flask server
        app.run(
            host=host,
            port=port,
            debug=verbose,
            use_reloader=False  # Disable reloader to prevent double browser open
        )
    except KeyboardInterrupt:
        console.print("\n👋 [bold]UI Server stopped[/bold]\n")
