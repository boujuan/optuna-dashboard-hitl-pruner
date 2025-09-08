# Linux Local Adaptation Task

## Objective

Adapt the optuna-dashboard-hitl-pruner for optimal Linux compatibility and streamlined local tuning process tracking using SQLite. The current system is designed primarily for remote PostgreSQL/MySQL databases with SSH tunneling, but needs adaptation for local development workflows common in Linux environments.

## Key Requirements

### 1. Linux Compatibility Issues
- **Port Management**: Current system uses multiple Unix tools (`lsof`, `fuser`, `netstat`, `ss`) for port conflict detection and process management
- **Process Management**: Uses Linux-specific commands (`pkill`, `kill`, `pgrep`) for cleanup
- **Path Handling**: Uses bash scripts that need to work reliably across Linux distributions
- **SSH Integration**: SSH tunneling features need testing on various Linux setups

### 2. Local SQLite Workflow
- **Database Setup**: Streamline SQLite database creation and initialization for local studies
- **Study Management**: Simplified workflows for creating, monitoring, and managing local optimization studies
- **File-based Storage**: Optimize for local file system performance and reliability
- **No-server Mode**: Option to run without remote database dependencies

### 3. Installation and Distribution
- **Package Installation**: Ensure `pip install .` works correctly on Linux systems
- **Dependency Management**: Handle Linux-specific package dependencies (psycopg2-binary, mysqlclient alternatives)
- **Environment Setup**: Streamline conda/miniforge environment setup on Linux

### 4. Testing and Validation
- **Cross-distribution Testing**: Test on Ubuntu, Debian, Fedora, Arch Linux
- **Performance Validation**: Ensure monitoring performance is acceptable for local workflows
- **Error Handling**: Robust error handling for common Linux configuration issues

## Implementation Areas

### Core Components to Address
1. **launcher.py**: Port management and process handling logic
2. **human_trial_monitor.py**: Database connection and monitoring optimization
3. **run_optuna_miniforge.sh**: Linux shell script compatibility
4. **setup.py**: Linux-specific installation requirements
5. **SQLite Integration**: Local database workflow optimization

### New Features Needed
1. **Local Study Templates**: Quick-start templates for common optimization scenarios
2. **SQLite Browser Integration**: Better SQLite database browsing and management
3. **Local Performance Monitoring**: System resource monitoring for optimization processes
4. **Config Management**: Local configuration file management

## Success Criteria

### Technical Requirements
- [ ] All port management functions work reliably across major Linux distributions
- [ ] SQLite-based workflows perform efficiently for studies with 100+ trials
- [ ] Installation via `pip install .` succeeds on fresh Linux systems
- [ ] Chrome extension works with Linux browsers (Chrome, Chromium, Firefox)
- [ ] SSH tunneling features work with standard Linux SSH configurations

### User Experience Requirements
- [ ] Single-command setup for new local optimization projects
- [ ] Clear documentation for Linux-specific configuration
- [ ] Robust error messages for common Linux configuration issues
- [ ] Performance comparable to or better than remote database workflows

### Validation Requirements
- [ ] Automated tests for Linux compatibility
- [ ] Example projects demonstrating local SQLite workflows
- [ ] Documentation for different Linux distributions
- [ ] Performance benchmarks for local vs remote workflows

## Timeline

**Phase 1: Analysis and Linux Compatibility** (Current)
- Audit current Linux compatibility issues
- Identify platform-specific dependencies and alternatives
- Test current system on multiple Linux distributions

**Phase 2: SQLite Workflow Optimization**
- Implement streamlined SQLite database setup
- Optimize monitoring performance for local databases
- Create local study management utilities

**Phase 3: Testing and Documentation**
- Comprehensive testing across Linux distributions
- Create Linux-specific documentation
- Performance validation and optimization

**Phase 4: Distribution and Deployment**
- Package optimization for Linux distribution
- Create installation automation
- User acceptance testing

## Context Manifest

### How the Current System Works: Optuna Dashboard with Human-in-the-Loop Monitoring

The optuna-dashboard-hitl-pruner is a comprehensive system that wraps Optuna Dashboard with enhanced human-in-the-loop trial management capabilities. When a user launches the system, the flow begins with the `run_optuna_miniforge.sh` bash script, which handles Conda environment activation and then delegates to the Python launcher.

The main entry point (`optuna_monitor/launcher.py`) orchestrates multiple services in parallel. It first performs environment validation by checking for required Python packages (optuna, optuna-dashboard, and database-specific drivers like psycopg2-binary or mysqlclient). The launcher supports three database backends: PostgreSQL (default), MySQL, and SQLite, with full SSL certificate support and SSH tunneling capabilities for remote databases.

**Port Management and Process Control**: The system implements sophisticated port conflict resolution using multiple Unix utilities. It attempts to detect port conflicts using `lsof -ti :PORT`, falls back to `fuser PORT/tcp`, then `netstat -tlnp`, and finally `ss -tlnp`. When port conflicts are detected and `--force-port` is specified, it systematically kills processes using `pkill`, `kill -TERM`, and `kill -9` commands, with special handling for process trees and WSL environments.

