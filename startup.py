"""
startup.py — Run once before Streamlit starts.
Initialises the DB and seeds sites on first deploy.
Works with both SQLite (local) and PostgreSQL (Supabase / Render).
"""
import db

# For SQLite, ensure the data directory exists
if not db._USE_PG:
    db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

db.init_db()

with db.get_conn() as conn:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM sites").fetchone()
    site_count = row["cnt"]

if site_count == 0:
    print("First run — seeding sites…")
    from reset_sites import reset
    reset()
else:
    prop_count = db.get_total_properties()
    db_type = "PostgreSQL" if db._USE_PG else "SQLite"
    print(f"DB ready ({db_type}): {site_count} sites, {prop_count} properties.")
