#!/usr/bin/env bash

# Default values
DASHBOARD_PORT=8080
STUDY_NAMES=() # Array to store multiple study names
VERBOSE=""
DB_TYPE="postgresql" # Default to postgresql
DB_HOST="localhost"
DB_PORT="" # No default port, will be set based on DB_TYPE
DB_NAME="optuna"
DB_USER="optuna"
DB_PASSWORD="password"
INTERVAL=10
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env
USERNAME=$(whoami)
HOME_DIR=$HOME
SCRIPT_DIR="$(dirname "$0")"
CERT_PATH="${SCRIPT_DIR}/cert/ca.pem" # Default certificate path
USE_CERT="false" # Flag to explicitly use certificate
NO_CERT="false" # Flag to explicitly disable certificate usage
BROWSER_LAUNCH_TYPE="" # "thorium_app" or "browser_path"
THORIUM_APP_FLAG="false" # Internal flag for --thorium-app
BROWSER_PATH_FLAG="false" # Internal flag for --browser-path
CUSTOM_BROWSER_PATH="" # Path for --browser-path
PRUNE_PATTERN="PRUNE"
FAIL_PATTERN="FAIL"
DRY_RUN=""
ALL_TRIALS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            DASHBOARD_PORT="$2"
            shift 2
            ;;
        --study)
            STUDY_NAMES+=("$2")
            shift 2
            ;;
        --db-host)
            DB_HOST="$2"
            shift 2
            ;;
        --db-port)
            DB_PORT="$2"
            shift 2
            ;;
        --db-name)
            DB_NAME="$2"
            shift 2
            ;;
        --db-user)
            DB_USER="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --db-type)
            DB_TYPE="$2"
            shift 2
            ;;
        --conda-env)
            CONDA_ENV="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --cert-path)
            CERT_PATH="$2"
            shift 2
            ;;
        --use-cert)
            USE_CERT="true"
            shift
            ;;
        --no-cert)
            NO_CERT="true"
            shift
            ;;
        --thorium-app)
            THORIUM_APP_FLAG="true"
            shift
            ;;
        --browser-path)
            BROWSER_PATH_FLAG="true"
            CUSTOM_BROWSER_PATH="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --prune-pattern)
            PRUNE_PATTERN="$2"
            shift 2
            ;;
        --fail-pattern)
            FAIL_PATTERN="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --all-trials)
            ALL_TRIALS="--all-trials"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --port PORT           Specify port for optuna-dashboard (default: 8080)"
            echo "  --study NAME [NAME...] Specify one or more study names to load"
            echo "  --db-host HOST        Database hostname"
            echo "  --db-port PORT        Database port"
            echo "  --db-name NAME        Database name"
            echo "  --db-user USER        Database username"
            echo "  --db-password PASS    Database password"
            echo "  --conda-env NAME      Conda environment name (default: $CONDA_ENV)"
            echo "  --db-type TYPE        Database type (e.g., postgresql, mysql, sqlite) (default: postgresql)"
            echo "  --interval SECONDS    Monitor check interval in seconds (default: 10)"
            echo "  --cert-path PATH      Path to CA certificate file (default: ${SCRIPT_DIR}/cert/ca.pem)"
            echo "  --use-cert            Explicitly use the certificate specified by --cert-path (overrides --no-cert)"
            echo "  --no-cert             Explicitly disable certificate usage (overrides --cert-path and default detection)"
            echo "  --thorium-app         Launch Thorium browser (uses hardcoded Thorium app arguments)."
            echo "  --browser-path PATH   Launch specified browser executable with the dashboard URL."
            echo "  --prune-pattern PAT   Custom regex pattern for PRUNE commands (default: 'PRUNE')"
            echo "  --fail-pattern PAT    Custom regex pattern for FAIL commands (default: 'FAIL')"
            echo "  --dry-run             Test mode - don't actually change trial states"
            echo "  --all-trials          Monitor all trials, not just active ones"
            echo "  --verbose             Show more detailed output"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help to see available options"
            exit 1
            ;;
    esac
 done
 
 # Check for mutual exclusivity of browser launch options
 if [ "$THORIUM_APP_FLAG" = "true" ] && [ "$BROWSER_PATH_FLAG" = "true" ]; then
     echo "Error: --thorium-app and --browser-path are mutually exclusive. Please choose only one."
     exit 1
 fi
 
 # Determine if certificate should be used
if [ "$NO_CERT" = "true" ]; then
    USE_CERT="false"
    CERT_PATH="" # Clear path if no-cert is specified
elif [ "$USE_CERT" = "true" ]; then
    # If --use-cert was explicitly given, CERT_PATH should already be set or default
    if [ -z "$CERT_PATH" ]; then
        echo "Error: --use-cert specified but no --cert-path provided and default is empty."
        exit 1
    fi
    if [[ ! -f "$CERT_PATH" ]]; then
        echo "Error: Certificate file not found at $CERT_PATH"
        exit 1
    fi
else
    # If neither --use-cert nor --no-cert was specified, check for default cert
    if [ -f "${SCRIPT_DIR}/cert/ca.pem" ]; then
        CERT_PATH="${SCRIPT_DIR}/cert/ca.pem"
        USE_CERT="true"
        echo "Automatically using default CA certificate at $CERT_PATH"
    else
        CERT_PATH="" # Ensure it's empty if no cert is found/used
        USE_CERT="false"
    fi
fi

# Set default port if not provided
if [ -z "$DB_PORT" ]; then
    case "$DB_TYPE" in
        postgresql) DB_PORT="5432" ;;
        mysql) DB_PORT="3306" ;;
        *) echo "Warning: No default port for DB_TYPE: $DB_TYPE. Please specify --db-port." ;;
    esac
