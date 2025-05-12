#!/usr/bin/env python3

import optuna
import threading
import time
import sys
import argparse
import logging
import re
from optuna.trial import TrialState
from optuna_dashboard._note import get_note_from_system_attrs, note_ver_key, note_str_key_prefix

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HumanTrialMonitor")

class HumanTrialStateMonitor:
    """
    Monitor for human-in-the-loop trial control via Optuna Dashboard notes.

    This class monitors trials within an Optuna study for changes in their notes
    made through the Optuna Dashboard. When a note contains command patterns like
    "PRUNE" or "FAIL", it will automatically update the trial's state accordingly.

    Features:
    - Customizable command patterns for different actions
    - Dry-run mode for testing without making actual changes
    - Efficient change detection to avoid redundant processing
    """
    def __init__(self, study, check_interval=10,
                 prune_pattern=r'PRUNE', fail_pattern=r'FAIL',
                 dry_run=False, only_active_trials=True):
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

        # Get proper trial states (handle different Optuna versions)
        # We know it's FAIL from examining _state.py
        self.FAILED_STATE = TrialState.FAIL

        # Keep track of processed notes to avoid duplicate actions
        self.processed_notes = {}

        logger_msg = [f"Monitor initialized for study: {study.study_name}"]
        if dry_run:
            logger_msg.append("DRY RUN MODE: No state changes will be applied")
        logger.info(" - ".join(logger_msg))

    def _get_trial_note(self, trial):
        """
        Get note for a trial using the study's storage directly.

        This is a workaround for the fact that FrozenTrial objects don't have
        a storage attribute, which is required by optuna_dashboard.get_note().

        Args:
            trial: The optuna.FrozenTrial object

        Returns:
            str: The note text, or empty string if no note exists
        """
        try:
            # Access study's storage and study_id
            storage = self.study._storage
            study_id = self.study._study_id
            trial_id = None

            # Get the trial's internal id
            # First try to get it directly from the trial if available
            if hasattr(trial, "_trial_id"):
                trial_id = trial._trial_id
            else:
                # Otherwise, we need to look it up from the database
                # This can happen with older Optuna versions
                # Use get_trial_id_from_study_id_trial_number if available
                if hasattr(storage, 'get_trial_id_from_study_id_trial_number'):
                    trial_id = storage.get_trial_id_from_study_id_trial_number(study_id, trial.number)
                else:
                    # Fallback: Get all trials and find the matching number
                    all_trials_in_study = storage.get_all_trials(study_id, deepcopy=False)
                    found_trial = next((t for t in all_trials_in_study if t.number == trial.number), None)
                    if found_trial:
                        trial_id = found_trial._trial_id
                    else:
                        logger.warning(f"Could not find trial_id for trial number {trial.number}")
                        return ""

            if trial_id is None:
                 logger.warning(f"Could not determine trial_id for trial number {trial.number}")
                 return ""

            # Get the system attributes for this study
            system_attrs = storage.get_study_system_attrs(study_id)

            # Use optuna_dashboard's helper function to extract the note
            note = get_note_from_system_attrs(system_attrs, trial_id)
            return note["body"]

        except Exception as e:
            logger.error(f"Error reading note for trial #{trial.number}: {e}")
            return ""

    def check_for_note_changes(self):
        """
        Check all trials in the study for note changes and process any commands
        found in those notes.
        """
        try:
            # Get all trials in the study, filtered if needed
            all_trials = self.study.get_trials(deepcopy=False, states=None)

            # Filter trials if needed
            if self.only_active_trials:
                inactive_states = [TrialState.PRUNED, self.FAILED_STATE]
                trials = [t for t in all_trials if t.state not in inactive_states]
                if len(trials) < len(all_trials):
                    logger.debug(f"Monitoring {len(trials)} active trials out of {len(all_trials)} total trials")
            else:
                trials = all_trials

            # Process each trial
            for trial in trials:
                try:
                    self._check_and_process_trial(trial)
                except Exception as e:
                    logger.error(f"Error processing trial #{trial.number}: {e}")

        except Exception as e:
            logger.error(f"Error checking for note changes: {e}")

    def _check_and_process_trial(self, trial):
        """
        Check if a trial's note has changed and process any commands in it.

        Args:
            trial: The optuna.FrozenTrial object to check
        """
        trial_number = trial.number

        try:
            # Use our custom function to get the note
            note = self._get_trial_note(trial)

            # Skip if no note
            if not note:
                return

            # Skip if we've already processed this exact note
            if trial_number in self.processed_notes and self.processed_notes[trial_number] == note:
                return

            # We have a new or changed note
            logger.info(f"New or changed note detected for trial #{trial_number}: {note}")

            # Process the note for commands
            if self.prune_pattern.search(note):
                logger.info(f"PRUNE command found in note for trial #{trial_number}")
                self._change_trial_state(trial_number, TrialState.PRUNED)
            elif self.fail_pattern.search(note):
                logger.info(f"FAIL command found in note for trial #{trial_number}")
                self._change_trial_state(trial_number, self.FAILED_STATE)

            # Remember we've processed this note
            self.processed_notes[trial_number] = note

        except Exception as e:
            logger.error(f"Error checking note for trial #{trial_number}: {e}")

    def _get_trial_state_from_storage(self, trial_number):
        """Get the current state of a trial directly from storage."""
        try:
            storage = self.study._storage
            study_id = self.study._study_id
            trial_id = None

            # Get trial_id (using the same logic as in _get_trial_note)
            if hasattr(storage, 'get_trial_id_from_study_id_trial_number'):
                 trial_id = storage.get_trial_id_from_study_id_trial_number(study_id, trial_number)
            else:
                 all_trials_in_study = storage.get_all_trials(study_id, deepcopy=False)
                 found_trial = next((t for t in all_trials_in_study if t.number == trial_number), None)
                 if found_trial:
                     trial_id = found_trial._trial_id

            if trial_id is None:
                logger.warning(f"Could not find trial_id for trial number {trial_number} when checking state.")
                return None

            # Get the FrozenTrial object from storage
            frozen_trial = storage.get_trial(trial_id)
            return frozen_trial.state
        except Exception as e:
            logger.error(f"Error getting state from storage for trial #{trial_number}: {e}")
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
                return

            # Skip if trial is not in a state that can be changed
            if current_state not in [TrialState.RUNNING, TrialState.COMPLETE, TrialState.WAITING]:
                logger.warning(f"Cannot change trial #{trial_number} from state {current_state} to {new_state}")
                return

            # Change the state (or just log in dry-run mode)
            if self.dry_run:
                logger.info(f"DRY RUN: Would change trial #{trial_number} from {current_state} to {new_state}")
            else:
                logger.info(f"Changing trial #{trial_number} state from {current_state} to {new_state}")
                # Use study.tell() as it seems available based on previous logs
                self.study.tell(trial_number, state=new_state)

                # Verify the change by checking storage again
                time.sleep(0.5) # Add a small delay to allow storage update
                updated_state = self._get_trial_state_from_storage(trial_number)

                if updated_state == new_state:
                    logger.info(f"Successfully changed trial #{trial_number} state to {new_state}")
                elif updated_state is not None:
                    logger.warning(f"Failed to change trial #{trial_number} state. Still {updated_state}")
                else:
                    logger.warning(f"Could not verify state change for trial #{trial_number}.")

        except Exception as e:
            # Log the specific error related to state change
            logger.error(f"Error changing state for trial #{trial_number}: {e}")


    def monitor_loop(self):
        """Main monitoring loop that runs in a separate thread"""
        logger.info("Starting monitor thread")
        while self.running:
            try:
                # Check for note changes
                self.check_for_note_changes()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            time.sleep(self.check_interval)

    def start(self):
        """Start the monitoring thread"""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self.monitor_loop)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Monitor thread started")

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=self.check_interval*2)
            logger.info("Monitor thread stopped")

