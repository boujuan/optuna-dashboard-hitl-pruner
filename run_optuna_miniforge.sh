#!/usr/bin/env bash

# Default conda environment name
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env

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

# Parse command line arguments for this script
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
            # Pass other arguments to the next script
            break
            ;;
    esac
done

echo "Activating $CONDA_ENV from $CONDA_BASE_PATH..."

if [ ! -d "$CONDA_BASE_PATH" ]; then
    echo "Error: Conda installation not found at $CONDA_BASE_PATH. Please specify the correct path with --conda-path."
    exit 1
fi

export PATH="$CONDA_BASE_PATH/bin:$PATH"
source "$CONDA_BASE_PATH/etc/profile.d/conda.sh"
conda activate $CONDA_ENV

echo "Environment activated, starting services..."

# Run the main script with all parameters and pass the conda environment name
# The --conda-env argument is handled by this script and not passed to the Python launcher.
FILTERED_ARGS=()
skip_next=false
for arg in "$@"; do
    if [[ "$skip_next" == true ]]; then
        skip_next=false
        continue
    fi
    
    if [[ "$arg" == "--thorium-app" ]]; then
        continue
    elif [[ "$arg" == "--conda-env" ]]; then
        skip_next=true
        continue
    elif [[ "$arg" == "--conda-path" ]]; then
        skip_next=true
        continue
    else
        FILTERED_ARGS+=("$arg")
    fi
done
python3 -m optuna_monitor.launcher "${FILTERED_ARGS[@]}"
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