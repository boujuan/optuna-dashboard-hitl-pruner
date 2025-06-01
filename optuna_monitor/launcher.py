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
    print(f"Waiting up to {timeout} seconds for port {port} to become available...")
    start_time = time.time()
    last_check_time = 0
    
    while time.time() - start_time < timeout:
        current_time = time.time() - start_time
        if not is_port_in_use(port):
            print(f"Port {port} is now available after {current_time:.1f} seconds")
            return True
        
        # Show progress every 5 seconds
        if current_time - last_check_time >= 5:
            print(f"Still waiting for port {port}... ({current_time:.0f}s elapsed)")
            last_check_time = current_time
            
            # Try to find what's still using the port
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    remaining_pids = result.stdout.strip().split('\n')
                    print(f"Processes still using port {port}: {', '.join(remaining_pids)}")
            except:
                pass
        
        time.sleep(1)
    
    print(f"Timeout waiting for port {port} to become available")
    return False


def kill_process_on_port(port):
    """Try to kill ALL processes using the specified port."""
    killed_any = False
    pids_to_kill = set()
    
    # Step 1: Collect ALL PIDs using the port
    try:
        # Try lsof first - it can return multiple PIDs
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            # lsof returns one PID per line
            for line in result.stdout.strip().split('\n'):
                if line.strip().isdigit():
                    pids_to_kill.add(line.strip())
    except FileNotFoundError:
        pass
    
    # Also try fuser which is good at finding all processes
    try:
        result = subprocess.run(['fuser', f'{port}/tcp'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.stdout:
            # fuser output format: "8080/tcp:   12345 12346 12347"
            parts = result.stdout.split()
            for part in parts:
                if part.isdigit():
                    pids_to_kill.add(part)
    except FileNotFoundError:
        pass
    
    # Try netstat as backup
    if not pids_to_kill:
        try:
            result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTEN' in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        pid_prog = parts[6]
                        if '/' in pid_prog:
                            pid = pid_prog.split('/')[0]
                            if pid.isdigit():
                                pids_to_kill.add(pid)
        except Exception:
            pass
    
    # Try ss as last resort
    if not pids_to_kill:
        try:
            result = subprocess.run(['ss', '-tlnp', f'sport = :{port}'], capture_output=True, text=True)
            import re
            for match in re.finditer(r'pid=(\d+)', result.stdout):
                pids_to_kill.add(match.group(1))
        except Exception:
            pass
    
    if not pids_to_kill:
        print(f"Could not find any process using port {port}")
        return False
    
    print(f"Found {len(pids_to_kill)} process(es) using port {port}: {', '.join(pids_to_kill)}")
    
    # Step 2: Kill all processes and their children
    for pid in pids_to_kill:
        try:
            # First try to kill the entire process group
            print(f"Killing process {pid} and its children...")
            
            # Try pkill to kill process tree
            subprocess.run(['pkill', '-TERM', '-P', pid], capture_output=True)
            time.sleep(0.5)
            
            # Then kill the main process
            subprocess.run(['kill', '-TERM', pid], capture_output=True)
            time.sleep(0.5)
            
            # Force kill if still alive
            subprocess.run(['kill', '-9', pid], capture_output=True)
            killed_any = True
            
        except Exception as e:
            print(f"Error killing process {pid}: {e}")
    
    # Step 3: Extra cleanup - kill any remaining processes by name
    try:
        # Common process names that might hold the port
        for proc_name in ['node', 'python', 'gunicorn', 'optuna-dashboard']:
            result = subprocess.run(['pgrep', '-f', proc_name], capture_output=True, text=True)
            if result.returncode == 0:
                for pid in result.stdout.strip().split('\n'):
                    if pid.strip().isdigit():
                        # Check if this process is actually using our port
                        check = subprocess.run(['lsof', '-p', pid, '-i', f':{port}'], 
                                             capture_output=True, text=True)
                        if check.returncode == 0 and check.stdout:
                            print(f"Found {proc_name} process {pid} still using port, killing...")
                            subprocess.run(['kill', '-9', pid], capture_output=True)
                            killed_any = True
    except:
        pass
    
    # Wait a bit longer for ports to be released
    if killed_any:
        print("Waiting for port to be released...")
        time.sleep(3)
        
        # WSL-specific: Sometimes we need to wait longer for port release
        if os.path.exists('/proc/version'):
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        print("WSL detected - waiting additional time for port release...")
                        time.sleep(2)
            except:
                pass
    
    return killed_any

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
            _, stderr = SSH_TUNNEL_PROCESS.communicate()
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
    monitor_group.add_argument("--cleanup-port", action="store_true", help="Only cleanup processes on the specified port and exit (useful for stuck ports)")
    monitor_group.add_argument("--study", nargs='*', help="Specify one or more study names to monitor (default: monitor all studies if none specified)")
    monitor_group.add_argument("--interval", type=int, default=10, help="Monitor check interval in seconds (default: 10)")
    monitor_group.add_argument("--prune-pattern", default="PRUNE", help="Regex pattern to detect PRUNE commands (default: 'PRUNE')")
    monitor_group.add_argument("--fail-pattern", default="FAIL", help="Regex pattern to detect FAIL commands (default: 'FAIL')")
    monitor_group.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes applied)")
    monitor_group.add_argument("--all-trials", action="store_true", help="Monitor RUNNING, WAITING, and COMPLETE trials (default: only RUNNING and WAITING)")
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

    # Handle cleanup-only mode
    if args.cleanup_port:
        print(f"Cleanup-only mode: Cleaning up processes on port {args.port}")
        if is_port_in_use(args.port):
            print(f"Port {args.port} is in use. Attempting to clean up...")
            if kill_process_on_port(args.port):
                if wait_for_port_available(args.port, timeout=15):
                    print(f"✅ Successfully cleaned up port {args.port}")
                    sys.exit(0)
                else:
                    print(f"❌ Port {args.port} is still in use after cleanup")
                    sys.exit(1)
            else:
                print(f"❌ Could not clean up port {args.port}")
                sys.exit(1)
        else:
            print(f"✅ Port {args.port} is already free")
            sys.exit(0)

    # Check port availability and handle conflicts
    if is_port_in_use(args.port):
        print(f"Port {args.port} is already in use.")
        if args.force_port:
            print(f"Force mode enabled. Attempting to kill process on port {args.port}...")
            
            # Show what's using the port before killing
            try:
                result = subprocess.run(['lsof', '-ti', f':{args.port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    print(f"Processes using port {args.port}: {', '.join(pids)}")
            except:
                pass
            
            if kill_process_on_port(args.port):
                print(f"Process cleanup completed for port {args.port}")
                # Wait longer for port to be released (increased timeout)
                if not wait_for_port_available(args.port, timeout=15):
                    print(f"Error: Port {args.port} still in use after killing process", file=sys.stderr)
                    
                    # Final diagnostic - show what's still using the port
                    try:
                        result = subprocess.run(['lsof', '-i', f':{args.port}'], capture_output=True, text=True)
                        if result.stdout:
                            print("Processes still using the port:", file=sys.stderr)
                            print(result.stdout, file=sys.stderr)
                    except:
                        pass
                    
                    print("Consider using a different port with --port or manually stopping the conflicting process", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"Error: Could not kill process on port {args.port}", file=sys.stderr)
                print("Consider using a different port with --port or manually stopping the conflicting process", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Use --force-port to kill the existing process, or choose a different port with --port", file=sys.stderr)
            sys.exit(1)

    # Launch Optuna Dashboard
    print(f"Starting optuna-dashboard on port {args.port}...")
    dashboard_cmd = ["optuna-dashboard", db_url, "--port", str(args.port), "--host", "0.0.0.0"]
    dashboard_process = subprocess.Popen(dashboard_cmd, preexec_fn=os.setsid)
    CHILD_PROCESSES.append(dashboard_process)
    print("Loading all studies from the database")

    # Wait for dashboard to initialize with retries
    print("Waiting for dashboard to initialize...")
    max_retries = 10
    for _ in range(max_retries):
        time.sleep(1)
        if dashboard_process.poll() is not None:
            print(f"Error: Optuna dashboard failed to start", file=sys.stderr)
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
                    # Pass all study names as arguments after a single --study flag
                    monitor_args.extend(["--study"] + args.study)
                if args.dry_run:
                    monitor_args.append("--dry-run")
                if not args.all_trials:
                    monitor_args.append("--only-active-trials") # Monitor only active trials by default
                if args.verbose:
                    monitor_args.append("--verbose")
                
                # Always enable some debug logging for troubleshooting
                print(f"Starting monitor with args: {' '.join(monitor_args)}")

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