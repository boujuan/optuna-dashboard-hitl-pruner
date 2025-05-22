# Optuna Dashboard Launcher with Human-in-the-Loop Monitoring

This project provides a robust and generalized launcher for the Optuna Dashboard, enhanced with a human-in-the-loop monitoring system. It allows users to track Optuna studies, and manually intervene to prune or fail trials directly from the dashboard's notes section.

## Features

*   **Human-in-the-Loop Pruning/Failing**: Easily mark trials as "pruned" or "failed" by adding specific keywords (`PRUNE` or `FAIL`) to their notes in the Optuna Dashboard. The monitor automatically detects these changes and updates the trial state. This can be done retroactively.
*   **Cross-Platform Compatibility**: Designed to work seamlessly across Windows (via WSL), Linux, and macOS environments.
*   **Multiple Database Backends**: Supports PostgreSQL, MySQL, and SQLite as Optuna storage backends.
*   **Flexible Certificate Handling**: Provides options to explicitly use, disable, or automatically detect SSL certificates for database connections.
*   **Configurable Browser Launch**: Offers options to automatically launch a browser to the Optuna Dashboard.

## Prerequisites

*   **Bash**: The shell scripts are written in `bash`/`zsh`. Ensure it's installed on your system
*   **Miniforge3 (or Anaconda/Conda)**: Used for managing Python environments and dependencies.
*   **Python 3**: Required for the human trial monitor script.
*   **Database**: Access to a PostgreSQL, MySQL, or SQLite database for Optuna storage.
*   **Optuna & Optuna-Dashboard**: These Python packages will be automatically installed by the launcher if not already present. Database-specific drivers (e.g., `psycopg2-binary` for PostgreSQL, `mysqlclient` for MySQL) will also be installed as needed.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/boujuan/optuna-dashboard-hitl-pruner.git
    cd optuna-dashboard-hitl-pruner
    ```
2.  **Ensure Miniforge3 is set up**: The `run_optuna_miniforge.sh` script assumes Miniforge3 is installed in your home directory (`$HOME/miniforge3`) by default. You can specify a different path using the `--conda-path` argument.
3.  **Activate your Conda environment**: The `run_optuna_miniforge.sh` script will activate the `wf_env` environment by default, or the one specified by the `CONDA_ENV` environment variable.

## Usage

The main entry point is `run_optuna_miniforge.sh`, which handles environment activation and then calls `run_optuna_with_monitor.sh` with your specified arguments.

### `run_optuna_miniforge.sh` Arguments

*   `--conda-path PATH`: Specify the base installation path of your Conda environment (e.g., `/opt/conda`). Defaults to `$HOME/miniforge3`.

### `run_optuna_with_monitor.sh` Arguments

Here's a list of available options for `run_optuna_with_monitor.sh`:

```
Usage: ./run_optuna_with_monitor.sh [options]
Options:
  --port PORT           Specify port for optuna-dashboard (default: 8080)
  --study NAME [NAME...] Specify one or more study names to load
  --db-host HOST        Database hostname
  --db-port PORT        Database port
  --db-name NAME        Database name
  --db-user USER        Database username
  --db-password PASS    Database password
  --conda-env NAME      Conda environment name (default: wf_env)
  --db-type TYPE        Database type (postgresql, mysql, sqlite) (default: postgresql)
  --interval SECONDS    Monitor check interval in seconds (default: 10)
  --cert-path PATH      Path to CA certificate file (default: ${SCRIPT_DIR}/cert/ca.pem)
  --use-cert            Explicitly use the certificate specified by --cert-path (overrides --no-cert)
  --no-cert             Explicitly disable certificate usage (overrides --cert-path and default detection)
  --thorium-app         Launch Thorium browser (uses hardcoded Thorium app arguments).
  --browser-path PATH   Launch specified browser executable with the dashboard URL.
  --prune-pattern PAT   Custom regex pattern for PRUNE commands (default: 'PRUNE')
  --fail-pattern PAT    Custom regex pattern for FAIL commands (default: 'FAIL')
  --dry-run             Test mode - don't actually change trial states
  --all-trials          Monitor all trials, not just active ones
  --verbose             Show more detailed output
  --help                Show this help message
```

### Launching Optuna Dashboard

#### For Windows (using WSL)

Create a `.bat` file (e.g., `launch_optuna.bat`) in your desired location (e.g., on your Desktop) with the following content. Remember to replace placeholder values like database credentials and study names with your actual information.

**Example using `--thorium-app`:**

```batch
@echo off
"C:\Users\User\AppData\Local\Microsoft\WindowsApps\wt.exe" -p "Debian" wsl.exe -d Debian -e bash -c "/home/user/optuna-dashboard/run_optuna_miniforge.sh --db-type postgresql --db-host remote_postgresql_database.com --db-port 12345 --db-user dbuser --db-password 'dbpassword' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --cert-path /home/user/optuna-dashboard/cert/ca.pem --use-cert --thorium-app"
```

**Example using `--browser-path` (for a custom browser like Chrome):**

```batch
@echo off
"C:\Users\User\AppData\Local\Microsoft\WindowsApps\wt.exe" -p "Debian" wsl.exe -d Debian -e bash -c "/home/user/optuna-dashboard/run_optuna_miniforge.sh --db-type postgresql --db-host remote_postgresql_database.com --db-port 12345 --db-user dbuser --db-password 'password' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --cert-path /home/user/optuna-dashboard/cert/ca.pem --use-cert --browser-path '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'"
```

#### For macOS and Linux

Open your terminal and navigate to the `optuna-dashboard` directory. Then, execute the `run_optuna_miniforge.sh` script directly. Remember to replace placeholder values with your actual information.

**Example using `--browser-path` (macOS/Linux):**

```bash
/Users/youruser/miniforge3/bin/bash /path/to/optuna-dashboard/run_optuna_miniforge.sh --db-type postgresql --db-host your_db_host --db-port 5432 --db-user your_user --db-password 'your_password' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --browser-path '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```
*(Replace `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` with the actual path to your browser executable on Linux, e.g., `/usr/bin/google-chrome` or `firefox`)*

## Human-in-the-Loop Monitoring

Once the Optuna Dashboard and the Human Trial Monitor are running:

1.  Open the Optuna Dashboard in your browser (usually `http://localhost:8080`).
2.  Navigate to the study and trial you wish to modify.
3.  In the "Notes" section of a trial, add a new note containing either:
    *   `PRUNE`: To mark the trial as `PRUNED`.
    *   `FAIL`: To mark the trial as `FAIL`.
4.  The monitor script will detect this note change within the specified `--interval` and update the trial's state in the Optuna storage.

**Note on Dry-Run Mode**: If you start the monitor with `--dry-run`, it will log what changes it *would* make without actually modifying the trial states. This is useful for testing.
