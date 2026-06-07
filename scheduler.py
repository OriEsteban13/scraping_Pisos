"""
scheduler.py – Background scraping scheduler for realestate_analyzer.
Runs in a daemon thread; interval/time are read from the DB settings table.
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import db
import scraper

logger = logging.getLogger(__name__)

_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


# ─── Schedule helpers ─────────────────────────────────────────────────────────

INTERVALS = {
    "manual":  None,
    "1":       1,
    "2":       2,
    "3":       3,
    "7":       7,
    "14":      14,
}

INTERVAL_LABELS = {
    "manual": "Solo manual",
    "1":      "Cada día",
    "2":      "Cada 2 días",
    "3":      "Cada 3 días",
    "7":      "Cada semana",
    "14":     "Cada 2 semanas",
}


def get_next_run() -> Optional[datetime]:
    """Return the next scheduled run datetime, or None if manual."""
    interval_key = db.get_setting("schedule_interval", "manual")
    days = INTERVALS.get(interval_key)
    if not days:
        return None

    last_run_str = db.get_setting("schedule_last_run", "")
    if not last_run_str:
        return datetime.now()  # no previous run → run now

    try:
        last_run = datetime.fromisoformat(last_run_str)
    except ValueError:
        return datetime.now()

    return last_run + timedelta(days=days)


def is_due() -> bool:
    """Return True if a scheduled run is due."""
    nxt = get_next_run()
    return nxt is not None and datetime.now() >= nxt


def run_now():
    """Execute scraping for all enabled sites and record the run time."""
    logger.info("Scheduler: running scraping job")
    db.set_setting("schedule_last_run", datetime.now().isoformat())
    db.set_setting("schedule_status", "running")
    try:
        result = scraper.scrape_all_sites()
        db.set_setting("schedule_status", "ok")
        db.set_setting(
            "schedule_last_result",
            f"Sitios: {result['sites_scraped']} | "
            f"Encontrados: {result['total_found']} | "
            f"Nuevos: {result['total_new']}",
        )
    except Exception as exc:
        db.set_setting("schedule_status", "error")
        db.set_setting("schedule_last_result", str(exc)[:200])
        logger.error("Scheduler error: %s", exc)


# ─── Background thread ────────────────────────────────────────────────────────

def _loop():
    while not _stop_event.is_set():
        try:
            if is_due():
                run_now()
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)
        # Check every 5 minutes
        _stop_event.wait(300)


def start():
    """Start the scheduler background thread (idempotent)."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="scrape-scheduler")
    _thread.start()
    logger.info("Scheduler started")


def stop():
    """Signal the background thread to stop."""
    _stop_event.set()
