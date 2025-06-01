#!/usr/bin/env python3

import optuna
import threading
import time
import sys
import argparse
import logging
import re
import os
from optuna.trial import TrialState
# Import necessary functions directly from the internal module
from optuna_dashboard._note import get_note_from_system_attrs, note_ver_key

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HumanTrialMonitor")

class HumanTrialStateMonitor:
    """
    Optimized monitor for human-in-the-loop trial control via Optuna Dashboard notes.

    This class monitors trials within an Optuna study for changes in their notes
    made through the Optuna Dashboard. It efficiently checks for note updates
    by tracking note versions and processes commands like "PRUNE" or "FAIL".

    Features:
    - Optimized note checking using version tracking.
    - Fetches system attributes only once per check cycle.
    - Customizable command patterns for different actions.
    - Dry-run mode for testing without making actual changes.
    - Efficient change detection to avoid redundant processing.
    - Study version tracking to minimize database queries.
    """
    def __init__(self, study, check_interval=10,
                 prune_pattern=r'PRUNE', fail_pattern=r'FAIL',
                 dry_run=False, only_active_trials=False):
        """
        Initialize the monitor with the given parameters.

        Args:
            study: The optuna.Study object to monitor
            check_interval: How often to check for changes (in seconds)
            prune_pattern: Regex pattern to detect PRUNE commands
            fail_pattern: Regex pattern to detect FAIL commands
            dry_run: If True, log actions but don't actually change trial states
            only_active_trials: If True, only monitor trials that are not already
                              in PRUNED, FAIL, or COMPLETE state
        """
        self.study = study
        self.check_interval = check_interval
        self.running = True
        self.thread = None
        self.dry_run = dry_run
        self.only_active_trials = only_active_trials

        # Compile regex patterns
        self.prune_pattern = re.compile(prune_pattern, re.IGNORECASE)
        self.fail_pattern = re.compile(fail_pattern, re.IGNORECASE)

        # Get proper trial states
        self.FAILED_STATE = TrialState.FAIL

        # Keep track of processed note *versions* to avoid duplicate actions
        # Stores {trial_number: last_processed_note_version}
        self.processed_note_versions = {}
        # Cache for trial_ids to avoid repeated lookups
        self._trial_id_cache = {}
        # Track last known study version to minimize DB queries
        self._last_study_version = None
        # Cache system attributes to reduce DB load
        self._cached_system_attrs = None
        self._cache_timestamp = 0

        logger_msg = [f"Monitor initialized for study: {study.study_name}"]
        if dry_run:
            logger_msg.append("DRY RUN MODE: No state changes will be applied")
        logger.info(" - ".join(logger_msg))

    def _get_trial_id(self, trial_number):
        """Get trial_id from cache or storage, caching the result."""
        if trial_number in self._trial_id_cache:
            return self._trial_id_cache[trial_number]

        try:
            storage = self.study._storage
            study_id = self.study._study_id
            trial_id = None

            # Use get_trial_id_from_study_id_trial_number if available
            if hasattr(storage, 'get_trial_id_from_study_id_trial_number'):
                 trial_id = storage.get_trial_id_from_study_id_trial_number(study_id, trial_number)
            else:
                 # Fallback: Get all trials and find the matching number
                 all_trials_in_study = storage.get_all_trials(study_id, deepcopy=False)
                 found_trial = next((t for t in all_trials_in_study if t.number == trial_number), None)
                 if found_trial:
                     trial_id = found_trial._trial_id

            if trial_id is not None:
                self._trial_id_cache[trial_number] = trial_id
                return trial_id
            else:
                logger.warning(f"Could not determine trial_id for trial number {trial_number}")
                return None
        except Exception as e:
            logger.error(f"Error getting trial_id for trial #{trial_number}: {e}")
            return None


    def check_for_note_changes(self):
        """
        Check all relevant trials in the study for note changes efficiently
        and process any commands found in those notes.
        """
        try:
            storage = self.study._storage
            study_id = self.study._study_id

            # Skip the study version optimization - just proceed with checking trials

            # --- Optimization 2: Cache system attributes with timestamp ---
            current_time = time.time()
            if self._cached_system_attrs is None or (current_time - self._cache_timestamp) > 5:  # 5 second cache
                system_attrs = storage.get_study_system_attrs(study_id)
                self._cached_system_attrs = system_attrs
                self._cache_timestamp = current_time
            else:
                system_attrs = self._cached_system_attrs

            # Get all trials in the study, filtered if needed
            all_trials = self.study.get_trials(deepcopy=False, states=None)

            # Filter trials based on what can be safely changed
            if self.only_active_trials:
                # Monitor only RUNNING and WAITING trials (most restrictive)
                changeable_states = [TrialState.RUNNING, TrialState.WAITING]
            else:
                # Monitor RUNNING, WAITING, and COMPLETE trials (but not PRUNED/FAILED)
                # COMPLETE trials can sometimes be changed depending on Optuna version
                changeable_states = [TrialState.RUNNING, TrialState.WAITING, TrialState.COMPLETE]
            
            trials_to_check = [t for t in all_trials if t.state in changeable_states]
            
            if len(trials_to_check) < len(all_trials):
                excluded_count = len(all_trials) - len(trials_to_check)
                mode = "active-only" if self.only_active_trials else "changeable"
                logger.debug(f"Monitoring {len(trials_to_check)} {mode} trials out of {len(all_trials)} total ({excluded_count} excluded)")

            # Process each relevant trial  
            for trial in trials_to_check:
                try:
                    # Pass pre-fetched system_attrs for efficiency
                    self._check_and_process_trial(trial, system_attrs)
                except Exception as e:
                    # Log error for specific trial processing but continue loop
                    logger.error(f"Error processing trial #{trial.number}: {e}")

        except Exception as e:
            # Log error for the overall check cycle
            logger.error(f"Error during note change check cycle: {e}")

    def _check_and_process_trial(self, trial, system_attrs):
        """
        Check if a trial's note version has changed and process commands if needed.

        Args:
            trial: The optuna.FrozenTrial object to check.
            system_attrs: Pre-fetched system attributes for the study.
        """
        trial_number = trial.number
        trial_id = self._get_trial_id(trial_number)

        if trial_id is None:
            return # Cannot process without trial_id

        try:
            # --- Optimization 2: Check note version first ---
            version_key = note_ver_key(trial_id)
            current_note_version = int(system_attrs.get(version_key, 0))
            last_processed_version = self.processed_note_versions.get(trial_number, -1) # Use -1 to process version 0

            # Only process if the note version is new
            if current_note_version > last_processed_version:
                # Extract the note body *only* when the version has changed
                note_data = get_note_from_system_attrs(system_attrs, trial_id)
                note_body = note_data["body"]

                if not note_body and last_processed_version == -1 and current_note_version == 0:
                     # Skip empty initial notes unless explicitly processed before
                     pass
                else:
                    logger.info(f"📝 Trial #{trial_number} note changed (v{current_note_version}): '{note_body[:100]}{'...' if len(note_body)>100 else ''}'")

                    # Process the note content for commands
                    if self.prune_pattern.search(note_body):
                        logger.info(f"🔶 PRUNE command found in trial #{trial_number}")
                        self._change_trial_state(trial_number, TrialState.PRUNED)
                    elif self.fail_pattern.search(note_body):
                        logger.info(f"🔴 FAIL command found in trial #{trial_number}")
                        self._change_trial_state(trial_number, self.FAILED_STATE)

                    # Update the processed version *after* processing
                    self.processed_note_versions[trial_number] = current_note_version

            # Clean up cache for finished trials to prevent memory leak if monitoring all trials
            if trial.state.is_finished() and trial_number in self._trial_id_cache:
                 del self._trial_id_cache[trial_number]


        except Exception as e:
            logger.error(f"Error checking/processing note for trial #{trial_number}: {e}")

    def _get_trial_state_from_storage(self, trial_number):
        """Get the current state of a trial directly from storage."""
        trial_id = self._get_trial_id(trial_number)
        if trial_id is None:
            logger.warning(f"Could not find trial_id for trial number {trial_number} when checking state.")
            return None
        try:
            storage = self.study._storage
            # Get the FrozenTrial object from storage using trial_id
            frozen_trial = storage.get_trial(trial_id)
            return frozen_trial.state
        except Exception as e:
            logger.error(f"Error getting state from storage for trial #{trial_number} (ID: {trial_id}): {e}")
            return None


    def _change_trial_state(self, trial_number, new_state):
        """
        Change a trial's state using study.tell() and verify using storage.

        Args:
            trial_number: The number of the trial to modify
            new_state: The new TrialState to set
        """
        try:
            # Get current state directly from storage to avoid study.get_trial()
            current_state = self._get_trial_state_from_storage(trial_number)

            if current_state is None:
                logger.error(f"Could not determine current state for trial #{trial_number}. Skipping state change.")
                return

            # Skip if already in the target state
            if current_state == new_state:
                logger.info(f"Trial #{trial_number} is already in state {new_state}")
                # Ensure version is marked as processed even if state doesn't change
                # Note: This logic is now handled in _check_and_process_trial
                return

            # Skip if trial is not in a state that can be changed by tell()
            # Typically RUNNING or WAITING. COMPLETE might sometimes be allowed depending on Optuna version/storage.
            if current_state not in [TrialState.RUNNING, TrialState.WAITING, TrialState.COMPLETE]:
                logger.warning(f"Cannot change trial #{trial_number} from state {current_state} to {new_state} using study.tell()")
                return

            # Change the state (or just log in dry-run mode)
            if self.dry_run:
                logger.info(f"DRY RUN: Would change trial #{trial_number} from {current_state} to {new_state}")
            else:
                logger.info(f"Attempting to change trial #{trial_number} state from {current_state} to {new_state}")
                # Use study.tell() as it seems available based on previous logs
                try:
                    self.study.tell(trial_number, state=new_state, values=None) # Explicitly set values=None for PRUNE/FAIL
                    logger.info(f"study.tell() called for trial #{trial_number} to set state {new_state}")
                except Exception as tell_error:
                     logger.error(f"Error calling study.tell() for trial #{trial_number}: {tell_error}")
                     # Don't proceed with verification if tell failed
                     return

                # Verify the change by checking storage again
                time.sleep(0.5) # Add a small delay to allow storage update
                updated_state = self._get_trial_state_from_storage(trial_number)

                if updated_state == new_state:
                    logger.info(f"Successfully verified trial #{trial_number} state changed to {new_state}")
                elif updated_state is not None:
                    logger.warning(f"Verification failed for trial #{trial_number}. State is {updated_state}, expected {new_state}")
                else:
                    logger.warning(f"Could not verify state change for trial #{trial_number}.")

        except Exception as e:
            # Log the specific error related to state change
            logger.error(f"Unexpected error during state change process for trial #{trial_number}: {e}")


    def monitor_loop(self):
        """Main monitoring loop that runs in a separate thread"""
        logger.info("Starting monitor thread")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Check for note changes
                self.check_for_note_changes()
                # Reset error counter on success
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Critical error in monitor loop (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                # If too many consecutive errors, increase sleep time
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors. Pausing for {self.check_interval * 10} seconds...")
                    time.sleep(self.check_interval * 10)
                    consecutive_errors = 0  # Reset counter after long pause
                    # Try to clear caches in case of stale data
                    self._trial_id_cache.clear()
                    self._cached_system_attrs = None
                    logger.info("Cleared caches and resuming monitoring...")
                else:
                    # Shorter pause for transient errors
                    time.sleep(self.check_interval * 2)
                continue

            time.sleep(self.check_interval)
        logger.info("Monitor thread finished.")


    def start(self):
        """Start the monitoring thread"""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            # Use a more descriptive thread name
            self.thread = threading.Thread(target=self.monitor_loop, name=f"OptunaMonitor-{self.study.study_name}")
            self.thread.daemon = True
            self.thread.start()
            logger.info(f"Monitor thread started for study '{self.study.study_name}'")

    def stop(self):
        """Stop the monitoring thread"""
        logger.info(f"Stopping monitor thread for study '{self.study.study_name}'...")
        self.running = False
        if self.thread and self.thread.is_alive():
            # Wait a bit longer if needed
            self.thread.join(timeout=max(10, self.check_interval * 2))
            if self.thread.is_alive():
                 logger.warning("Monitor thread did not stop gracefully.")
            else:
                 logger.info("Monitor thread stopped.")
        else:
            logger.info("Monitor thread was not running or already stopped.")


def main():
    parser = argparse.ArgumentParser(description="Optimized Human-in-the-loop trial state monitor for Optuna")
    # Database connection options
    db_group = parser.add_argument_group('Database connection')
    db_group.add_argument("--db-url", help="Database URL for Optuna storage")
    db_group.add_argument("--db-host", help="Database hostname")
    db_group.add_argument("--db-port", help="Database port")
    db_group.add_argument("--db-name", help="Database name")
    db_group.add_argument("--db-user", help="Database username")
    db_group.add_argument("--db-password", help="Database password")
    db_group.add_argument("--db-type", default="postgresql", help="Database type (e.g., postgresql, mysql, sqlite) (default: postgresql)")
    db_group.add_argument("--cert-path", help="Path to CA certificate file")
    db_group.add_argument("--use-cert", action="store_true", help="Explicitly use the certificate specified by --cert-path")
    db_group.add_argument("--no-cert", action="store_true", help="Explicitly disable certificate usage")

    # Monitor configuration
    monitor_group = parser.add_argument_group('Monitor configuration')
    monitor_group.add_argument("--study", nargs='*', help="Specific study name(s) to monitor (default: monitor all studies if none specified)")
    monitor_group.add_argument("--interval", type=int, default=10, help="Check interval in seconds (default: 10)") # Increased default
    monitor_group.add_argument("--prune-pattern", default="PRUNE", help="Regex pattern to detect PRUNE commands (default: 'PRUNE')")
    monitor_group.add_argument("--fail-pattern", default="FAIL", help="Regex pattern to detect FAIL commands (default: 'FAIL')")
    monitor_group.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes applied)")
    monitor_group.add_argument("--only-active-trials", action="store_true", help="Monitor only RUNNING and WAITING trials (excludes COMPLETE trials which may have notes added later)")
    monitor_group.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    args = parser.parse_args()

    # Set logging level based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    # Reconfigure root logger if needed, or just our logger
    # logging.basicConfig(level=log_level, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s', force=True)
    logger.setLevel(log_level)
    # Ensure handlers are set up correctly if basicConfig was already called
    if not logger.handlers:
         handler = logging.StreamHandler(sys.stdout)
         formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
         handler.setFormatter(formatter)
         logger.addHandler(handler)
         logger.propagate = False # Avoid duplicate messages if root logger also has handlers


    # Determine the database URL
    db_url = args.db_url
    if not db_url:
        # Determine if certificate should be used
        use_cert = False
        cert_path = args.cert_path
        if args.no_cert:
            use_cert = False
            cert_path = "" # Clear path if no-cert is specified
        elif args.use_cert:
            # If --use-cert was explicitly given, cert_path should already be set or default
            if not cert_path:
                logger.error("Error: --use-cert specified but no --cert-path provided.")
                return 1
            if not os.path.exists(cert_path):
                logger.error(f"Error: Certificate file not found at {cert_path}")
                sys.exit(1)
            use_cert = True
        else:
            # If neither --use-cert nor --no-cert was specified, check for default cert
            default_cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cert", "ca.pem")
            if os.path.exists(default_cert_path):
                cert_path = default_cert_path
                use_cert = True
                logger.info(f"Automatically using default CA certificate at {cert_path}")
            else:
                cert_path = "" # Ensure it's empty if no cert is found/used
                use_cert = False

        if args.db_host and args.db_port and args.db_name and args.db_user and args.db_password:
            # Construct DB URL from components
            if args.db_type == "postgresql":
                db_url = f"postgresql://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_name}"
                if use_cert and cert_path:
                    db_url = f"{db_url}?sslmode=require&sslrootcert={cert_path}"
            elif args.db_type == "mysql":
                db_url = f"mysql://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_name}"
                if use_cert and cert_path:
                    db_url = f"{db_url}?ssl_ca={cert_path}"
            elif args.db_type == "sqlite":
                db_url = f"sqlite:///{args.db_name}"
            else:
                logger.error(f"Unsupported database type: {args.db_type}")
                sys.exit(1)

    if not db_url:
        logger.error("Database URL is required. Provide either --db-url or all of: --db-host, --db-port, --db-name, --db-user, --db-password")
        sys.exit(1)

    # Connect to the database
    logger.info(f"Connecting to database associated with host: {args.db_host or db_url.split('@')[-1].split('/')[0]}") # Mask password if using URL

    monitors = []
    try:
        studies_to_monitor = []
        if args.study:
            # Check if user wants to monitor all studies
            if len(args.study) == 1 and args.study[0].lower() == 'all':
                logger.info("Loading all studies from the database...")
                all_study_summaries = optuna.get_all_study_summaries(storage=db_url)
                if not all_study_summaries:
                    logger.warning("No studies found in the database to monitor.")
                    return 0
                studies_to_monitor = [s.study_name for s in all_study_summaries]
                logger.info(f"Found {len(studies_to_monitor)} studies. Starting monitors for all of them...")
            else:
                # Monitor specific studies provided by argument
                # Filter out empty strings
                studies_to_monitor = [s for s in args.study if s.strip()]
                if not studies_to_monitor:
                    logger.warning("No valid study names provided (empty strings ignored).")
                    logger.info("To monitor all studies, specify '--study all'")
                    logger.info("To monitor specific studies, use '--study study1 study2 ...'")
                    return 0
                logger.info(f"Monitoring specified studies: {', '.join(studies_to_monitor)}")
        else:
            # No studies specified - don't monitor any by default
            logger.info("No specific studies provided. Not monitoring any studies.")
            logger.info("To monitor all studies, specify '--study all'")
            logger.info("To monitor specific studies, use '--study study1 study2 ...'")
            return 0

        for study_name in studies_to_monitor:
            logger.info(f"Loading study: {study_name}")
            # Retry logic for loading study
            max_retries = 3
            retry_delay = 2
            
            for retry in range(max_retries):
                try:
                    study = optuna.load_study(study_name=study_name, storage=db_url)
                    monitor = HumanTrialStateMonitor(
                        study,
                        check_interval=args.interval,
                        prune_pattern=args.prune_pattern,
                        fail_pattern=args.fail_pattern,
                        dry_run=args.dry_run,
                        only_active_trials=args.only_active_trials
                    )
                    monitor.start()
                    monitors.append(monitor)
                    logger.info(f"Started monitoring for study: {study_name}")
                    break  # Success
                except Exception as load_err:
                    if retry < max_retries - 1:
                        logger.warning(f"Failed to load study '{study_name}' (attempt {retry + 1}/{max_retries}): {load_err}")
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"Failed to load or start monitor for study '{study_name}' after {max_retries} attempts: {load_err}")

        if monitors:
            logger.info(f"Successfully started monitoring for {len(monitors)} studies.")

        if not monitors:
             logger.warning("No monitors started. Exiting.")
             return 0

        # Keep the script running
        logger.info(f"Monitor(s) running. Configuration:")
        logger.info(f"  - Prune pattern: '{args.prune_pattern}'")
        logger.info(f"  - Fail pattern: '{args.fail_pattern}'")
        logger.info(f"  - Check interval: {args.interval} seconds")
        logger.info(f"  - Dry run: {args.dry_run}")
        logger.info(f"  - Monitoring {'only potentially active' if args.only_active_trials else 'all'} trials")
        logger.info("Press Ctrl+C to stop.")

        while True:
            # Check if any monitor threads are still alive
            if not any(m.thread and m.thread.is_alive() for m in monitors):
                 logger.warning("All monitor threads seem to have stopped unexpectedly.")
                 break
            time.sleep(5) # Main thread sleep

    except KeyboardInterrupt:
        logger.info("Ctrl+C received. Stopping monitors...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        for monitor in monitors:
            monitor.stop()
        logger.info("All monitors stopped. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    sys.exit(main())