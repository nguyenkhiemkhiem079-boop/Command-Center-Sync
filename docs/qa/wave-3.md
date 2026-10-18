# Wave 3 — failover and recovery

Controller suite 21 tests passes, including real owned Windows process stop proof, old checkpoint epoch rejection, lead loss, steering authorization, additive migration and unchanged-defect freeze. Standalone process recovery drill executes real HTTP/coordinator restart and SQLite integrity checks. Actual Windows reboot and Google quota exhaustion are NOT_EXECUTED; quota event is simulated. No arbitrary PID or checkbox can release frozen ownership.
