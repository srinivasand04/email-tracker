"""Entry point for the Windows scheduled task (run with pythonw.exe, so no window opens).

    pythonw.exe -m ingest.run_scheduled

Runs the sync (which classifies new mail afterwards) and appends all output to
logs/sync.log. Two runs never overlap: the task is registered with
MultipleInstances=IgnoreNew, and a lock file guards against manual runs.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from datetime import datetime

from .config import REPO_ROOT

LOG_DIR = REPO_ROOT / "logs"
LOCK = LOG_DIR / "sync.lock"
STALE_LOCK_SECONDS = 6 * 3600


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < STALE_LOCK_SECONDS:
        return 0  # another run is still going
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        with open(LOG_DIR / "sync.log", "a", encoding="utf-8") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            print(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} sync started ===", flush=True)
            from .sync import main as sync_main

            try:
                code = sync_main([])
            except Exception as exc:  # keep the error in the log, not lost in a hidden window
                print(f"Sync crashed: {type(exc).__name__}: {exc}", flush=True)
                code = 1
            print(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} finished with code {code} ===", flush=True)
            return code
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
