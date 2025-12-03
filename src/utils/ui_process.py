"""UI process management utilities."""

import os
import sys
import signal
import psutil
import subprocess
from pathlib import Path
from typing import Optional


UI_PID_FILE = Path.home() / ".ai_cli_ui.pid"
UI_PORT = int(os.getenv("UI_PORT", "18080"))


def get_running_ui_pid() -> Optional[int]:
    """
    Get the PID of the running UI server if it exists.

    Returns:
        PID of running UI server, or None if not running
    """
    if not UI_PID_FILE.exists():
        return None

    try:
        pid = int(UI_PID_FILE.read_text().strip())

        # Check if process actually exists
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            # Verify it's a Python process running the UI server
            cmdline = ' '.join(proc.cmdline())
            if 'ai-cli' in cmdline or 'main.py' in cmdline or 'ui_server_standalone' in cmdline:
                return pid

        # Stale PID file, remove it
        UI_PID_FILE.unlink(missing_ok=True)
        return None

    except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
        UI_PID_FILE.unlink(missing_ok=True)
        return None


def stop_ui_server(verbose: bool = False) -> bool:
    """
    Stop the running UI server.

    Args:
        verbose: Print status messages

    Returns:
        True if server was stopped, False if no server was running
    """
    pid = get_running_ui_pid()

    if pid is None:
        if verbose:
            print("No UI server is currently running.")
        return False

    try:
        # Try graceful shutdown first
        os.kill(pid, signal.SIGTERM)

        # Wait a bit for graceful shutdown
        import time
        for _ in range(10):
            if not psutil.pid_exists(pid):
                break
            time.sleep(0.1)

        # Force kill if still running
        if psutil.pid_exists(pid):
            os.kill(pid, signal.SIGKILL)

        UI_PID_FILE.unlink(missing_ok=True)

        if verbose:
            print(f"✓ UI server (PID {pid}) stopped successfully.")

        return True

    except (ProcessLookupError, psutil.NoSuchProcess):
        # Process already dead
        UI_PID_FILE.unlink(missing_ok=True)
        if verbose:
            print("UI server process already terminated.")
        return True

    except Exception as e:
        if verbose:
            print(f"Error stopping UI server: {e}")
        return False


def start_ui_server_background(verbose: bool = False) -> bool:
    """
    Start the UI server in background (detached process, no logs).

    Args:
        verbose: Enable verbose mode for the UI server

    Returns:
        True if server was started successfully
    """
    # First, stop any existing UI server
    stop_ui_server(verbose=False)

    # Get the path to the ui_server_standalone.py script
    ui_server_script = Path(__file__).parent.parent / "ui" / "ui_server_standalone.py"

    # Determine Python executable (prefer venv if available)
    venv_python = Path(__file__).parent.parent.parent / "venv" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    # Build command
    cmd = [python_exe, str(ui_server_script), "--port", str(UI_PORT)]
    if verbose:
        cmd.append("--verbose")

    # Start detached process with no output
    try:
        # Use subprocess.DEVNULL to suppress all output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent
            cwd=str(ui_server_script.parent)
        )

        # Save PID
        UI_PID_FILE.write_text(str(process.pid))

        # Brief check that process started
        import time
        time.sleep(1.5)

        if not psutil.pid_exists(process.pid):
            print("✗ Failed to start UI server.")
            return False

        print(f"✓ UI server started in background (PID {process.pid})")
        print(f"  Access at: http://127.0.0.1:{UI_PORT}")
        print(f"  Stop with: ai-cli --stop-ui")

        # Open browser after server starts
        import webbrowser
        import threading

        def open_browser():
            import time
            time.sleep(0.5)  # Brief delay to ensure server is ready
            webbrowser.open(f"http://127.0.0.1:{UI_PORT}")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        return True

    except Exception as e:
        print(f"✗ Error starting UI server: {e}")
        return False


def cleanup_ui_on_startup(verbose: bool = False):
    """
    Clean up any running UI servers on CLI startup.
    This ensures only one UI instance runs per working directory.

    Args:
        verbose: Print cleanup messages
    """
    pid = get_running_ui_pid()

    if pid is not None:
        if verbose:
            print(f"Cleaning up previous UI server instance (PID {pid})...")
        stop_ui_server(verbose=False)
