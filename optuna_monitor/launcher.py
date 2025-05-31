#!/usr/bin/env python3

import argparse
import subprocess
import sys
import os
import time
import atexit
import signal
from . import human_trial_monitor # Import the human_trial_monitor module
import threading
import socket

# List to keep track of child processes
CHILD_PROCESSES = []

# SSH tunnel process
SSH_TUNNEL_PROCESS = None

def cleanup_processes():
    """Terminate all child processes."""
    print("\nStopping services...")
    for p in CHILD_PROCESSES:
        if p.poll() is None:  # Process is still running
            print(f"Terminating process {p.pid}...")
            p.terminate()
            p.wait(timeout=5)
            if p.poll() is None:
                print(f"Killing process {p.pid}...")
                p.kill()
    
    # Clean up SSH tunnel if it exists
    global SSH_TUNNEL_PROCESS
    if SSH_TUNNEL_PROCESS and SSH_TUNNEL_PROCESS.poll() is None:
        print("Terminating SSH tunnel...")
        SSH_TUNNEL_PROCESS.terminate()
        SSH_TUNNEL_PROCESS.wait(timeout=5)
        if SSH_TUNNEL_PROCESS.poll() is None:
            print("Killing SSH tunnel...")
            SSH_TUNNEL_PROCESS.kill()
    
    print("Cleaned up and stopped services.")

# Register cleanup function to be called on exit
atexit.register(cleanup_processes)

