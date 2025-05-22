#!/usr/bin/env python3

import argparse
import subprocess
import sys
import os
import time
import atexit
import signal

# List to keep track of child processes
CHILD_PROCESSES = []

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

    # Monitor configuration
    monitor_group = parser.add_argument_group('Monitor configuration')
    monitor_group.add_argument("--port", type=int, default=8080, help="Specify port for optuna-dashboard (default: 8080)")
    monitor_group.add_argument("--study", nargs='*', help="Specify one or more study names to monitor (default: monitor all studies if none specified)")
    monitor_group.add_argument("--interval", type=int, default=10, help="Monitor check interval in seconds (default: 10)")
    monitor_group.add_argument("--prune-pattern", default="PRUNE", help="Regex pattern to detect PRUNE commands (default: 'PRUNE')")
    monitor_group.add_argument("--fail-pattern", default="FAIL", help="Regex pattern to detect FAIL commands (default: 'FAIL')")
    monitor_group.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes applied)")
    monitor_group.add_argument("--all-trials", action="store_true", help="Monitor all trials, not just active ones")
    monitor_group.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # Browser launch options
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument("--thorium-app", action="store_true", help="Launch Thorium browser (uses hardcoded Thorium app arguments).")
    browser_group.add_argument("--browser-path", help="Launch specified browser executable with the dashboard URL.")

    args = parser.parse_args()

    # Validate mutual exclusivity (argparse handles this, but good for clarity)
    if args.thorium_app and args.browser_path:
        parser.error("--thorium-app and --browser-path are mutually exclusive. Please choose only one.")

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

    # Launch Optuna Dashboard
    print(f"Starting optuna-dashboard on port {args.port}...")
    # Call optuna-dashboard directly as a command
    dashboard_cmd = ["optuna-dashboard", db_url, "--port", str(args.port)]
    dashboard_process = subprocess.Popen(dashboard_cmd, preexec_fn=os.setsid) # Use os.setsid to create a new process group
    CHILD_PROCESSES.append(dashboard_process)
    print("Loading all studies from the database")

    print("Waiting for dashboard to initialize (5 seconds)...")
    time.sleep(5)

    # Launch Human Trial Monitor
    print("Starting Human-in-the-loop Trial Monitor...")
    monitor_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "human_trial_monitor.py")
    
    monitor_cmd = [sys.executable, monitor_script_path, "--db-url", db_url]
    if args.study:
        monitor_cmd.extend(["--study"] + args.study)
    monitor_cmd.extend([
        "--interval", str(args.interval),
        "--prune-pattern", args.prune_pattern,
        "--fail-pattern", args.fail_pattern
    ])
    if args.dry_run:
        monitor_cmd.append("--dry-run")
    if args.all_trials:
        monitor_cmd.append("--all-trials")
    if args.verbose:
        monitor_cmd.append("--verbose")

    monitor_process = subprocess.Popen(monitor_cmd, preexec_fn=os.setsid)
    CHILD_PROCESSES.append(monitor_process)

    print("Services are running:")
    print(f"- Dashboard: http://localhost:{args.port}")
    print("- Human-in-the-loop Monitor: Active and connected to the database")
    print("The services will automatically stop when this terminal is closed.")
    print("To use: Add a note with 'PRUNE' or 'FAIL' to any trial in the dashboard to change its state.")
    if args.dry_run:
        print("NOTE: Running in DRY-RUN mode - no actual trial state changes will be made.")

    # Launch browser
    dashboard_url = f"http://localhost:{args.port}"
    if args.thorium_app:
        print("Launching Thorium browser app...")
        if sys.platform == "darwin": # macOS
            browser_cmd = ["open", "-a", "Thorium", dashboard_url]
        elif sys.platform.startswith("linux"): # Linux (including WSL)
            # This path is specific to Windows Thorium launched from WSL.
            # For native Linux Thorium, it might be just 'thorium-browser' if in PATH,
            # or a specific path like '/opt/thorium/thorium-browser'.
            # Keeping the Windows path for WSL as per previous context.
            browser_cmd = ["/mnt/c/Users/Juan Boullosa/AppData/Local/Thorium/Application/chrome_proxy.exe",
                           "--profile-directory=Default", "--app-id=njlcciipedhmlpadngkndhojnjhpmdio",
                           f"--app={dashboard_url}"]
        else:
            print(f"Warning: Thorium app launch not configured for this OS ({sys.platform}).", file=sys.stderr)
            browser_cmd = []
        
        if browser_cmd:
            try:
                browser_process = subprocess.Popen(browser_cmd, preexec_fn=os.setsid)
                CHILD_PROCESSES.append(browser_process)
            except FileNotFoundError:
                print(f"Error: Browser executable not found for Thorium app. Command: {' '.join(browser_cmd)}", file=sys.stderr)
            except Exception as e:
                print(f"Error launching Thorium app: {e}", file=sys.stderr)

    elif args.browser_path:
        print(f"Launching custom browser: {args.browser_path}")
        try:
            browser_process = subprocess.Popen([args.browser_path, dashboard_url], preexec_fn=os.setsid)
            CHILD_PROCESSES.append(browser_process)
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
            if monitor_process.poll() is not None:
                print("Human Trial Monitor process terminated unexpectedly.", file=sys.stderr)
                break
    except KeyboardInterrupt:
        print("Ctrl+C received. Stopping services...")
    finally:
        cleanup_processes()

if __name__ == "__main__":
    main()