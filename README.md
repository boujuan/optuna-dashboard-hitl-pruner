# Optuna Dashboard Launcher with Human-in-the-Loop Monitoring

This project provides a robust and generalized launcher for the Optuna Dashboard, enhanced with a human-in-the-loop monitoring system. It allows users to track Optuna studies, and manually intervene to prune or fail trials directly from the dashboard's notes section.

## Features

*   **Human-in-the-Loop Pruning/Failing**: Easily mark trials as "pruned" or "failed" by adding specific keywords (`PRUNE` or `FAIL`) to their notes in the Optuna Dashboard. The monitor automatically detects these changes and updates the trial state. This can be done retroactively.
*   **Cross-Platform Compatibility**: Designed to work seamlessly across Windows (via WSL), Linux, and macOS environments.
*   **Multiple Database Backends**: Supports PostgreSQL, MySQL, and SQLite as Optuna storage backends.
*   **Flexible Certificate Handling**: Provides options to explicitly use, disable, or automatically detect SSL certificates for database connections.
*   **Configurable Browser Launch**: Offers options to automatically launch a browser to the Optuna Dashboard.

## Prerequisites

*   **Bash**: The shell scripts are written in `bash`/`zsh`. Ensure it's installed on your system.
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

## Installation as a Python Package

You can install this project as a Python package using `pip`. This will make the `optuna-monitor` command available in your Python environment.

```bash
pip install .
```

## Usage

The main entry point is `run_optuna_miniforge.sh`, which handles environment activation and then calls the `optuna-monitor` command with your specified arguments.

### `run_optuna_miniforge.sh` Arguments

*   `--conda-path PATH`: Specify the base installation path of your Conda environment (e.g., `/opt/conda`). Defaults to `$HOME/miniforge3`.

### `optuna-monitor` Arguments

Here's a list of available options for `optuna-monitor`:

```
Usage: optuna-monitor [-h] [--db-url DB_URL] [--db-host DB_HOST] [--db-port DB_PORT] [--db-name DB_NAME] [--db-user DB_USER] [--db-password DB_PASSWORD] [--db-type {postgresql,mysql,sqlite}] [--cert-path CERT_PATH] [--use-cert] [--no-cert] [--port PORT] [--study [STUDY ...]] [--interval INTERVAL] [--prune-pattern PRUNE_PATTERN] [--fail-pattern FAIL_PATTERN] [--dry-run] [--all-trials] [--verbose] [--thorium-app | --browser-path BROWSER_PATH]

Launch Optuna Dashboard and Human-in-the-Loop Monitor.

options:
  -h, --help            show this help message and exit

Database connection:
  --db-url DB_URL       Database URL for Optuna storage
  --db-host DB_HOST     Database hostname (default: localhost)
  --db-port DB_PORT     Database port (default: 5432 for postgresql, 3306 for mysql)
  --db-name DB_NAME     Database name (default: optuna)
  --db-user DB_USER     Database username (default: optuna)
  --db-password DB_PASSWORD
                        Database password (default: password)
  --db-type {postgresql,mysql,sqlite}
                        Database type (postgresql, mysql, sqlite) (default: postgresql)
  --cert-path CERT_PATH
                        Path to CA certificate file
  --use-cert            Explicitly use the certificate specified by --cert-path (overrides --no-cert)
  --no-cert             Explicitly disable certificate usage (overrides --cert-path and default detection)

Monitor configuration:
  --port PORT           Specify port for optuna-dashboard (default: 8080)
  --study [STUDY ...]   Specify one or more study names to monitor (default: monitor all studies if none specified)
  --interval INTERVAL   Monitor check interval in seconds (default: 10)
  --prune-pattern PRUNE_PATTERN
                        Regex pattern to detect PRUNE commands (default: 'PRUNE')
  --fail-pattern FAIL_PATTERN
                        Regex pattern to detect FAIL commands (default: 'FAIL')
  --dry-run             Run in dry-run mode (no changes applied)
  --all-trials          Monitor all trials, not just active ones
  --verbose             Enable verbose logging (DEBUG level)

Browser launch options:
  --browser-path BROWSER_PATH
                        Launch specified browser executable with the dashboard URL.
```

### Launching Optuna Dashboard

#### For Windows (using WSL)

Create a `.bat` file (e.g., `launch_optuna.bat`) in your desired location (e.g., on your Desktop) with the following content. Remember to replace placeholder values like database credentials and study names with your actual information.


**Example using `--browser-path` (for a custom browser like Chrome):**

```batch
@echo off
"C:\Users\User\AppData\Local\Microsoft\WindowsApps\wt.exe" -p "Debian" wsl.exe -d Debian -e bash -c "/home/user/optuna-dashboard/run_optuna_miniforge.sh --db-type postgresql --db-host remote_postgresql_database.com --db-port 12345 --db-user dbuser --db-password 'password' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --cert-path /home/user/optuna-dashboard-hitl-pruner/cert/ca.pem --use-cert --browser-path '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'"
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
