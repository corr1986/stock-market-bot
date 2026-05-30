"""
Daemon che esegue tracker.py ogni ora, lun-ven dalle 9:00 alle 22:00 ora locale.
Va avviato una volta sola (dal Task Scheduler all'avvio di Windows).
"""

import subprocess
import time
from datetime import datetime
import sys
import os

TRACKER  = os.path.join(os.path.dirname(__file__), "tracker.py")
PYTHON   = sys.executable
LOG      = os.path.join(os.path.dirname(__file__), "daemon.log")
LOCKFILE = os.path.join(os.path.dirname(__file__), "daemon.lock")

START_H = 9
END_H   = 22


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def should_run():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return START_H <= now.hour < END_H


def seconds_to_next_hour():
    now = datetime.now()
    return (60 - now.minute) * 60 - now.second


def run_tracker():
    log("Avvio tracker.py...")
    try:
        result = subprocess.run(
            [PYTHON, "-X", "utf8", TRACKER],
            capture_output=True, text=True, encoding="utf-8"
        )
        for line in result.stdout.strip().splitlines():
            log("  " + line)
        if result.returncode != 0:
            log(f"ERRORE exit code {result.returncode}: {result.stderr[:200]}")
        else:
            log("Tracker completato OK.")
    except Exception as e:
        log(f"Eccezione: {e}")


def main():
    log("Daemon avviato.")
    while True:
        if should_run():
            run_tracker()
            wait = seconds_to_next_hour()
            log(f"Prossima esecuzione tra {wait//60} min.")
            time.sleep(wait)
        else:
            now = datetime.now()
            # Se prima delle 9, aspetta fino alle 9
            if now.hour < START_H:
                wait = (START_H - now.hour) * 3600 - now.minute * 60 - now.second
            else:
                # Dopo le 22 o weekend: aspetta fino alle 9 del prossimo giorno lavorativo
                wait = 60
            time.sleep(wait)


if __name__ == "__main__":
    # Controllo anti-duplicato tramite lock file
    if os.path.exists(LOCKFILE):
        with open(LOCKFILE) as f:
            pid = f.read().strip()
        try:
            import psutil
            if psutil.pid_exists(int(pid)):
                print(f"Daemon già in esecuzione (PID {pid}). Uscita.")
                sys.exit(0)
        except ImportError:
            pass  # psutil non disponibile, procedi senza controllo
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))
    try:
        main()
    except Exception as e:
        log(f"CRASH: {e}")
    finally:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