def main():
    parser = argparse.ArgumentParser(description="Human-in-the-loop trial state monitor for Optuna")
    # Database connection options
    db_group = parser.add_argument_group('Database connection')
    db_group.add_argument("--db-url", help="Database URL for Optuna storage")
    db_group.add_argument("--db-host", help="Database hostname")
    db_group.add_argument("--db-port", help="Database port")
    db_group.add_argument("--db-name", help="Database name")
    db_group.add_argument("--db-user", help="Database username")
    db_group.add_argument("--db-password", help="Database password")
    db_group.add_argument("--cert-path", help="Path to CA certificate file")

    # Monitor configuration
    monitor_group = parser.add_argument_group('Monitor configuration')
    monitor_group.add_argument("--study", help="Specific study name to monitor (default: monitor all studies)")
    monitor_group.add_argument("--interval", type=int, default=5, help="Check interval in seconds (default: 5)")
    monitor_group.add_argument("--prune-pattern", default="PRUNE", help="Regex pattern to detect PRUNE commands (default: 'PRUNE')")
    monitor_group.add_argument("--fail-pattern", default="FAIL", help="Regex pattern to detect FAIL commands (default: 'FAIL')")
    monitor_group.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes applied)")
    monitor_group.add_argument("--all-trials", action="store_true", help="Monitor all trials, not just active ones")
    monitor_group.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Determine the database URL
    db_url = args.db_url
    if not db_url and args.db_host and args.db_port and args.db_name and args.db_user and args.db_password:
        # Construct DB URL from components
        if args.cert_path:
            db_url = f"postgresql://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_name}?sslmode=require&sslrootcert={args.cert_path}"
        else:
            db_url = f"postgresql://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_name}"

    if not db_url:
        logger.error("Database URL is required. Provide either --db-url or all of: --db-host, --db-port, --db-name, --db-user, --db-password")
        sys.exit(1)

    # Connect to the database
    logger.info(f"Connecting to database: {db_url.split('@')[-1].split('/')[0]}")

    # Common monitor params
    monitor_params = {
        'check_interval': args.interval,
        'prune_pattern': args.prune_pattern,
        'fail_pattern': args.fail_pattern,
        'dry_run': args.dry_run,
        'only_active_trials': not args.all_trials
    }

    try:
        if args.study:
            # Monitor a specific study
            study = optuna.load_study(study_name=args.study, storage=db_url)
            monitor = HumanTrialStateMonitor(study, **monitor_params)
            monitor.start()
            logger.info(f"Monitoring study: {args.study}")
        else:
            # Monitor all studies in the database
            studies = optuna.get_all_study_summaries(storage=db_url)
            monitors = []

            if not studies:
                logger.warning("No studies found in the database")

            for study_summary in studies:
                study = optuna.load_study(study_name=study_summary.study_name, storage=db_url)
                monitor = HumanTrialStateMonitor(study, **monitor_params)
                monitor.start()
                monitors.append(monitor)
                logger.info(f"Monitoring study: {study.study_name}")

            if monitors:
                logger.info(f"Monitoring {len(monitors)} studies in total")

        # Keep the script running
        logger.info(f"Monitor running with configuration:")
        logger.info(f"  - Prune pattern: '{args.prune_pattern}'")
        logger.info(f"  - Fail pattern: '{args.fail_pattern}'")
        logger.info(f"  - Check interval: {args.interval} seconds")
        logger.info(f"  - Dry run: {args.dry_run}")
        logger.info(f"  - Monitoring {'all' if args.all_trials else 'only active'} trials")
        logger.info("Press Ctrl+C to stop.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Stopping monitor...")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()