fi

# Construct the database URL
DB_URL=""
case "$DB_TYPE" in
    postgresql)
        DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
        if [ "$USE_CERT" = "true" ] && [ -n "$CERT_PATH" ]; then
            DB_URL="${DB_URL}?sslmode=require&sslrootcert=${CERT_PATH}"
        fi
        ;;
    mysql)
        DB_URL="mysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
        if [ "$USE_CERT" = "true" ] && [ -n "$CERT_PATH" ]; then
            # MySQL SSL parameters might vary, using a common one for CA cert
            DB_URL="${DB_URL}?ssl_ca=${CERT_PATH}"
        fi
        ;;
    sqlite)
        # For SQLite, DB_NAME is the file path
        DB_URL="sqlite:///${DB_NAME}"
        ;;
    *)
        echo "Error: Unsupported database type: $DB_TYPE"
        exit 1
        ;;
esac

# Function to check if a package is installed
package_installed() {
    pip show "$1" &> /dev/null
}

# Install required packages if not already installed
echo "Checking required packages..."
if ! package_installed "optuna"; then
    echo "Installing optuna..."
    pip install optuna
fi

if ! package_installed "optuna-dashboard"; then
    echo "Installing optuna-dashboard..."
    pip install optuna-dashboard
fi


if [ "$DB_TYPE" = "postgresql" ]; then
    if ! package_installed "psycopg2-binary"; then
        echo "Installing psycopg2-binary for PostgreSQL connection..."
        pip install psycopg2-binary
    fi
elif [ "$DB_TYPE" = "mysql" ]; then
    if ! package_installed "mysqlclient"; then
        echo "Installing mysqlclient for MySQL connection..."
        pip install mysqlclient
    fi
fi

# Start the Optuna Dashboard in the background
echo "Starting optuna-dashboard on port ${DASHBOARD_PORT}..."
echo "Loading all studies from the database"
optuna-dashboard "$DB_URL" --port "$DASHBOARD_PORT" &
DASHBOARD_PID=$!

# Wait a moment for the dashboard to initialize
echo "Waiting for dashboard to initialize (5 seconds)..."
sleep 5

# Start the Human Trial Monitor in the background
MONITOR_SCRIPT="${SCRIPT_DIR}/human_trial_monitor.py"

echo "Starting Human-in-the-loop Trial Monitor..."
if [ ${#STUDY_NAMES[@]} -gt 0 ]; then
    echo "Monitoring specific studies: ${STUDY_NAMES[@]}"
    python3 "$MONITOR_SCRIPT" --db-url "$DB_URL" --study "${STUDY_NAMES[@]}" \
        --interval "$INTERVAL" --prune-pattern "$PRUNE_PATTERN" --fail-pattern "$FAIL_PATTERN" \
        $VERBOSE $DRY_RUN $ALL_TRIALS &
else
    echo "Monitoring all studies in the database"
    python3 "$MONITOR_SCRIPT" --db-url "$DB_URL" \
        --interval "$INTERVAL" --prune-pattern "$PRUNE_PATTERN" --fail-pattern "$FAIL_PATTERN" \
        $VERBOSE $DRY_RUN $ALL_TRIALS &
fi
MONITOR_PID=$!

# Launch browser if specified
DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"
BROWSER_PID="" # Initialize BROWSER_PID here
 
if [ "$THORIUM_APP_FLAG" = "true" ]; then
    echo "Launching Thorium browser app..."
    # Determine OS for Thorium path
    if [[ "$OSTYPE" == "darwin"* ]]; then # macOS
        open -a "Thorium" "$DASHBOARD_URL" &
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # This path is specific to Windows Thorium launched from WSL.
        "/mnt/c/Users/Juan Boullosa/AppData/Local/Thorium/Application/chrome_proxy.exe" --profile-directory=Default --app-id=njlcciipedhmlpadngkndhojnjhpmdio --app="$DASHBOARD_URL" &
    else
        echo "Warning: Thorium app launch not configured for this OS ($OSTYPE)."
    fi
    BROWSER_PID=$! # Capture PID if launched
elif [ "$BROWSER_PATH_FLAG" = "true" ]; then
    if [ -n "$CUSTOM_BROWSER_PATH" ]; then
        echo "Launching custom browser: $CUSTOM_BROWSER_PATH"
        "$CUSTOM_BROWSER_PATH" "$DASHBOARD_URL" &
        BROWSER_PID=$!
    else
        echo "Error: --browser-path requires a path to the browser executable."
        exit 1 # Exit if path is missing
    fi
fi

# Set up cleanup function
cleanup() {
    echo "Stopping services..."
    kill $DASHBOARD_PID 2>/dev/null
    kill $MONITOR_PID 2>/dev/null
    if [ -n "$BROWSER_PID" ]; then
        kill $BROWSER_PID 2>/dev/null
    fi
    echo "Cleaned up and stopped services."
}

# Register the cleanup function
trap cleanup EXIT INT TERM

echo ""
echo "Services are running:"
echo "- Dashboard: http://localhost:${DASHBOARD_PORT}"
echo "- Human-in-the-loop Monitor: Active and connected to the database"
echo ""
echo "The services will automatically stop when this terminal is closed."
echo "To use: Add a note with '$PRUNE_PATTERN' or '$FAIL_PATTERN' to any trial in the dashboard to change its state."
if [ -n "$DRY_RUN" ]; then
    echo "NOTE: Running in DRY-RUN mode - no actual trial state changes will be made."
fi
echo ""

# Wait for the processes to keep the script running
if [ -n "$BROWSER_PID" ]; then
    wait $DASHBOARD_PID $MONITOR_PID $BROWSER_PID
else
    wait $DASHBOARD_PID $MONITOR_PID
fi