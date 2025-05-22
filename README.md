# Optuna Dashboard Launcher with Human-in-the-Loop Monitoring

This project provides a robust and generalized launcher for the Optuna Dashboard, enhanced with a human-in-the-loop monitoring system. It allows users to track Optuna studies, and manually intervene to prune or fail trials directly from the dashboard's notes section.

## Features

*   **Human-in-the-Loop Pruning/Failing**: Easily mark trials as "pruned" or "failed" by adding specific keywords (`PRUNE` or `FAIL`) to their notes in the Optuna Dashboard. The monitor automatically detects these changes and updates the trial state. This can be done retroactively.
*   **Cross-Platform Compatibility**: Designed to work seamlessly across Windows (via WSL), Linux, and macOS environments.
*   **Multiple Database Backends**: Supports PostgreSQL, MySQL, and SQLite as Optuna storage backends.
*   **SSH Tunnel Support**: Securely connect to remote databases through SSH jump servers or bastion hosts.
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
3.  **Activate your Conda environment**: The `run_optuna_miniforge.sh` script will activate the `wf_env` environment by default, or the one specified by the `CONDA_ENV` environment variable, or the one specified using the `--conda-env` argument.

## Installation as a Python Package

You can install this project as a Python package using `pip`. This will make the `optuna-monitor` command available in your Python environment.

```bash
pip install .
```

## Usage

The main entry point is `run_optuna_miniforge.sh`, which handles environment activation and then calls the `optuna-monitor` command with your specified arguments.

### `run_optuna_miniforge.sh` Arguments

*   `--conda-path PATH`: Specify the base installation path of your Conda environment (e.g., `/opt/conda`). Defaults to `$HOME/miniforge3`.
*   `--conda-env ENV_NAME`: Specify the conda environment name to activate (e.g., `my_env`). Defaults to `wf_env` or the value of the `CONDA_ENV` environment variable.

### `optuna-monitor` Arguments

Here's a list of available options for `optuna-monitor`:

```
Usage: optuna-monitor [-h] [--db-url DB_URL] [--db-host DB_HOST] [--db-port DB_PORT] [--db-name DB_NAME] [--db-user DB_USER] [--db-password DB_PASSWORD] [--db-type {postgresql,mysql,sqlite}] [--cert-path CERT_PATH] [--use-cert] [--no-cert] [--ssh-host SSH_HOST] [--ssh-user SSH_USER] [--ssh-port SSH_PORT] [--ssh-key SSH_KEY] [--ssh-password SSH_PASSWORD] [--port PORT] [--study [STUDY ...]] [--interval INTERVAL] [--prune-pattern PRUNE_PATTERN] [--fail-pattern FAIL_PATTERN] [--dry-run] [--all-trials] [--verbose] [--browser-path BROWSER_PATH]

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

SSH tunnel options:
  --ssh-host SSH_HOST   SSH host for tunneling (e.g., jump.example.com)
  --ssh-user SSH_USER   SSH username for tunneling
  --ssh-port SSH_PORT   SSH port for tunneling (default: 22)
  --ssh-key SSH_KEY     Path to SSH private key file
  --ssh-password SSH_PASSWORD
                        SSH password (not recommended, use SSH keys instead)

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
"C:\Users\User\AppData\Local\Microsoft\WindowsApps\wt.exe" -p "Debian" wsl.exe -d Debian -e bash -c "/home/user/optuna-dashboard-hitl-pruner/run_optuna_miniforge.sh --conda-env my_env --db-type postgresql --db-host remote_postgresql_database.com --db-port 12345 --db-user dbuser --db-password 'password' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --cert-path /home/user/optuna-dashboard-hitl-pruner/cert/ca.pem --use-cert --browser-path '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'"
```

#### For macOS and Linux

Open your terminal and navigate to the `optuna-dashboard` directory. Then, execute the `run_optuna_miniforge.sh` script directly. Remember to replace placeholder values with your actual information.

**Example using `--browser-path` (macOS/Linux):**

```bash
/Users/youruser/miniforge3/bin/bash /path/to/optuna-dashboard-hitl-pruner/run_optuna_miniforge.sh --conda-env my_env --db-type postgresql --db-host your_db_host --db-port 5432 --db-user your_user --db-password 'your_password' --db-name 'db_name' --study 'study_name_1' 'study_name_2' --browser-path '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```
*(Replace `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` with the actual path to your browser executable on Linux, e.g., `/usr/bin/google-chrome` or `firefox`)*

