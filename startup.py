"""
startup.py — Run once before Streamlit starts.
Initialises the DB and seeds sites on first deploy.
"""
import db
from pathlib import Path

db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db.init_db()

import sqlite3
conn = sqlite3.connect(str(db.DB_PATH))
site_count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
conn.close()

if site_count == 0:
    print("First run — seeding sites…")
    from reset_sites import reset
    reset()
else:
    prop_count = db.get_total_properties()
    print(f"DB ready: {site_count} sites, {prop_count} properties.")
