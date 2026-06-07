"""
Reset sites table to only include real, verified domains.
Run once: python reset_sites.py
Works with both SQLite (local) and PostgreSQL (Supabase).
"""
import db

REAL_SITES = [
    # ── Major portals with dedicated scrapers ─────────────────────────────
    {
        "id": "fotocasa-andorra",
        "name": "Fotocasa Andorra",
        "base_url": "https://www.fotocasa.es/es/comprar/viviendas/andorra/todas-las-zonas/l",
        "scraper_type": "fotocasa",
        "notes": "Portal principal. curl_cffi impersonation.",
    },
    {
        "id": "idealista-andorra",
        "name": "Idealista Andorra",
        "base_url": "https://www.idealista.com/venta-viviendas/andorra-pais/",
        "scraper_type": "idealista",
        "notes": "Principal portal español.",
    },
    {
        "id": "habitaclia-andorra",
        "name": "Habitaclia Andorra",
        "base_url": "https://www.habitaclia.com/comprar-en-andorra.htm",
        "scraper_type": "habitaclia",
        "notes": "Portal catalán con listings de Andorra.",
    },
    {
        "id": "buscocasa-andorra",
        "name": "BuscoCasa Andorra",
        "base_url": "https://www.buscocasa.ad/es/comprar/",
        "scraper_type": "buscocasa",
        "notes": "Portal local .ad con inmuebles de Andorra.",
    },
    # ── International portals ─────────────────────────────────────────────
    {
        "id": "kyero-andorra",
        "name": "Kyero Andorra",
        "base_url": "https://www.kyero.com/en/andorra/property-for-sale",
        "scraper_type": "generic",
    },
    {
        "id": "spainhouses-andorra",
        "name": "SpainHouses Andorra",
        "base_url": "https://www.spainhouses.net/en/buy-property-andorra.html",
        "scraper_type": "generic",
    },
    {
        "id": "nuroa-andorra",
        "name": "Nuroa Andorra",
        "base_url": "https://www.nuroa.es/comprar/andorra/",
        "scraper_type": "generic",
    },
    {
        "id": "immovisor-andorra",
        "name": "Immovisor Andorra",
        "base_url": "https://www.immovisor.com/andorra/",
        "scraper_type": "generic",
    },
    {
        "id": "trovit-andorra",
        "name": "Trovit Andorra",
        "base_url": "https://casas.trovit.es/index.php/cod.search_homes/what.andorra/",
        "scraper_type": "generic",
    },
    {
        "id": "pisos-andorra",
        "name": "Pisos.com Andorra",
        "base_url": "https://www.pisos.com/comprar/pisos-andorra/",
        "scraper_type": "generic",
    },
    {
        "id": "milanuncios-andorra",
        "name": "Milanuncios Andorra",
        "base_url": "https://www.milanuncios.com/inmobiliaria-en-andorra/",
        "scraper_type": "generic",
    },
    # ── Luxury / international agencies ──────────────────────────────────
    {
        "id": "engelvoelkers-andorra",
        "name": "Engel & Völkers Andorra",
        "base_url": "https://www.engelvoelkers.com/en/andorra/properties/buy/",
        "scraper_type": "generic",
    },
    {
        "id": "knightfrank-andorra",
        "name": "Knight Frank Andorra",
        "base_url": "https://www.knightfrank.com/properties/residential/for-sale/andorra",
        "scraper_type": "generic",
    },
    {
        "id": "savills-andorra",
        "name": "Savills Andorra",
        "base_url": "https://www.savills.com/buy-property/andorra.aspx",
        "scraper_type": "generic",
    },
    {
        "id": "sothebys-andorra",
        "name": "Sotheby's Andorra",
        "base_url": "https://www.sothebysrealty.com/eng/sales/andorra",
        "scraper_type": "generic",
    },
    {
        "id": "barnes-andorra",
        "name": "Barnes Andorra",
        "base_url": "https://www.barnes-international.com/real-estate/andorra/",
        "scraper_type": "generic",
    },
    # ── Local Andorran sites ──────────────────────────────────────────────
    {
        "id": "immobiliaria-ad",
        "name": "Immobiliaria.ad",
        "base_url": "https://www.immobiliaria.ad/venda",
        "scraper_type": "generic",
        "notes": "Portal local andorrà .ad",
    },
    {
        "id": "creditandorra-immo",
        "name": "Crèdit Andorrà Immo",
        "base_url": "https://creditandorra.ad/ca/serveis/immobiliaria",
        "scraper_type": "generic",
        "notes": "Servei immobiliari del Crèdit Andorrà",
    },
]


def reset():
    db.init_db()
    # Clear all existing sites
    with db.get_conn() as conn:
        conn.execute("DELETE FROM sites")
    print("Cleared sites table.")

    for s in REAL_SITES:
        db.upsert_site({
            "id":           s["id"],
            "name":         s["name"],
            "base_url":     s["base_url"],
            "enabled":      1,
            "country":      "Andorra",
            "site_type":    "portal",
            "scraper_type": s.get("scraper_type", "generic"),
            "selectors_json": "{}",
            "notes":        s.get("notes", ""),
        })
        print(f"  + {s['name']}")

    print(f"\nDone. {len(REAL_SITES)} real sites loaded.")


if __name__ == "__main__":
    reset()
