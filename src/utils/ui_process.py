"""UI process management utilities."""

import os
import sys
import signal
import psutil
import subprocess
from pathlib import Path
from typing import Optional, List


UI_PID_FILE = Path.home() / ".ai_cli_ui.pid"
UI_PORT = int(os.getenv("UI_PORT", "18080"))


def get_pids_using_port(port: int) -> List[int]:
    """
    Get PIDs of processes listening on the specified port.

    Args:
        port: Port number to check

    Returns:
        List of PIDs using the port
    """
    pids = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                if conn.pid and conn.pid not in pids:
                    pids.append(conn.pid)
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return pids


def get_running_ui_pid() -> Optional[int]:
    """
    Get the PID of the running UI server if it exists.

    Returns:
        PID of running UI server, or None if not running
    """
    # First, check the PID file
    if UI_PID_FILE.exists():
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

        except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
            UI_PID_FILE.unlink(missing_ok=True)

    # Fallback: Check for processes listening on the UI port
    port_pids = get_pids_using_port(UI_PORT)
    for pid in port_pids:
        try:
            proc = psutil.Process(pid)
            cmdline = ' '.join(proc.cmdline())
            if 'ui_server' in cmdline or 'ui/server' in cmdline:
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


def stop_ui_server(verbose: bool = False) -> bool:
    """
    Stop the running UI server.

    Args:
        verbose: Print status messages

    Returns:
        True if server was stopped, False if no server was running
    """
    stopped_any = False
    
    # First, try to find and stop via PID file or port detection
    pid = get_running_ui_pid()
    
    if pid is not None:
        stopped_any = _kill_process(pid, verbose)
    
    # Also kill any other processes on the UI port as fallback
    port_pids = get_pids_using_port(UI_PORT)
    for port_pid in port_pids:
        if port_pid != pid:  # Don't try to kill same process twice
            if _kill_process(port_pid, verbose):
                stopped_any = True
    
    # Clean up PID file
    UI_PID_FILE.unlink(missing_ok=True)
    
    if not stopped_any:
        if verbose:
            print("No UI server is currently running.")
        return False
    
    return True


def _kill_process(pid: int, verbose: bool = False) -> bool:
    """
    Kill a process by PID.
    
    Args:
        pid: Process ID to kill
        verbose: Print status messages
        
    Returns:
        True if process was killed, False otherwise
    """
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
            time.sleep(0.1)

        if verbose:
            print(f"✓ UI server (PID {pid}) stopped successfully.")

        return True

    except (ProcessLookupError, psutil.NoSuchProcess):
        # Process already dead
        if verbose:
            print(f"UI server process (PID {pid}) already terminated.")
        return True

    except PermissionError:
        if verbose:
            print(f"✗ Permission denied stopping process {pid}. Try with sudo.")
        return False

    except Exception as e:
        if verbose:
            print(f"Error stopping UI server (PID {pid}): {e}")
        return False


def start_ui_server_background(verbose: bool = False, open_browser: bool = True) -> bool:
    """
    Start the UI server in background (detached process, no logs).

    Args:
        verbose: Enable verbose mode for the UI server
        open_browser: Whether to open browser after starting (default True)

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

        # Open browser after server starts (if requested)
        if open_browser:
            import webbrowser
            import threading

            def _open_browser():
                import time
                time.sleep(0.5)  # Brief delay to ensure server is ready
                webbrowser.open(f"http://127.0.0.1:{UI_PORT}")

            browser_thread = threading.Thread(target=_open_browser)
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
