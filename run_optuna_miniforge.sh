#!/bin/zsh

# Default conda environment name
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env

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
echo "Activating $CONDA_ENV in Miniforge3..."
export PATH="$HOME/miniforge3/bin:$PATH"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate $CONDA_ENV

echo "Environment activated, starting services..."

# Run the main script with all parameters and pass the conda environment name
/home/$(whoami)/optuna-dashboard/run_optuna_with_monitor.sh --conda-env "$CONDA_ENV" "$@"
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