**Database Connection Architecture**: The system constructs database URLs based on the specified backend. For PostgreSQL: `postgresql://user:pass@host:port/db?sslmode=require&sslrootcert=path`. For MySQL: `mysql://user:pass@host:port/db?ssl_ca=path`. For SQLite: `sqlite:///database_name`. SSL certificates are handled through a detection hierarchy: explicit `--use-cert`/`--no-cert` flags, automatic detection of `cert/ca.pem`, or no SSL.

**SSH Tunneling Implementation**: When SSH parameters are provided, the system establishes an SSH tunnel using `ssh -N -L local_port:remote_host:remote_port` with additional reliability options. The tunnel process is tracked globally and cleaned up on exit. Local database connections are then redirected through `localhost:local_port`.

**Human Trial Monitor**: The core monitoring logic runs in a separate thread, implementing an optimized note-checking algorithm. It tracks note versions per trial using Optuna's system attributes (`dashboard:trial_id:note_ver`), only processing trials when note versions change. The monitor searches note content for configurable regex patterns (default: "PRUNE" and "FAIL") and uses `study.tell()` to change trial states accordingly.

**Chrome Extension Integration**: A companion Chrome extension provides one-click pruning/failing through hover buttons that inject notes directly into the dashboard interface, eliminating the need for manual note editing.

### For Linux Local Adaptation: Critical Integration Points

Since we're optimizing for Linux compatibility and local SQLite workflows, several system components require careful attention:

**Process Management Compatibility**: The current port management logic assumes availability of Unix tools (`lsof`, `fuser`, `netstat`, `ss`, `pkill`, `kill`, `pgrep`) which may have different behaviors or availability across Linux distributions. Ubuntu/Debian systems typically have all these tools, but minimal installations or container environments might lack some utilities.

**SQLite Optimization Opportunities**: The current SQLite implementation is basic (`sqlite:///db_name`) and doesn't leverage SQLite-specific optimizations for local development. Unlike PostgreSQL/MySQL connections that assume network latency, SQLite should benefit from different monitoring intervals, reduced connection pooling, and local file system optimizations.

**Dependency Management**: The package installation logic currently handles PostgreSQL (`psycopg2-binary`) and MySQL (`mysqlclient`) drivers but doesn't optimize for SQLite-only installations. Linux distributions often have these packages available through system package managers, which might be more reliable than pip installation.

**Chrome Extension Linux Browser Support**: While the extension supports Chrome/Chromium, it needs validation with Firefox and other Linux browsers. The browser launching logic uses platform-specific paths that need Linux distribution awareness.

### Technical Reference Details

#### Core Component Interfaces

**Launcher Entry Point**:
```python
def main():  # optuna_monitor/launcher.py
    # Arguments: db_url, db_type, port, study, interval, ssh_*, browser_path
    # Returns: None (runs indefinitely until interrupted)
```

**Monitor Class**:
```python
class HumanTrialStateMonitor:  # optuna_monitor/human_trial_monitor.py
    def __init__(study, check_interval=10, prune_pattern='PRUNE', fail_pattern='FAIL', dry_run=False, only_active_trials=False)
    def start()  # Starts monitoring thread
    def stop()   # Graceful shutdown
```

#### Database URL Patterns
- PostgreSQL: `postgresql://user:pass@host:port/dbname?sslmode=require&sslrootcert=cert.pem`
- MySQL: `mysql://user:pass@host:port/dbname?ssl_ca=cert.pem`
- SQLite: `sqlite:///dbname` (relative path) or `sqlite:////absolute/path/dbname`

#### Port Management Process Flow
1. Check port availability with `socket.bind()`
2. If occupied and `--force-port`:
   - Collect PIDs using `lsof -ti :port`
   - Fallback to `fuser port/tcp` for additional PIDs
   - Kill process trees with `pkill -TERM -P pid`
   - Force kill with `kill -9 pid`
   - Wait up to 15 seconds for port release

#### Configuration Requirements
- **Conda Environment**: Activated through `run_optuna_miniforge.sh` (default: `wf_env`)
- **Python Packages**: optuna, optuna-dashboard, plus database drivers
- **System Tools**: lsof, fuser, netstat, ss, pkill, kill, pgrep (not all required, fallback chain)
- **Browser Path**: Distribution-specific paths for Chrome/Firefox

#### File Locations for Implementation
- Main launcher logic: `/optuna_monitor/launcher.py` (lines 285-638)
- Monitor implementation: `/optuna_monitor/human_trial_monitor.py` (lines 23-382)
- Package setup: `/setup.py`
- Shell wrapper: `/run_optuna_miniforge.sh`
- Chrome extension: `/chrome-extension/` (manifest.json, content.js, popup.js)

#### SQLite-specific Optimizations Needed
- Local file path validation and creation
- Reduced monitoring intervals (SQLite has no network latency)
- File system permission handling
- WAL mode optimization for concurrent access
- Backup and recovery strategies for local files

## Notes

- Current system has robust database support but is optimized for remote databases
- Port management uses comprehensive Unix tool fallback chain but needs distribution testing
- SSH tunneling should be preserved as optional feature while prioritizing local workflows
- Chrome extension architecture supports Linux browsers but needs validation
- SQLite support exists but lacks local development workflow optimizations