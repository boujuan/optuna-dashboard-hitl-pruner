#!/usr/bin/env bash

# Default conda environment name
CONDA_ENV="${CONDA_ENV:-optuna-dashboard}"  # Use environment variable or default to optuna-dashboard

CONDA_BASE_PATH="$HOME/miniforge3" # Default Conda installation path
echo "Starting Optuna Dashboard with Human-in-the-Loop monitoring..."

# Function to handle errors
handle_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "==============================================="
        echo "An error occurred with exit code: $exit_code"
        echo "Press Enter to close this terminal, or Ctrl+C to abort."
        echo "==============================================="
        read
    fi
}

# Set up trap to catch errors
trap 'handle_error' EXIT

# Activate miniforge environment

LAUNCHER_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --conda-path)
            CONDA_BASE_PATH="$2"
            shift 2
            ;;
        --conda-env)
            CONDA_ENV="$2"
            shift 2
            ;;
        *)
            LAUNCHER_ARGS+=("$1")
            shift
            ;;
    esac
done

echo "Activating $CONDA_ENV from $CONDA_BASE_PATH..."

if [ ! -d "$CONDA_BASE_PATH" ]; then
    echo "Error: Conda installation not found at $CONDA_BASE_PATH. Please specify the correct path with --conda-path."
    exit 1
fi

# Use the Python from the target environment directly
PYTHON_BIN="$CONDA_BASE_PATH/envs/$CONDA_ENV/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python not found at $PYTHON_BIN"
    echo "Make sure the conda environment '$CONDA_ENV' exists."
    exit 1
fi

echo "Environment activated, starting services..."
echo "Using Python: $PYTHON_BIN"

# Run the main script with all parameters and automatically open browser
"$PYTHON_BIN" -m optuna_monitor.launcher "${LAUNCHER_ARGS[@]}" --browser-path "/home/boujuan/.local/bin/edge-optuna-launcher"
exit_code=$?

# If there was an error, wait for user input before exiting
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "==============================================="
    echo "Process exited with code: $exit_code"
    echo "Press Enter to close this terminal."
    echo "==============================================="
    read
fi

echo "Services have stopped."