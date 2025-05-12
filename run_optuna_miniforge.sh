#!/bin/zsh

# Default conda environment name
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env

echo "Starting Optuna Dashboard with Human-in-the-Loop monitoring..."

# Activate miniforge environment
echo "Activating $CONDA_ENV in Miniforge3..."
export PATH="$HOME/miniforge3/bin:$PATH"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate $CONDA_ENV

echo "Environment activated, starting services..."

# Run the main script with all parameters and pass the conda environment name
/home/$(whoami)/optuna-dashboard/run_optuna_with_monitor.sh --conda-env "$CONDA_ENV" "$@"

echo "Services have stopped."