#!/bin/zsh

# Default conda environment name
CONDA_ENV="${CONDA_ENV:-wf_env}"  # Use environment variable or default to wf_env

# Parse command line arguments to handle --conda-env explicitly
# We need to do this early before passing to the main script
i=1
while [ $i -le $# ]; do
    arg="${!i}"
    next_i=$((i + 1))
    
    if [ "$arg" = "--conda-env" ] && [ $next_i -le $# ]; then
        CONDA_ENV="${!next_i}"
        set -- "${@:1:$((i-1))}" "${@:$((i+2))}"
        continue
    fi
    
    i=$((i + 1))
done

# Pass all other arguments through to the main script
ARGS="$@"

echo "Starting Optuna Dashboard with Human-in-the-Loop monitoring..."

# Activate miniforge environment only here - we won't do it again in the main script
echo "Activating $CONDA_ENV in Miniforge3..."
export PATH="$HOME/miniforge3/bin:$PATH"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate $CONDA_ENV

echo "Environment activated, starting services..."

# Set the environment variable so the main script knows not to activate again
export CONDA_ENV_ACTIVATED=true

# Run the main script with all parameters and pass the conda environment name
/home/$(whoami)/optuna-dashboard/run_optuna_with_monitor.sh --conda-env "$CONDA_ENV" $ARGS

echo "Services have stopped."