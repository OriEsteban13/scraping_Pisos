"""
db.py - SQLite database layer for realestate_analyzer
Tables: properties, sites, scrape_logs
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

import os as _os
_DATA_DIR = _os.environ.get("DATA_DIR", str(Path(__file__).parent / "data"))
DB_PATH = Path(_DATA_DIR) / "realestate.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                precio REAL,
                metros_cuadrados REAL,
                habitaciones INTEGER,
                banos INTEGER,
                zona TEXT,
                direccion TEXT,
                portal TEXT,
                url TEXT,
                descripcion TEXT,
                fecha_publicacion TEXT,
                planta INTEGER,
                ascensor INTEGER,
                terraza INTEGER,
                parking INTEGER,
                estado TEXT DEFAULT 'desconocido',
                imagen_url TEXT,
                tipo_inmueble TEXT DEFAULT 'piso',
                site_id TEXT,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            );

            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                country TEXT DEFAULT 'Andorra',
                site_type TEXT DEFAULT 'agency',
                scraper_type TEXT DEFAULT 'generic',
                selectors_json TEXT DEFAULT '{}',
                notes TEXT,
                last_scraped TEXT,
                properties_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scrape_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT,
                site_name TEXT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                properties_found INTEGER DEFAULT 0,
                properties_new INTEGER DEFAULT 0,
                error_msg TEXT
            );
        """)


def load_sites_from_json(json_path: str):
    """Seed sites table from JSON if empty."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        if count > 0:
            return
        with open(json_path, 'r', encoding='utf-8') as f:
            sites = json.load(f)
        for s in sites:
            conn.execute("""
                INSERT OR IGNORE INTO sites
                (id, name, base_url, enabled, country, site_type, scraper_type, selectors_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s['id'], s['name'], s['base_url'],
                1 if s.get('enabled', True) else 0,
                s.get('country', 'Andorra'),
                s.get('type', 'agency'),
                s.get('scraper_type', 'generic'),
                json.dumps(s.get('selectors', {})),
                s.get('notes', ''),
            ))


# ─── Sites ───────────────────────────────────────────────────────────────────

def get_sites() -> List[Dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM sites ORDER BY name").fetchall()]


def get_enabled_sites() -> List[Dict]:
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute("SELECT * FROM sites WHERE enabled=1 ORDER BY name").fetchall()]