# Handle signals for graceful shutdown
def signal_handler(signum, frame):
    print(f"Signal {signum} received. Initiating graceful shutdown...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def package_installed(package_name):
    """Check if a Python package is installed."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "show", package_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def install_package(package_name):
    """Install a Python package."""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package_name}: {e}", file=sys.stderr)
        sys.exit(1)

def find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True

def wait_for_port_available(port, timeout=30):
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False

def kill_process_on_port(port):
    """Try to kill process using the specified port."""
    try:
        # Try lsof first (Linux/Mac)
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip()
            print(f"Found process {pid} using port {port}, attempting to kill...")
            subprocess.run(['kill', '-9', pid])
            time.sleep(1)
            return True
    except FileNotFoundError:
        # lsof not available, try netstat
        pass
    
    try:
        # Alternative: use netstat (more universal)
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTEN' in line:
                # Extract PID from the line
                parts = line.split()
                if len(parts) >= 7:
                    pid_prog = parts[6]
                    if '/' in pid_prog:
                        pid = pid_prog.split('/')[0]
                        print(f"Found process {pid} using port {port}, attempting to kill...")
                        subprocess.run(['kill', '-9', pid])
                        time.sleep(1)
                        return True
    except Exception:
        pass
    
    try:
        # Last resort: use ss command
        result = subprocess.run(['ss', '-tlnp', f'sport = :{port}'], capture_output=True, text=True)
        if 'pid=' in result.stdout:
            # Extract PID
            import re
            match = re.search(r'pid=(\d+)', result.stdout)
            if match:
                pid = match.group(1)
                print(f"Found process {pid} using port {port}, attempting to kill...")
                subprocess.run(['kill', '-9', pid])
                time.sleep(1)
                return True
    except Exception:
        pass
    
    print(f"Could not find/kill process on port {port} (tried lsof, netstat, ss)")
    return False

def create_ssh_tunnel(ssh_host, ssh_user, ssh_port, db_host, db_port, ssh_key_path=None, ssh_password=None):
    """Create an SSH tunnel and return the local port."""
    global SSH_TUNNEL_PROCESS
    
    local_port = find_free_port()
    
    # Build SSH command
    ssh_cmd = ["ssh", "-N", "-L", f"{local_port}:{db_host}:{db_port}"]
    
    if ssh_key_path:
        ssh_cmd.extend(["-i", ssh_key_path])
    
    if ssh_port != 22:
        ssh_cmd.extend(["-p", str(ssh_port)])
    
    # Add connection options for better reliability
    ssh_cmd.extend([
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=60",
        "-o", "ServerAliveCountMax=3"
    ])
    
    ssh_cmd.append(f"{ssh_user}@{ssh_host}")
    
    print(f"Creating SSH tunnel: {' '.join(ssh_cmd)}")
    
    try:
        SSH_TUNNEL_PROCESS = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for the tunnel to establish
        time.sleep(3)
        
        # Check if the process is still running
        if SSH_TUNNEL_PROCESS.poll() is not None:
            stdout, stderr = SSH_TUNNEL_PROCESS.communicate()
            print(f"SSH tunnel failed to start. Error: {stderr.decode()}", file=sys.stderr)
            sys.exit(1)
        
        print(f"SSH tunnel established on local port {local_port}")
        return local_port
        
    except Exception as e:
        print(f"Error creating SSH tunnel: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Launch Optuna Dashboard and Human-in-the-Loop Monitor.")

    # Database connection options
    db_group = parser.add_argument_group('Database connection')
    db_group.add_argument("--db-url", help="Database URL for Optuna storage")
    db_group.add_argument("--db-host", default="localhost", help="Database hostname (default: localhost)")
    db_group.add_argument("--db-port", help="Database port (default: 5432 for postgresql, 3306 for mysql)")
    db_group.add_argument("--db-name", default="optuna", help="Database name (default: optuna)")
    db_group.add_argument("--db-user", default="optuna", help="Database username (default: optuna)")
    db_group.add_argument("--db-password", default="password", help="Database password (default: password)")
    db_group.add_argument("--db-type", default="postgresql", choices=["postgresql", "mysql", "sqlite"], help="Database type (postgresql, mysql, sqlite) (default: postgresql)")
    db_group.add_argument("--cert-path", help="Path to CA certificate file")
    db_group.add_argument("--use-cert", action="store_true", help="Explicitly use the certificate specified by --cert-path (overrides --no-cert)")
    db_group.add_argument("--no-cert", action="store_true", help="Explicitly disable certificate usage (overrides --cert-path and default detection)")
    
    # SSH tunnel options
    ssh_group = parser.add_argument_group('SSH tunnel options')
    ssh_group.add_argument("--ssh-host", help="SSH host for tunneling (e.g., jump.example.com)")
    ssh_group.add_argument("--ssh-user", help="SSH username for tunneling")
    ssh_group.add_argument("--ssh-port", type=int, default=22, help="SSH port for tunneling (default: 22)")
    ssh_group.add_argument("--ssh-key", help="Path to SSH private key file")
    ssh_group.add_argument("--ssh-password", help="SSH password (not recommended, use SSH keys instead)")

    # Monitor configuration
    monitor_group = parser.add_argument_group('Monitor configuration')
    monitor_group.add_argument("--port", type=int, default=8080, help="Specify port for optuna-dashboard (default: 8080)")
    monitor_group.add_argument("--force-port", action="store_true", help="Force use of specified port by killing existing process if needed")
    monitor_group.add_argument("--study", nargs='*', help="Specify one or more study names to monitor (default: monitor all studies if none specified)")
    monitor_group.add_argument("--interval", type=int, default=10, help="Monitor check interval in seconds (default: 10)")
    monitor_group.add_argument("--prune-pattern", default="PRUNE", help="Regex pattern to detect PRUNE commands (default: 'PRUNE')")
    monitor_group.add_argument("--fail-pattern", default="FAIL", help="Regex pattern to detect FAIL commands (default: 'FAIL')")
    monitor_group.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes applied)")
    monitor_group.add_argument("--all-trials", action="store_true", help="Monitor all trials, not just active ones")
    monitor_group.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # Browser launch options
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument("--browser-path", help="Launch specified browser executable with the dashboard URL.")

    args = parser.parse_args()

    # Validate SSH tunnel arguments
    if (args.ssh_host or args.ssh_user) and not (args.ssh_host and args.ssh_user):
        print("Error: Both --ssh-host and --ssh-user must be specified when using SSH tunneling", file=sys.stderr)
        sys.exit(1)
    
    if args.ssh_key and args.ssh_password:
        print("Warning: Both SSH key and password specified. SSH key will be used.", file=sys.stderr)
    
    if args.ssh_host and args.ssh_user and not args.ssh_key and not args.ssh_password:
        print("Warning: No SSH authentication method specified. SSH agent or default key will be used.", file=sys.stderr)

    # Handle SSH tunneling if specified
    original_db_host = args.db_host
    original_db_port = args.db_port
    
    if args.ssh_host and args.ssh_user:
        if not args.db_host or args.db_host == "localhost":
            print("Error: When using SSH tunnel, you must specify the actual database host with --db-host", file=sys.stderr)
            sys.exit(1)
        
        # Set default port if not provided
        if not original_db_port:
            if args.db_type == "postgresql":
                original_db_port = "5432"
            elif args.db_type == "mysql":
                original_db_port = "3306"
            else:
                print(f"Warning: No default port for DB_TYPE: {args.db_type}. Please specify --db-port.", file=sys.stderr)
                sys.exit(1)
        
        print(f"Setting up SSH tunnel to {args.ssh_user}@{args.ssh_host} for database {original_db_host}:{original_db_port}")
        
        # Create SSH tunnel
        local_port = create_ssh_tunnel(
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_port=args.ssh_port,
            db_host=original_db_host,
            db_port=original_db_port,
            ssh_key_path=args.ssh_key,
            ssh_password=args.ssh_password
        )
        
        # Update connection parameters to use the tunnel
        args.db_host = "localhost"
        args.db_port = str(local_port)
        
        print(f"Database connection will use SSH tunnel: localhost:{local_port} -> {original_db_host}:{original_db_port}")
    
    # Determine DB URL
    db_url = args.db_url
    if not db_url:
        # Certificate handling
        use_cert = False
        cert_path = args.cert_path
        if args.no_cert:
            use_cert = False
            cert_path = ""
        elif args.use_cert:
            if not cert_path:
                print("Error: --use-cert specified but no --cert-path provided.", file=sys.stderr)
                sys.exit(1)
            if not os.path.exists(cert_path):
                print(f"Error: Certificate file not found at {cert_path}", file=sys.stderr)
                sys.exit(1)
            use_cert = True
        else:
            # Auto-detect default cert
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_cert_path = os.path.join(script_dir, "cert", "ca.pem")
            if os.path.exists(default_cert_path):
                cert_path = default_cert_path
                use_cert = True
                print(f"Automatically using default CA certificate at {cert_path}")
            else:
                cert_path = ""
                use_cert = False

        # Set default port if not provided
        db_port = args.db_port
        if not db_port:
            if args.db_type == "postgresql":
                db_port = "5432"
            elif args.db_type == "mysql":
                db_port = "3306"
            else:
                print(f"Warning: No default port for DB_TYPE: {args.db_type}. Please specify --db-port.", file=sys.stderr)
                sys.exit(1) # Exit if port is critical and not provided

        # Construct DB URL from components
        if args.db_type == "postgresql":
            db_url = f"postgresql://{args.db_user}:{args.db_password}@{args.db_host}:{db_port}/{args.db_name}"
            if use_cert and cert_path:
                db_url = f"{db_url}?sslmode=require&sslrootcert={cert_path}"
        elif args.db_type == "mysql":
            db_url = f"mysql://{args.db_user}:{args.db_password}@{args.db_host}:{db_port}/{args.db_name}"
            if use_cert and cert_path:
                db_url = f"{db_url}?ssl_ca={cert_path}"
        elif args.db_type == "sqlite":
            db_url = f"sqlite:///{args.db_name}"
        else:
            print(f"Error: Unsupported database type: {args.db_type}", file=sys.stderr)
            sys.exit(1)

    if not db_url:
        print("Database URL is required. Provide either --db-url or all of: --db-host, --db-port, --db-name, --db-user, --db-password", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to database associated with host: {args.db_host or db_url.split('@')[-1].split('/')[0]}")

    # Install required packages
    print("Checking required packages...")
    required_packages = ["optuna", "optuna-dashboard"]
    if args.db_type == "postgresql":
        required_packages.append("psycopg2-binary")
    elif args.db_type == "mysql":
        required_packages.append("mysqlclient")

    for pkg in required_packages:
        if not package_installed(pkg):
            install_package(pkg)

    # Check port availability and handle conflicts
    if is_port_in_use(args.port):
        print(f"Port {args.port} is already in use.")
        if args.force_port:
            print(f"Force mode enabled. Attempting to kill process on port {args.port}...")
            if kill_process_on_port(args.port):
                print(f"Successfully killed process on port {args.port}")
                # Wait a bit for port to be released
                if not wait_for_port_available(args.port, timeout=5):
                    print(f"Error: Port {args.port} still in use after killing process", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"Error: Could not kill process on port {args.port}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Use --force-port to kill the existing process, or choose a different port with --port", file=sys.stderr)
            sys.exit(1)

    # Launch Optuna Dashboard
    print(f"Starting optuna-dashboard on port {args.port}...")
    # Call optuna-dashboard directly as a command
    dashboard_cmd = ["optuna-dashboard", db_url, "--port", str(args.port)]
    dashboard_process = subprocess.Popen(dashboard_cmd, preexec_fn=os.setsid) # Use os.setsid to create a new process group
    CHILD_PROCESSES.append(dashboard_process)
    print("Loading all studies from the database")

    # Wait for dashboard to initialize with retries
    print("Waiting for dashboard to initialize...")
    max_retries = 10
    for i in range(max_retries):
        time.sleep(1)
        if dashboard_process.poll() is not None:
            # Process died
            stdout, stderr = dashboard_process.communicate()
            print(f"Error: Optuna dashboard failed to start", file=sys.stderr)
            if stderr:
                print(f"Error details: {stderr.decode()}", file=sys.stderr)
            sys.exit(1)
        
        # Check if port is now in use (dashboard started successfully)
        if is_port_in_use(args.port):
            print("Dashboard initialized successfully")
            break
    else:
        print("Warning: Could not confirm dashboard started, but proceeding...")

    # Check if we should start the monitor
    should_start_monitor = True
    if not args.study or (args.study and all(not s.strip() for s in args.study)):
        # No studies specified or all are empty strings
        print("No studies specified for monitoring.")
        print("Dashboard will run without the Human-in-the-loop monitor.")
        print("To enable monitoring, specify studies with --study study1 study2 or --study all")
        should_start_monitor = False
    
    # Launch Human Trial Monitor in a separate thread (if needed)
    monitor_thread = None
    monitor_error = None
    
    if should_start_monitor:
        print("Starting Human-in-the-loop Trial Monitor...")
        
        def run_monitor():
            nonlocal monitor_error
            try:
                # Pass arguments directly to human_trial_monitor.main()
                monitor_args = [
                f"--db-url={db_url}",
                f"--interval={args.interval}",
                f"--prune-pattern={args.prune_pattern}",
                f"--fail-pattern={args.fail_pattern}"
                ]
                if args.study:
                    # Pass each study name as a separate --study argument
                    for study_name in args.study:
                        monitor_args.extend(["--study", study_name])
                if args.dry_run:
                    monitor_args.append("--dry-run")
                if not args.all_trials:
                    monitor_args.append("--only-active-trials") # Monitor only active trials by default
                if args.verbose:
                    monitor_args.append("--verbose")

                # Temporarily replace sys.argv to pass arguments to human_trial_monitor.main()
                original_argv = sys.argv
                sys.argv = [human_trial_monitor.__file__] + monitor_args
                try:
                    monitor_exit_code = human_trial_monitor.main()
                    if monitor_exit_code != 0:
                        monitor_error = f"Human Trial Monitor exited with code {monitor_exit_code}"
                finally:
                    sys.argv = original_argv # Restore sys.argv
            except Exception as e:
                monitor_error = f"Error in monitor thread: {e}"
        
        # Start monitor in thread
        monitor_thread = threading.Thread(target=run_monitor, name="HumanTrialMonitorLauncher")
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Wait a bit to ensure monitor starts properly
        time.sleep(2)
        if monitor_error:
            print(f"Error: {monitor_error}", file=sys.stderr)
            # Continue anyway - dashboard can still be useful without monitor

    print("Services are running:")
    print(f"- Dashboard: http://localhost:{args.port}")
    if should_start_monitor:
        print("- Human-in-the-loop Monitor: Active and connected to the database")
    else:
        print("- Human-in-the-loop Monitor: Not running (no studies specified)")
    print("The services will automatically stop when this terminal is closed.")
    print("To use: Add a note with 'PRUNE' or 'FAIL' to any trial in the dashboard to change its state.")
    if args.dry_run:
        print("NOTE: Running in DRY-RUN mode - no actual trial state changes will be made.")

    # Launch browser
    dashboard_url = f"http://localhost:{args.port}"
    if args.browser_path:
        print(f"Attempting to launch custom browser: {args.browser_path}")
        try:
            browser_process = subprocess.Popen([args.browser_path, dashboard_url], preexec_fn=os.setsid,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            CHILD_PROCESSES.append(browser_process)
            print("Custom browser process launched.")
        except FileNotFoundError:
            print(f"Error: Custom browser executable not found at {args.browser_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error launching custom browser: {e}", file=sys.stderr)

    print("\nPress Ctrl+C to stop all services.")
    try:
        # Keep the main script running indefinitely
        while True:
            time.sleep(1)
            # Check if dashboard or monitor processes have died
            if dashboard_process.poll() is not None:
                print("Optuna Dashboard process terminated unexpectedly.", file=sys.stderr)
                break
            # The monitor is now in-process, so no separate process to check
            # if monitor_process.poll() is not None:
            #     print("Human Trial Monitor process terminated unexpectedly.", file=sys.stderr)
            #     break
    except KeyboardInterrupt:
        print("Ctrl+C received. Stopping services...")
    finally:
        cleanup_processes()

if __name__ == "__main__":
    main()