## SSH Tunnel Support

For secure database connections through jump servers or bastion hosts, you can use SSH tunneling.

### Basic SSH Tunnel Example

```bash
./run_optuna_miniforge.sh \
    --ssh-host "jump.example.com" \
    --ssh-user "username" \
    --ssh-key "~/.ssh/id_rsa" \
    --db-host "internal-db.company.com" \
    --db-port "5432" \
    --db-type "postgresql" \
    --db-name "optuna" \
    --db-user "optuna_user" \
    --db-password "password"
```

## How SSH Tunneling Works

1. **SSH Tunnel Creation**: The system creates an SSH tunnel from your local machine to the jump server
2. **Port Forwarding**: A local port is forwarded through the tunnel to the remote database
3. **Database Connection**: The Optuna Dashboard and monitor connect to `localhost:local_port` instead of the actual database host
4. **Automatic Cleanup**: The SSH tunnel is automatically terminated when the application stops

## SSH Tunnel Arguments

| Argument | Required | Description | Example |
|----------|----------|-------------|---------|
| `--ssh-host` | Yes* | SSH jump server hostname | `jump.example.com` |
| `--ssh-user` | Yes* | SSH username | `ahenry` |
| `--ssh-port` | No | SSH port (default: 22) | `2222` |
| `--ssh-key` | No** | Path to SSH private key | `~/.ssh/id_rsa` |
| `--ssh-password` | No** | SSH password (not recommended) | `mypassword` |

*Required when using SSH tunneling
**At least one authentication method should be provided

## Authentication Methods

### 1. SSH Key (Recommended)
```bash
--ssh-key "~/.ssh/id_rsa"
```

### 2. SSH Agent
If no key or password is specified, the system will attempt to use your SSH agent or default SSH configuration.

### 3. Password (Not Recommended)
```bash
--ssh-password "your_password"
```

## Troubleshooting

### Common Issues

1. **SSH Connection Fails**
   - Verify SSH credentials and network connectivity
   - Check if the SSH host is reachable: `ssh user@host`
   - Ensure SSH key permissions are correct: `chmod 600 ~/.ssh/id_rsa`

2. **Database Connection Through Tunnel Fails**
   - Verify the database host and port are correct
   - Check if the database is accessible from the SSH server
   - Test manually: `ssh -L 5432:db-host:5432 user@ssh-host`

3. **Port Already in Use**
   - The system automatically finds free ports, but if issues persist, try restarting

### Debug Mode

Add `--verbose` to see detailed logging:
```bash
./run_optuna_miniforge.sh --verbose --ssh-host ... # other options
```

## Security Considerations

1. **Use SSH Keys**: Always prefer SSH keys over passwords
2. **Key Permissions**: Ensure SSH private keys have proper permissions (600)
3. **Jump Server Access**: Only use trusted jump servers
4. **Network Security**: The tunnel encrypts data between your machine and the jump server
5. **Credential Management**: Consider using SSH agent or credential managers

## Integration with Existing Workflows

The SSH tunnel feature is fully compatible with all existing database and certificate options:

- Works with PostgreSQL, MySQL, and SQLite (though SQLite doesn't need tunneling)
- Supports SSL certificates through `--cert-path`, `--use-cert`, `--no-cert`
- Compatible with all monitoring and dashboard features
- Works with custom browser launching and all other options

## Human-in-the-Loop Monitoring

Once the Optuna Dashboard and the Human Trial Monitor are running:

1.  Open the Optuna Dashboard in your browser (usually `http://localhost:8080`).
2.  Navigate to the study and trial you wish to modify.
3.  In the "Notes" section of a trial, add a new note containing either:
    *   `PRUNE`: To mark the trial as `PRUNED`.
    *   `FAIL`: To mark the trial as `FAIL`.
4.  The monitor script will detect this note change within the specified `--interval` and update the trial's state in the Optuna storage.

**Note on Dry-Run Mode**: If you start the monitor with `--dry-run`, it will log what changes it *would* make without actually modifying the trial states. This is useful for testing.
