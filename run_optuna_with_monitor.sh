#!/bin/zsh

# Default values
DASHBOARD_PORT=8080
STUDY_NAME=""
VERBOSE=""
DB_HOST="pg-windforecasting-aiven-wind-forecasting.e.aivencloud.com"
DB_PORT="12472"
DB_NAME="defaultdb"
DB_USER="avnadmin"
DB_PASSWORD="PASSWORD"
INTERVAL=5
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env
USERNAME=$(whoami)
HOME_DIR=$HOME
SCRIPT_DIR="$(dirname "$0")"
CERT_PATH="${SCRIPT_DIR}/cert/ca.pem"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            DASHBOARD_PORT="$2"
            shift 2
            ;;
        --study)
            STUDY_NAME="$2"
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
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --port PORT           Specify port for optuna-dashboard (default: 8080)"
            echo "  --study NAME          Specify a specific study name to load"
            echo "  --db-host HOST        Database hostname"
            echo "  --db-port PORT        Database port"
            echo "  --db-name NAME        Database name"
            echo "  --db-user USER        Database username"
            echo "  --db-password PASS    Database password"
            echo "  --conda-env NAME      Conda environment name (default: $CONDA_ENV)"
            echo "  --interval SECONDS    Monitor check interval in seconds (default: 5)"
            echo "  --cert-path PATH      Path to CA certificate file"
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

# Check for cert directory and file
CERT_DIR="$(dirname "$CERT_PATH")"
if [[ ! -d "$CERT_DIR" ]]; then
    echo "Creating certificate directory: $CERT_DIR"
    mkdir -p "$CERT_DIR"
fi

if [[ ! -f "$CERT_PATH" ]]; then
    echo "CA certificate not found at $CERT_PATH, creating it..."
    cat > "$CERT_PATH" << 'EOT'
-----BEGIN CERTIFICATE-----
CERTIFICATE CONTENT HERE
-----END CERTIFICATE-----
EOT
    echo "CA certificate saved to $CERT_PATH"
else
    echo "Using existing CA certificate at $CERT_PATH"
fi

# Construct the database URL with SSL certificate
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require&sslrootcert=${CERT_PATH}"

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

if ! package_installed "psycopg2-binary"; then
    echo "Installing psycopg2-binary for PostgreSQL connection..."
    pip install psycopg2-binary
fi

# Start the Optuna Dashboard in the background
echo "Starting optuna-dashboard on port ${DASHBOARD_PORT}..."
if [ -n "$STUDY_NAME" ]; then
    echo "Loading study: $STUDY_NAME"
    optuna-dashboard "$DB_URL" --port "$DASHBOARD_PORT" --study "$STUDY_NAME" &
else
    echo "Loading all studies from the database"
    optuna-dashboard "$DB_URL" --port "$DASHBOARD_PORT" &
fi
DASHBOARD_PID=$!

# Wait a moment for the dashboard to initialize
echo "Waiting for dashboard to initialize (2 seconds)..."
sleep 2

# Start the Human Trial Monitor in the background
MONITOR_SCRIPT="${SCRIPT_DIR}/human_trial_monitor.py"

echo "Starting Human-in-the-loop Trial Monitor..."
if [ -n "$STUDY_NAME" ]; then
    python3 "$MONITOR_SCRIPT" --db-url "$DB_URL" --study "$STUDY_NAME" --interval "$INTERVAL" $VERBOSE &
else
    python3 "$MONITOR_SCRIPT" --db-url "$DB_URL" --interval "$INTERVAL" $VERBOSE &
fi
MONITOR_PID=$!

# Launch Thorium browser
echo "Launching Thorium browser..."
/mnt/c/Users/$USERNAME/AppData/Local/Thorium/Application/chrome_proxy.exe --profile-directory=Default --app-id=njlcciipedhmlpadngkndhojnjhpmdio &
BROWSER_PID=$!

# Set up cleanup function
cleanup() {
    echo "Stopping services..."
    kill $DASHBOARD_PID 2>/dev/null
    kill $MONITOR_PID 2>/dev/null
    echo "Cleaned up and stopped services."
}

# Register the cleanup function
trap cleanup EXIT INT TERM

echo "Services are running:"
echo "- Dashboard: http://localhost:${DASHBOARD_PORT}"
echo "- Human-in-the-loop Monitor: Active and connected to the database"
echo "The services will automatically stop when this terminal is closed."
echo "To use: Add a note with 'PRUNE' or 'FAIL' to any trial in the dashboard to change its state."

# Wait for the processes to keep the script running
wait $DASHBOARD_PID $MONITOR_PID