def get_site(site_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
        return dict(row) if row else None


def toggle_site(site_id: str, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE sites SET enabled=? WHERE id=?", (1 if enabled else 0, site_id))


def update_site_stats(site_id: str, count: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sites SET last_scraped=?, properties_count=? WHERE id=?",
            (datetime.now().isoformat(), count, site_id),
        )


def add_site(site: Dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO sites (id, name, base_url, enabled, country, site_type,
                               scraper_type, selectors_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            site['id'], site['name'], site['base_url'],
            1 if site.get('enabled', True) else 0,
            site.get('country', 'Andorra'),
            site.get('site_type', 'agency'),
            site.get('scraper_type', 'generic'),
            json.dumps(site.get('selectors', {})),
            site.get('notes', ''),
        ))


def update_site(site_id: str, fields: Dict):
    allowed = {'name', 'base_url', 'enabled', 'site_type', 'scraper_type', 'selectors_json', 'notes'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ', '.join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(f"UPDATE sites SET {set_clause} WHERE id=?",
                     list(updates.values()) + [site_id])


def delete_site(site_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sites WHERE id=?", (site_id,))


# ─── Properties ──────────────────────────────────────────────────────────────

def save_property(prop: Dict) -> bool:
    """Insert or update a property. Returns True if newly inserted."""
    with get_conn() as conn:
        try:
            conn.execute("""
                INSERT INTO properties
                (titulo, precio, metros_cuadrados, habitaciones, banos, zona, direccion,
                 portal, url, descripcion, fecha_publicacion, planta, ascensor, terraza,
                 parking, estado, imagen_url, tipo_inmueble, site_id, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                prop.get('titulo'), prop.get('precio'), prop.get('metros_cuadrados'),
                prop.get('habitaciones'), prop.get('banos'), prop.get('zona'),
                prop.get('direccion'), prop.get('portal'), prop.get('url'),
                prop.get('descripcion'), prop.get('fecha_publicacion'), prop.get('planta'),
                prop.get('ascensor'), prop.get('terraza'), prop.get('parking'),
                prop.get('estado', 'desconocido'), prop.get('imagen_url'),
                prop.get('tipo_inmueble', 'piso'), prop.get('site_id'),
                datetime.now().isoformat(),
            ))
            return True
        except sqlite3.IntegrityError:
            conn.execute("""
                UPDATE properties SET
                titulo=?, precio=?, metros_cuadrados=?, habitaciones=?, banos=?,
                zona=?, descripcion=?, fecha_publicacion=COALESCE(?, fecha_publicacion), scraped_at=?
                WHERE url=?
            """, (
                prop.get('titulo'), prop.get('precio'), prop.get('metros_cuadrados'),
                prop.get('habitaciones'), prop.get('banos'), prop.get('zona'),
                prop.get('descripcion'), prop.get('fecha_publicacion'),
                datetime.now().isoformat(), prop.get('url'),
            ))
            return False


def get_properties(
    limit: int = 1000,
    site_id: Optional[str] = None,
    zona: Optional[str] = None,
    search: Optional[str] = None,
    portal: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    metros_min: Optional[float] = None,
    metros_max: Optional[float] = None,
    hab_min: Optional[int] = None,
    banos_min: Optional[int] = None,
    tipo: Optional[str] = None,
    sort_by: str = "scraped_at",
    sort_asc: bool = False,
) -> List[Dict]:
    allowed_sort = {"scraped_at", "precio", "metros_cuadrados", "habitaciones", "zona"}
    sort_col = sort_by if sort_by in allowed_sort else "scraped_at"
    direction = "ASC" if sort_asc else "DESC"

    query = "SELECT * FROM properties WHERE 1=1"
    params: List = []
    if site_id:
        query += " AND site_id=?"
        params.append(site_id)
    if zona:
        query += " AND zona LIKE ?"
        params.append(f"%{zona}%")
    if portal:
        query += " AND portal LIKE ?"
        params.append(f"%{portal}%")
    if search:
        query += " AND (titulo LIKE ? OR descripcion LIKE ? OR zona LIKE ?)"
        params += [f"%{search}%"] * 3
    if precio_min is not None:
        query += " AND precio >= ?"
        params.append(precio_min)
    if precio_max is not None:
        query += " AND precio <= ?"
        params.append(precio_max)
    if metros_min is not None:
        query += " AND metros_cuadrados >= ?"
        params.append(metros_min)
    if metros_max is not None:
        query += " AND metros_cuadrados <= ?"
        params.append(metros_max)
    if hab_min is not None and hab_min > 0:
        query += " AND habitaciones >= ?"
        params.append(hab_min)
    if banos_min is not None and banos_min > 0:
        query += " AND banos >= ?"
        params.append(banos_min)
    if tipo:
        query += " AND tipo_inmueble LIKE ?"
        params.append(f"%{tipo}%")
    query += f" ORDER BY {sort_col} {direction} LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_total_properties() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]


def get_properties_today() -> int:
    today = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM properties WHERE scraped_at LIKE ?",
            (f"{today}%",),
        ).fetchone()[0]


def get_daily_counts(days: int = 30) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DATE(scraped_at) as day, COUNT(*) as count
            FROM properties
            WHERE scraped_at >= DATE('now', ?)
            GROUP BY DATE(scraped_at)
            ORDER BY day
        """, (f'-{days} days',)).fetchall()
        return [dict(r) for r in rows]


def get_zone_distribution() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT zona, COUNT(*) as count,
                   ROUND(AVG(precio), 0) as avg_precio,
                   ROUND(AVG(metros_cuadrados), 1) as avg_sqm
            FROM properties
            WHERE zona IS NOT NULL AND zona != ''
            GROUP BY zona ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_portal_distribution() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT portal, COUNT(*) as count
            FROM properties WHERE portal IS NOT NULL AND portal != ''
            GROUP BY portal ORDER BY count DESC LIMIT 15
        """).fetchall()
        return [dict(r) for r in rows]


def get_avg_price() -> Optional[float]:
    with get_conn() as conn:
        val = conn.execute("SELECT AVG(precio) FROM properties WHERE precio > 0").fetchone()[0]
        return round(val, 0) if val else None


def get_price_stats() -> Dict:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                AVG(precio) as avg_precio,
                MIN(precio) as min_precio,
                MAX(precio) as max_precio,
                AVG(metros_cuadrados) as avg_sqm,
                AVG(CASE WHEN metros_cuadrados > 0 THEN precio/metros_cuadrados END) as avg_price_sqm
            FROM properties WHERE precio > 0
        """).fetchone()
        return dict(row) if row else {}


def get_rooms_distribution() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT habitaciones, COUNT(*) as count,
                   ROUND(AVG(precio), 0) as avg_precio,
                   ROUND(AVG(metros_cuadrados), 1) as avg_sqm,
                   ROUND(AVG(CASE WHEN metros_cuadrados > 0 THEN precio/metros_cuadrados END), 0) as avg_pm2
            FROM properties
            WHERE habitaciones IS NOT NULL AND habitaciones > 0 AND precio > 0
            GROUP BY habitaciones ORDER BY habitaciones
        """).fetchall()
        return [dict(r) for r in rows]


def get_tipo_distribution() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT tipo_inmueble, COUNT(*) as count,
                   ROUND(AVG(precio), 0) as avg_precio
            FROM properties
            WHERE tipo_inmueble IS NOT NULL AND tipo_inmueble != ''
            GROUP BY tipo_inmueble ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_price_sqm_by_zone() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT zona,
                   COUNT(*) as count,
                   ROUND(AVG(precio), 0) as avg_precio,
                   ROUND(AVG(CASE WHEN metros_cuadrados > 0 THEN precio/metros_cuadrados END), 0) as avg_pm2,
                   ROUND(MIN(precio), 0) as min_precio,
                   ROUND(MAX(precio), 0) as max_precio
            FROM properties
            WHERE zona IS NOT NULL AND zona != '' AND precio > 0
            GROUP BY zona HAVING count >= 1 ORDER BY avg_precio DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ─── Logs ─────────────────────────────────────────────────────────────────────

def log_scrape(site_id: str, site_name: str, started_at: str, finished_at: str,
               status: str, found: int, new_count: int, error: Optional[str] = None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO scrape_logs
            (site_id, site_name, started_at, finished_at, status,
             properties_found, properties_new, error_msg)
            VALUES (?,?,?,?,?,?,?,?)
        """, (site_id, site_name, started_at, finished_at, status, found, new_count, error))


def get_recent_logs(limit: int = 100) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Settings ─────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, value, datetime.now().isoformat()))
