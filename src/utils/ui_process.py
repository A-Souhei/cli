"""UI process management utilities."""

import os
import sys
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
    # Note: This only kills processes bound to our specific UI_PORT (5005 by default),
    # so it's safe - we're only stopping what we started on that port.
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
    Kill a process by PID using cross-platform psutil methods.
    
    Args:
        pid: Process ID to kill
        verbose: Print status messages
        
    Returns:
        True if process was killed, False otherwise
    """
    try:
        process = psutil.Process(pid)
        
        # Try graceful shutdown first (cross-platform)
        process.terminate()

        # Wait a bit for graceful shutdown
        import time
        try:
            process.wait(timeout=1.0)
        except psutil.TimeoutExpired:
            # Force kill if still running (cross-platform)
            process.kill()
            time.sleep(0.1)

        if verbose:
            print(f"✓ UI server (PID {pid}) stopped successfully.")

        return True

    except psutil.NoSuchProcess:
        # Process already dead
        if verbose:
            print(f"UI server process (PID {pid}) already terminated.")
        return True

    except psutil.AccessDenied:
        if verbose:
            print(f"✗ Permission denied stopping process {pid}. Try with sudo.")
        return False

    except Exception as e:
        if verbose:
            print(f"Error stopping UI server (PID {pid}): {e}")
        return False


def _get_python_executable() -> str:
    """
    Get the Python executable path, preferring virtual environment if available.
    Cross-platform: handles both Unix (bin/python) and Windows (Scripts/python.exe).
    
    Returns:
        Path to the Python executable
    """
    project_root = Path(__file__).parent.parent.parent
    
    # Try Unix-style venv first
    unix_venv = project_root / "venv" / "bin" / "python"
    if unix_venv.exists():
        return str(unix_venv)
    
    # Try Windows-style venv
    windows_venv = project_root / "venv" / "Scripts" / "python.exe"
    if windows_venv.exists():
        return str(windows_venv)
    
    # Fall back to current Python executable
    return sys.executable


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

    # Get Python executable (cross-platform)
    python_exe = _get_python_executable()

    # Build command
    cmd = [python_exe, str(ui_server_script), "--port", str(UI_PORT)]
    if verbose:
        cmd.append("--verbose")

    # Start detached process with no output
    try:
        # Pass current working directory to UI server via environment variable
        env = os.environ.copy()
        if 'AI_CLI_CWD' not in env:
            env['AI_CLI_CWD'] = os.getcwd()

        # Prepare platform-specific subprocess options
        popen_kwargs = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
            'stdin': subprocess.DEVNULL,
            'cwd': str(ui_server_script.parent),
            'env': env
        }
        
        # start_new_session is not supported on Windows
        if sys.platform != 'win32':
            popen_kwargs['start_new_session'] = True
        else:
            # On Windows, use CREATE_NEW_PROCESS_GROUP for detaching
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        process = subprocess.Popen(cmd, **popen_kwargs)

        # Brief check that process started
        import time
        time.sleep(1.5)

        if not psutil.pid_exists(process.pid):
            print("✗ Failed to start UI server.")
            return False

        # Save PID only after confirming process is running
        UI_PID_FILE.write_text(str(process.pid))

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
