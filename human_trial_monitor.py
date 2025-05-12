#!/usr/bin/env python3

import optuna
import threading
import time
import sys
import argparse
import logging
import re
from optuna.trial import TrialState

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HumanTrialMonitor")

class HumanTrialStateMonitor:
    def __init__(self, study, check_interval=10):
        self.study = study
        self.check_interval = check_interval
        self.running = True
        self.thread = None
        self.prune_pattern = re.compile(r'PRUNE', re.IGNORECASE)
        self.fail_pattern = re.compile(r'FAIL', re.IGNORECASE)
        
        # Set up a place to store state change requests
        if "state_change_requests" not in study.user_attrs:
            study.set_user_attr("state_change_requests", "")
            
        logger.info(f"Monitor initialized for study: {study.study_name}")
    
    def check_notes_for_commands(self):
        """Check all trial notes for prune/fail commands"""
        try:
            logger.info(f"Checking notes for study {self.study.study_name} (ID: {self.study._study_id})")
            trials = self.study.get_trials(deepcopy=False)
            logger.info(f"Found {len(trials)} trials to check")
            
            # Force a refresh of the study (optional, try if other fixes don't work)
            # self.study = optuna.load_study(study_name=self.study.study_name, storage=self.study._storage)
            
            # Log trials with notes
            trials_with_notes = [t for t in trials if "note" in t.user_attrs]
            logger.info(f"Found {len(trials_with_notes)} trials with notes")
            for trial in trials_with_notes:
                logger.info(f"Trial #{trial.number} has note: {trial.user_attrs['note']}")
            
            for trial in trials:
                # Skip if there's no note
                if "note" not in trial.user_attrs:
                    continue
                
                note = trial.user_attrs["note"]
                trial_id = trial.number
                
                # Skip if already processed this note (has confirmation message)
                if "✅ Marked this trial" in note:
                    continue
                
                # Look for pruning command
                if self.prune_pattern.search(note):
                    self._add_state_change_request(trial_id, "PRUNED", note)
                    new_note = f"✅ Marked this trial (#{trial_id}) for PRUNING.\nOriginal note: {note}"
                    trial.set_user_attr("note", new_note)
                    logger.info(f"Received request to PRUNE trial #{trial_id}")
                
                # Look for fail command
                elif self.fail_pattern.search(note):
                    self._add_state_change_request(trial_id, "FAILED", note)
                    new_note = f"✅ Marked this trial (#{trial_id}) for FAILING.\nOriginal note: {note}"
                    trial.set_user_attr("note", new_note)
                    logger.info(f"Received request to FAIL trial #{trial_id}")
        
        except Exception as e:
            logger.error(f"Error checking notes: {e}")
    
    def _add_state_change_request(self, trial_id, target_state, original_note):
        """Add a state change request."""
        current_requests = self.study.user_attrs.get("state_change_requests", "")
        request = f"{trial_id}:{target_state}"
        
        if request not in current_requests.split(","):
            new_requests = current_requests + f",{request}" if current_requests else request
            self.study.set_user_attr("state_change_requests", new_requests)
    
    def monitor_and_process_requests(self):
        """Monitor for state change requests and apply them."""
        logger.info("Starting monitor thread")
        while self.running:
            try:
                # Check for commands in notes
                self.check_notes_for_commands()
                
                # Process any pending requests
                requests = self.study.user_attrs.get("state_change_requests", "")
                if requests:
                    processed_requests = []
                    for request in requests.split(","):
                        if request:
                            try:
                                trial_id, target_state = request.split(":")
                                trial_id = int(trial_id)
                                
                                if self._change_trial_state(trial_id, target_state):
                                    processed_requests.append(request)
                            except (ValueError, IndexError) as e:
                                logger.error(f"Invalid request format: {request}, error: {e}")
                    
                    # Clear processed requests
                    if processed_requests:
                        new_requests = ",".join([r for r in requests.split(",") if r and r not in processed_requests])
                        self.study.set_user_attr("state_change_requests", new_requests)
                        logger.info(f"Processed state changes: {processed_requests}")
            except Exception as e:
                logger.error(f"Error in state change monitor: {e}")
            
            time.sleep(self.check_interval)
    
    def _change_trial_state(self, trial_id, target_state):
        """Change a trial's state."""
        try:
            trial = self.study.get_trial(trial_id)
            current_state = trial.state
            
            # Convert string state to TrialState enum
            if target_state == "PRUNED":
                new_state = TrialState.PRUNED
            elif target_state == "FAILED":
                new_state = TrialState.FAILED
            else:
                logger.error(f"Unknown target state: {target_state}")
                return False
            
            # Skip if already in target state
            if current_state == new_state:
                logger.info(f"Trial #{trial_id} is already in state {target_state}")
                return True
                
            # Handle state change via tell()
            logger.info(f"Changing trial #{trial_id} state from {current_state} to {new_state}")
            self.study.tell(trial_id, state=new_state)
            return True
                
        except Exception as e:
            logger.error(f"Error changing state for trial #{trial_id}: {e}")
            return False
    
    def start(self):
        """Start the monitoring thread."""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self.monitor_and_process_requests)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Monitor thread started")
    
    def stop(self):
        """Stop the monitoring thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=self.check_interval*2)
            logger.info("Monitor thread stopped")

def main():
    parser = argparse.ArgumentParser(description="Human-in-the-loop trial state monitor for Optuna")
    parser.add_argument("--db-url", help="Database URL for Optuna storage")
    parser.add_argument("--db-host", help="Database hostname")
    parser.add_argument("--db-port", help="Database port")
    parser.add_argument("--db-name", help="Database name")
    parser.add_argument("--db-user", help="Database username")
    parser.add_argument("--db-password", help="Database password")
    parser.add_argument("--cert-path", help="Path to CA certificate file")
    parser.add_argument("--study", help="Specific study name to monitor (default: monitor all studies)")
    parser.add_argument("--interval", type=int, default=5, help="Check interval in seconds (default: 5)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
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
    
    try:
        if args.study:
            # Monitor a specific study
            study = optuna.load_study(study_name=args.study, storage=db_url)
            monitor = HumanTrialStateMonitor(study, check_interval=args.interval)
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
                monitor = HumanTrialStateMonitor(study, check_interval=args.interval)
                monitor.start()
                monitors.append(monitor)
                logger.info(f"Monitoring study: {study.study_name}")
            
            if monitors:
                logger.info(f"Monitoring {len(monitors)} studies in total")
        
        # Keep the script running
        logger.info("Monitor running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Stopping monitor...")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()