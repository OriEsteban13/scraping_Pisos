"""
scraper.py – Andorra real estate scraper.
Primary fetcher: curl_cffi (browser impersonation, bypasses Cloudflare/bot protection).
Fallback: requests.Session.
"""

import re
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import db

logger = logging.getLogger(__name__)

# ─── Fetcher: curl_cffi primary, requests fallback ───────────────────────────

try:
    from curl_cffi import requests as _creq
    _CURL_OK = True
except ImportError:
    _CURL_OK = False
    import requests as _creq  # type: ignore

import requests as _req_fallback

_SESSION = _req_fallback.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


_CLOUDFLARE_SIGNALS = ("Pardon Our Interruption", "Just a moment", "Please Wait")

# Scraper types that route through the configured proxy (to bypass geo-IP blocks)
_PROXY_SITES = {"idealista"}

# Sites with paginated results:
#   "param"  → append &param=N to base URL          (buscocasa)
#   "path"   → append /N/ to base URL path           (pisoscom)
_PAGINATED_SITES = {
    "buscocasa": ("pn",   "param", 10),
    "pisoscom":  ("",     "path",  5),
}


def _get_proxy() -> Optional[str]:
    """Return configured proxy URL from DB, or None if not set/disabled."""
    try:
        enabled = db.get_setting("proxy_enabled", "0")
        if enabled != "1":
            return None
        url = db.get_setting("proxy_url", "").strip()
        return url or None
    except Exception:
        return None


def _fetch(url: str, timeout: int = 25, impersonate: str = "chrome124",
           proxy: Optional[str] = None) -> str:
    """Fetch URL using curl_cffi (stealth) or requests fallback. Raises RuntimeError on failure."""
    last_err = ""

    proxies = {"http": proxy, "https": proxy} if proxy else None

    if _CURL_OK:
        # Try requested impersonation, fall back to chrome116 if Cloudflare-blocked
        for imp in [impersonate] + (["chrome116", "safari17_0"] if impersonate == "chrome124" else []):
            try:
                kwargs = {"impersonate": imp, "timeout": timeout}
                if proxies:
                    kwargs["proxies"] = proxies
                r = _creq.get(url, **kwargs)
                if r.status_code == 200:
                    if not any(sig in r.text for sig in _CLOUDFLARE_SIGNALS):
                        return r.text
                    continue  # try next impersonation
                raise RuntimeError(f"HTTP {r.status_code}")
            except RuntimeError:
                raise
            except Exception as exc:
                last_err = str(exc)
                break

    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True, proxies=proxies)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        raise RuntimeError(last_err or str(exc))


# ─── Field helpers ────────────────────────────────────────────────────────────

def _price(text) -> Optional[float]:
    if not text:
        return None
    t = re.sub(r"[^\d,.]", "", str(text).replace("\xa0", " ").strip())
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t and len(t.split(",")[-1]) > 2:
        t = t.replace(",", "")
    elif "." in t and len(t.split(".")[-1]) > 2:
        t = t.replace(".", "")
    try:
        v = float(t)
        return v if 5_000 < v < 200_000_000 else None
    except (ValueError, TypeError):
        return None


def _sqm(text) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", str(text), re.I)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            return v if 8 < v < 50_000 else None
        except ValueError:
            pass
    return None


def _rooms(text) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\d+", str(text))
    return int(m.group()) if m and 0 < int(m.group()) < 30 else None


def _abs(href: str, base: str) -> str:
    if not href:
        return base
    return href if href.startswith("http") else urljoin(base, href)


# ─── JSON recursive search ────────────────────────────────────────────────────

def _find_list(obj, key: str, depth: int = 0) -> Optional[list]:
    """Recursively find first list value for `key` in nested JSON."""
    if depth > 15:
        return None
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], list):
            return obj[key]
        for v in obj.values():
            result = _find_list(v, key, depth + 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_list(item, key, depth + 1)
            if result is not None:
                return result
    return None


# ─── Fotocasa parser ──────────────────────────────────────────────────────────

def _scrape_fotocasa(html: str, site: Dict) -> List[Dict]:
    """Parse listings from Fotocasa's embedded application/json script tag."""
    soup = BeautifulSoup(html, "lxml")
    listings = None

    for tag in soup.find_all("script"):
        txt = tag.string or ""
        if "realEstates" not in txt or len(txt) < 5000:
            continue
        try:
            data = json.loads(txt)
            listings = _find_list(data, "realEstates")
            if listings:
                break
        except Exception:
            continue

    if not listings:
        logger.warning("Fotocasa: no realEstates JSON found, falling back to heuristic")
        return _scrape_heuristic(html, site)

    props = []
    for p in listings[:80]:
        # Price (string like "1.490.000 €" or int)
        precio = _price(str(p.get("price", "")))
        if not precio:
            continue

        # Address
        addr = p.get("address") or {}
        zona = (
            addr.get("municipality")
            or addr.get("city")
            or addr.get("district")
            or "Andorra"
        )

        # URL
        detail = p.get("detail") or {}
        if isinstance(detail, dict):
            path = detail.get("es-ES") or detail.get("ca-ES") or detail.get("en-GB") or ""
        else:
            path = str(detail)
        url = (
            "https://www.fotocasa.es" + path
            if path and path.startswith("/")
            else path or f"https://www.fotocasa.es/andorra/{hash(str(p))}"
        )

        # Features
        feats = {f["key"]: f["value"] for f in p.get("features") or [] if isinstance(f, dict)}
        surface = feats.get("surface")
        rooms   = feats.get("rooms")
        baths   = feats.get("bathrooms")
        # Parking: value > 0 means present
        has_parking = 1 if feats.get("parking") and int(feats["parking"]) > 0 else None
        # Terraza/jardín/balcón: any positive value = present
        has_terraza = 1 if any(
            feats.get(k) and int(feats[k]) > 0
            for k in ("terrace", "balcony", "private_garden")
            if k in feats
        ) else None

        tipo = (p.get("buildingType") or "piso").lower()
        desc = str(p.get("description") or "")[:500]

        # Publication date — Fotocasa stores as {"timestamp": ms, "diff": N, "unit": "DAYS"}
        fecha = None
        for date_key in ("date", "dateOriginal", "publishDate", "publicationDate", "insertionDate"):
            date_val = p.get(date_key)
            if not date_val:
                continue
            if isinstance(date_val, dict):
                ts_ms = date_val.get("timestamp")
                if ts_ms:
                    try:
                        from datetime import datetime as _dt
                        fecha = str(_dt.utcfromtimestamp(int(ts_ms) / 1000).date())
                        break
                    except Exception:
                        pass
            elif isinstance(date_val, (int, float)) and date_val > 1e9:
                try:
                    from datetime import datetime as _dt
                    ts = date_val / 1000 if date_val > 1e11 else date_val
                    fecha = str(_dt.utcfromtimestamp(ts).date())
                    break
                except Exception:
                    pass
            elif isinstance(date_val, str) and date_val:
                try:
                    from datetime import datetime as _dt
                    fecha = str(_dt.fromisoformat(date_val.replace("Z", "+00:00")).date())
                    break
                except Exception:
                    pass

        props.append({
            "titulo": f"{tipo.capitalize()} en {zona}",
            "precio": precio,
            "metros_cuadrados": float(surface) if surface else None,
            "habitaciones": int(rooms) if rooms else None,
            "banos": int(baths) if baths else None,
            "zona": zona,
            "descripcion": desc or None,
            "portal": "Fotocasa",
            "url": url,
            "tipo_inmueble": tipo,
            "fecha_publicacion": fecha,
            "parking": has_parking,
            "terraza": has_terraza,
            "site_id": site["id"],
            "estado": "desconocido",
        })

    return props


# ─── Idealista parser ─────────────────────────────────────────────────────────

def _scrape_idealista(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("article.item, article[class*='item']")
    if not items:
        return _scrape_heuristic(html, site)

    props = []
    base = "https://www.idealista.com"
    for item in items[:60]:
        title_el = item.select_one(".item-title a, h3.item-title a, h2.item-title a")
        price_el = item.select_one(".item-price, [class*='price']")
        details = item.select(".item-detail")
        loc_el = item.select_one(".item-location")
        img_el = item.select_one("img")

        if not title_el:
            continue
        precio = _price(price_el.get_text() if price_el else "")
        if not precio:
            continue

        zona = loc_el.get_text(strip=True) if loc_el else "Andorra"
        href = _abs(title_el.get("href", ""), base)

        props.append({
            "titulo": title_el.get_text(strip=True),
            "precio": precio,
            "metros_cuadrados": _sqm(details[0].get_text() if details else ""),
            "habitaciones": _rooms(details[1].get_text() if len(details) > 1 else ""),
            "zona": zona,
            "portal": "Idealista",
            "url": href or f"{base}#{hash(title_el.get_text())}",
            "imagen_url": (img_el.get("src") or img_el.get("data-src", "")) if img_el else "",
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Habitaclia parser ────────────────────────────────────────────────────────

def _scrape_habitaclia(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    # article.list-item-container has data-href with direct URL
    items = soup.select("article.list-item-container")
    if not items:
        return _scrape_heuristic(html, site)

    props = []
    for item in items[:60]:
        url = item.get("data-href", "")
        if not url:
            a_el = item.select_one("a[href*=habitaclia]")
            url = a_el.get("href", "") if a_el else ""
        if not url:
            continue

        # Price: element with 'price' in class; strip non-numeric prefix/suffix
        price_el = item.find(class_=re.compile(r"price", re.I))
        if price_el:
            m_p = re.search(r"([\d.]+(?:\.[\d]{3})*)\s*€", price_el.get_text())
            precio = _price(m_p.group(1)) if m_p else None
        else:
            precio = None
        if not precio:
            continue

        # Title
        h_el = item.find(["h2", "h3"])
        titulo = h_el.get_text(strip=True) if h_el else ""

        # Zone / location
        loc_el = item.find(class_=re.compile(r"location|zone|address", re.I))
        zona = loc_el.get_text(strip=True) if loc_el else "Andorra"

        # Extract numbers from full text
        text = item.get_text(" ", strip=True)
        m_sqm = re.search(r"(\d+)\s*m[²2 ]", text)
        metros = float(m_sqm.group(1)) if m_sqm else None
        m_hab = re.search(r"(\d+)\s*habitacion", text, re.I)
        habs = int(m_hab.group(1)) if m_hab else None
        m_ban = re.search(r"(\d+)\s*baño", text, re.I)
        banos = int(m_ban.group(1)) if m_ban else None

        text_low = text.lower()
        has_parking = 1 if any(w in text_low for w in ("parking", "garaje", "garatge", "aparcament")) else None
        has_terraza = 1 if any(w in text_low for w in ("terraza", "terrassa", "jardín", "jardí", "balcón", "balcó")) else None

        # Date — habitaclia often has no date on list; leave None
        time_el = item.find("time")
        fecha = None
        if time_el:
            dt_attr = time_el.get("datetime", "")
            m_date = re.search(r"\d{4}-\d{2}-\d{2}", dt_attr)
            fecha = m_date.group(0) if m_date else None

        props.append({
            "titulo": titulo or f"Inmueble en {zona}",
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": zona[:100],
            "portal": "Habitaclia",
            "url": url.split("?")[0],  # strip tracking params
            "fecha_publicacion": fecha,
            "parking": has_parking,
            "terraza": has_terraza,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Generic heuristic scraper ────────────────────────────────────────────────

_CARD_SELS = [
    "[class*='PropertyCard']", "[class*='property-card']", "[class*='listing-card']",
    "[class*='re-Card']", "[class*='AdCard']", "[class*='inmueble']",
    "[class*='listing-item']", "[class*='property-item']", "[class*='result-item']",
    "article.item", "article.card", "li.listing", "div.property",
    "[class*='listItem']", "[class*='list-item']", "[class*='SearchCard']",
    "[class*='adCard']", "[class*='propertySnippet']",
]
_PRICE_SELS = ["[class*='price']", "[class*='Price']", "[class*='precio']", "[class*='importe']", "[class*='cost']"]
_TITLE_SELS = ["h2 a", "h3 a", "h1 a", "h2", "h3", "[class*='title'] a", "[class*='Title']", "[class*='name'] a"]
_SQM_SELS   = ["[class*='area']", "[class*='surface']", "[class*='sqm']", "[class*='metros']", "[class*='size']", "[class*='m2']"]
_ROOM_SELS  = ["[class*='room']", "[class*='bedroom']", "[class*='hab']", "[class*='dormitor']"]
_ZONE_SELS  = ["[class*='location']", "[class*='zona']", "[class*='address']", "[class*='area']", "[class*='place']"]
_DATE_SELS  = ["time[datetime]", "[class*='date']", "[class*='Date']", "[class*='published']", "[class*='insertion']"]


def _t(el, sels: list) -> str:
    for s in sels:
        f = el.select_one(s)
        if f:
            return f.get_text(" ", strip=True)
    return ""


def _scrape_heuristic(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    base = site["base_url"]

    best: List = []
    for sel in _CARD_SELS:
        candidates = soup.select(sel)
        valid = [c for c in candidates if re.search(r"\d{3}", c.get_text())]
        if len(valid) > len(best):
            best = valid
        if len(best) >= 4:
            break

    if not best:
        return []

    def _fecha(card):
        for sel in _DATE_SELS:
            el = card.select_one(sel)
            if not el:
                continue
            raw = el.get("datetime") or el.get_text(strip=True)
            if not raw or not isinstance(raw, str):
                continue
            # Must look like a date/datetime string, not arbitrary text
            m = re.search(r"\d{4}-\d{2}-\d{2}", raw)
            if not m:
                continue
            return m.group(0)
        return None

    props = []
    for card in best[:60]:
        titulo = _t(card, _TITLE_SELS) or card.get_text(" ", strip=True)[:80]
        precio = _price(_t(card, _PRICE_SELS))
        metros = _sqm(_t(card, _SQM_SELS) or card.get_text())
        habs   = _rooms(_t(card, _ROOM_SELS))
        zona   = _t(card, _ZONE_SELS) or "Andorra"
        a_el   = card.select_one("a[href]")
        href   = _abs(a_el["href"], base) if a_el else f"{base}#{hash(titulo)}"
        img    = card.select_one("img[src]") or card.select_one("img[data-src]")
        imagen = (img.get("src") or img.get("data-src", "")) if img else ""
        fecha  = _fecha(card)

        if not titulo or not precio:
            continue
        props.append({
            "titulo": titulo[:200],
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "zona": zona[:100],
            "portal": site["name"],
            "url": href,
            "imagen_url": imagen,
            "fecha_publicacion": fecha,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


def _scrape_with_selectors(html: str, site: Dict) -> List[Dict]:
    sels = json.loads(site.get("selectors_json") or "{}")
    if not sels or "listings" not in sels:
        return _scrape_heuristic(html, site)

    soup = BeautifulSoup(html, "lxml")
    base = site["base_url"]
    items = soup.select(sels["listings"])
    props = []
    for item in items[:60]:
        def _st(k):
            return (
                item.select_one(sels[k]).get_text(" ", strip=True)
                if sels.get(k) and item.select_one(sels[k])
                else ""
            )
        def _at(k, a):
            el = item.select_one(sels[k]) if sels.get(k) else None
            return el.get(a, "") if el else ""

        titulo = _st("titulo")
        if not titulo:
            continue
        precio = _price(_st("precio"))
        if not precio:
            continue
        props.append({
            "titulo": titulo,
            "precio": precio,
            "metros_cuadrados": _sqm(_st("metros")),
            "habitaciones": _rooms(_st("habitaciones")),
            "zona": _st("zona") or "Andorra",
            "portal": site["name"],
            "url": _abs(_at("titulo", "href") or _at("url", "href"), base),
            "imagen_url": _at("imagen", "src") or _at("imagen", "data-src"),
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Trovit scraper ──────────────────────────────────────────────────────────

def _decode_trovit_url(href: str) -> str:
    """Extract real detail URL from Trovit's thribee tracking redirect."""
    if "thribee.com" not in href and "trovit" not in href:
        return href
    try:
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(href).query)
        detail = qs.get("detailPageUrl", [""])[0]
        if detail:
            return detail
    except Exception:
        pass
    return href


def _trovit_relative_date(text: str) -> Optional[str]:
    """Convert 'Hace X días/semanas/meses' to ISO date string."""
    from datetime import datetime as _dt, timedelta
    text = text.lower()
    patterns = [
        (r"hace\s+(\d+)\+?\s*día", 1),
        (r"hace\s+(\d+)\+?\s*semana", 7),
        (r"hace\s+(\d+)\+?\s*mes", 30),
        (r"hace\s+(\d+)\+?\s*año", 365),
        (r"hace\s+(\d+)\+?\s*hora", 0),
    ]
    for pat, multiplier in patterns:
        m = re.search(pat, text)
        if m:
            n = int(m.group(1))
            delta = timedelta(days=n * multiplier)
            return str((_dt.now() - delta).date())
    if "hoy" in text:
        return str(_dt.now().date())
    if "ayer" in text:
        from datetime import timedelta
        return str((_dt.now() - timedelta(days=1)).date())
    return None


def _scrape_trovit(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article.snippet-listing, article[class*='snippet']")
    if not articles:
        return _scrape_heuristic(html, site)

    props = []
    for art in articles[:60]:
        a_el   = art.select_one("a[href]")
        href   = _decode_trovit_url(a_el.get("href", "") if a_el else "")
        title  = a_el.get("title", "") if a_el else ""
        if not title:
            title = _t(art, ["[class*='title']", "h2", "h3"])
        price_el = art.select_one(".price__actual, .price, [class*='price']")
        precio = _price(price_el.get_text() if price_el else "")
        if not precio:
            continue
        loc_el = art.select_one("[class*='location'], [class*='address'], [class*='area']")
        zona = loc_el.get_text(strip=True) if loc_el else "Andorra"
        text = art.get_text(" ", strip=True)
        metros = _sqm(text)
        habs   = _rooms(text)
        img    = art.select_one("img[src]")
        imagen = img.get("src", "") if img else ""
        fecha  = _trovit_relative_date(text)

        # Bathrooms: "2 baños" pattern
        m_banos = re.search(r"(\d+)\s*bañ", text, re.I)
        banos = int(m_banos.group(1)) if m_banos else None

        text_lower = text.lower()
        has_parking = 1 if any(w in text_lower for w in ("parking", "garaje", "garage", "aparcament")) else None
        has_terraza = 1 if any(w in text_lower for w in ("terraza", "terrassa", "jardín", "jardí", "jardín", "balcón", "balcó")) else None

        props.append({
            "titulo": (title or zona)[:200],
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": zona[:100],
            "portal": "Trovit",
            "url": href or site["base_url"],
            "imagen_url": imagen,
            "fecha_publicacion": fecha,
            "parking": has_parking,
            "terraza": has_terraza,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Nuroa scraper ───────────────────────────────────────────────────────────

def _scrape_nuroa(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    detail_divs = soup.find_all("div", class_="nu_listing_details")
    if not detail_divs:
        return _scrape_jsonld(html, site)

    props = []
    for div in detail_divs[:60]:
        text = div.get_text(" ", strip=True)
        # Price is the first numeric token ending in €
        price_m = re.search(r"([\d.,]+)\s*€", text)
        precio = _price(price_m.group(1)) if price_m else None
        if not precio:
            continue
        metros = _sqm(text)
        habs   = _rooms(text)

        # Find title and URL from parent container
        parent = div.parent
        title_el = parent.find(class_=re.compile("title|name|heading")) if parent else None
        titulo = title_el.get_text(strip=True) if title_el else ""
        link = parent.find("a", href=True) if parent else None
        href = link.get("href", "") if link else ""
        # Resolve relative nuroa URL
        if href and not href.startswith("http"):
            href = "https://www.nuroa.es" + href

        # Zone from title (e.g. "Piso, Andorra la Vella Centro")
        parts = titulo.split(",")
        zona = parts[1].strip() if len(parts) > 1 else "Andorra"

        m_banos = re.search(r"(\d+)\s*baño", text, re.I)
        banos = int(m_banos.group(1)) if m_banos else None
        text_low = text.lower()
        has_parking = 1 if any(w in text_low for w in ("parking", "garaje", "aparcament")) else None
        has_terraza = 1 if any(w in text_low for w in ("terraza", "terrassa", "jardín", "jardí", "balcón", "balcó")) else None

        props.append({
            "titulo": titulo or f"Inmueble en {zona}",
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": zona[:100],
            "portal": "Nuroa",
            "url": href or site["base_url"],
            "parking": has_parking,
            "terraza": has_terraza,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Pisos.ad scraper ────────────────────────────────────────────────────────

def _pisosad_detail_info(url: str) -> dict:
    """Fetch a pisos.ad detail page and extract date, parking, terraza."""
    result = {}
    try:
        html = _fetch(url, timeout=12)
        # Date: DD/MM/YYYY
        m = re.search(r"(\d{2}/\d{2}/\d{4})", html)
        if m:
            d, mo, y = m.group(1).split("/")
            result["fecha_publicacion"] = f"{y}-{mo}-{d}"
        html_low = html.lower()
        # Parking: look for parking mention outside nav/footer
        if re.search(r"aparcament|parking|garatge|garaje", html_low):
            result["parking"] = 1
        # Terraza / jardín / balcó
        if re.search(r"terrassa|terraza|jardí|jardín|balcó|balcón", html_low):
            result["terraza"] = 1
    except Exception:
        pass
    return result


def _scrape_pisosad(html: str, site: Dict) -> List[Dict]:
    """
    Scrapes pisos.ad listing pages.
    Handles pagination: fetches up to MAX_PAGES of /venda?pagina=N.
    Fetches detail page for each new listing to get publication date.
    """
    MAX_PAGES = 8   # 8 × 12 = ~96 listings per run
    base = "https://www.pisos.ad"

    def _parse_page(page_html: str) -> list:
        soup = BeautifulSoup(page_html, "lxml")
        items = [i for i in soup.select(".list-item, .grid-item")
                 if re.search(r"\d{4,}", i.get_text())]
        results = []
        for item in items:
            a_el   = item.select_one("a[href]")
            href   = a_el.get("href", "") if a_el else ""
            if not href:
                continue
            full_url = href if href.startswith("http") else urljoin(base + "/", href.lstrip("/"))

            title_el = item.select_one("h2, h3, [class*='title']")
            titulo   = (title_el.get_text(strip=True) if title_el else
                        (a_el.get("title", "") if a_el else ""))[:200]

            price_el = item.select_one("p.list-item__price, p.grid-item__price, [class*='price']")
            precio   = _price(price_el.get_text() if price_el else "")
            if not precio:
                continue

            sup_el = item.select_one("[class*='superficie']")
            hab_el = item.select_one("[class*='habitaci']")
            ban_el = item.select_one("[class*='banys']")
            metros = _sqm(sup_el.get_text() if sup_el else "")
            habs   = _rooms(hab_el.get_text() if hab_el else "")
            banos  = _rooms(ban_el.get_text() if ban_el else "")

            # Zone from title: "Pis en venda a Encamp" → "Encamp"
            m_zona = re.search(r"\ba\s+([A-ZÀ-Ü][^\d,]{2,30})", titulo)
            zona   = m_zona.group(1).strip() if m_zona else "Andorra"

            results.append({
                "titulo": titulo,
                "precio": precio,
                "metros_cuadrados": metros,
                "habitaciones": habs,
                "banos": banos,
                "zona": zona[:100],
                "portal": "Pisos.ad",
                "url": full_url,
                "site_id": site["id"],
                "estado": "desconocido",
            })
        return results

    # First page (already fetched)
    all_props = _parse_page(html)

    # Paginate
    base_url = site["base_url"].split("?")[0]   # strip any existing query
    for page_n in range(2, MAX_PAGES + 1):
        try:
            page_html = _fetch(f"{base_url}?pagina={page_n}", timeout=15)
            page_props = _parse_page(page_html)
            if not page_props:
                break
            all_props.extend(page_props)
            time.sleep(0.3)
        except Exception:
            break

    # Fetch detail page for each listing to get publication date
    import sqlite3
    try:
        import db as _db
        conn = _db.get_conn()
        existing_urls = {row[0] for row in conn.execute("SELECT url FROM properties").fetchall()}
        conn.close()
    except Exception:
        existing_urls = set()

    for prop in all_props:
        if prop["url"] not in existing_urls:
            detail = _pisosad_detail_info(prop["url"])
            prop.update(detail)
            time.sleep(0.2)

    return all_props


# ─── JSON-LD scraper (Schema.org SearchResultsPage fallback) ─────────────────

def _scrape_jsonld(html: str, site: Dict) -> List[Dict]:
    """Extract listings from Schema.org JSON-LD embedded in page."""
    soup = BeautifulSoup(html, "lxml")
    props = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        about = data.get("about") if isinstance(data, dict) else None
        if not about or not isinstance(about, list):
            continue
        for item in about[:60]:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("description") or "")
            precio = _price(desc)
            if not precio:
                # Try to find price in description text
                m = re.search(r"([\d.]+(?:\.\d{3})*)\s*€", desc)
                if m:
                    precio = _price(m.group(1))
            if not precio:
                continue
            addr = item.get("address") or {}
            zona = (addr.get("addressLocality") or addr.get("addressRegion") or "Andorra").split(",")[0].strip()
            sqm_val = (item.get("floorSize") or {}).get("value")
            rooms_val = item.get("numberOfBedrooms")
            baths_val = item.get("numberOfBathroomsTotal")
            tipo_raw = item.get("@type", "piso")
            tipo = tipo_raw.lower() if tipo_raw else "piso"
            url = item.get("url") or item.get("mainEntityOfPage") or site["base_url"]
            props.append({
                "titulo": f"{tipo.capitalize()} en {zona}",
                "precio": precio,
                "metros_cuadrados": float(sqm_val) if sqm_val else _sqm(desc),
                "habitaciones": int(rooms_val) if rooms_val else None,
                "banos": int(baths_val) if baths_val else None,
                "zona": zona,
                "descripcion": desc[:500] or None,
                "portal": site["name"],
                "url": str(url)[:500] if url else site["base_url"],
                "tipo_inmueble": tipo,
                "site_id": site["id"],
                "estado": "desconocido",
            })
        if props:
            return props
    return _scrape_heuristic(html, site)


# ─── Buscocasa.ad scraper ────────────────────────────────────────────────────

_ANDORRA_ZONES = {
    "andorra-la-vella": "Andorra la Vella", "andorra-vella": "Andorra la Vella",
    "escaldes": "Escaldes-Engordany", "escaldes-engordany": "Escaldes-Engordany",
    "les-escaldes": "Escaldes-Engordany", "encamp": "Encamp",
    "la-massana": "La Massana", "massana": "La Massana",
    "ordino": "Ordino", "canillo": "Canillo",
    "sant-julia": "Sant Julià de Lòria", "sant-julia-de-loria": "Sant Julià de Lòria",
}


def _buscocasa_zone(url: str, titulo: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1].lower()
    for key, name in _ANDORRA_ZONES.items():
        if key in slug or key in titulo.lower():
            return name
    # Fallback: extract "a {Place}" from title
    m = re.search(r"\ba\s+([A-ZÀ-Üa-zà-ü][^\d,\n]{2,25})", titulo)
    if m:
        return m.group(1).strip().title()
    return "Andorra"


def _scrape_buscocasa(html: str, site: Dict) -> List[Dict]:
    """Parse buscocasa.ad listings. Cards are wrapped in <a> > div.my-container > div.uk-panel-box."""
    soup = BeautifulSoup(html, "lxml")
    panels = soup.select("div.uk-panel.uk-panel-box")
    if not panels:
        return _scrape_heuristic(html, site)

    base = "https://www.buscocasa.ad"
    props = []
    for panel in panels[:60]:
        # URL: the <a> tag is great-grandparent of the panel
        container = panel.parent  # div.my-container
        a_tag = container.parent if container else None
        if a_tag and a_tag.name != "a":
            a_tag = None
        href = a_tag.get("href", "") if a_tag else ""
        url = _abs(href, base)

        # Skip Spanish listings (slug ends with "-espanya")
        if "espanya" in href.lower():
            continue

        # Price: inside the photo overlay
        overlay = panel.select_one(".box-overlay .uk-float-right")
        precio = _price(overlay.get_text(strip=True) if overlay else "")
        if not precio:
            continue

        # Title
        h_el = panel.select_one(".box-titol h2")
        titulo = h_el.get_text(strip=True) if h_el else ""

        # Meta line: "Venda 74 m2 - 2 hab." → sqm + rooms
        em_el = panel.select_one("p.uk-text-small em")
        meta = em_el.get_text(" ", strip=True) if em_el else ""
        metros = _sqm(meta)
        habs = None
        m_hab = re.search(r"(\d+)\s*hab", meta, re.I)
        if m_hab:
            habs = int(m_hab.group(1))

        # Full description text for banos / parking / terraza
        desc_el = panel.select_one("p.uk-text-small")
        text = desc_el.get_text(" ", strip=True) if desc_el else ""
        m_ban = re.search(r"(\d+)\s*banys?|(\d+)\s*baños?", text, re.I)
        banos = int((m_ban.group(1) or m_ban.group(2))) if m_ban else None
        text_low = text.lower()
        has_parking = 1 if any(w in text_low for w in ("parking", "aparcament", "garatge", "garaje")) else None
        has_terraza = 1 if any(w in text_low for w in ("terrassa", "terraza", "jardí", "jardín", "balcó", "balcón")) else None

        # Date: ".box-footer .uk-float-right" text is "DD/MM/YYYYNNN VISITES"
        footer_right = panel.select_one(".box-footer .uk-float-right")
        fecha = None
        if footer_right:
            date_text = footer_right.get_text(strip=True)
            m_date = re.search(r"(\d{2})/(\d{2})/(\d{4})", date_text)
            if m_date:
                fecha = f"{m_date.group(3)}-{m_date.group(2)}-{m_date.group(1)}"

        # Property type from footer
        footer_left = panel.select_one(".box-footer .uk-float-left")
        tipo_raw = footer_left.get_text(strip=True).lower() if footer_left else ""
        if "casa" in tipo_raw or "xalet" in tipo_raw or "terreny" in tipo_raw:
            tipo = "casa"
        elif "local" in tipo_raw or "oficina" in tipo_raw:
            tipo = "local"
        else:
            tipo = "piso"

        zona = _buscocasa_zone(url, titulo)

        props.append({
            "titulo": titulo or f"Inmueble en {zona}",
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": zona,
            "portal": "BuscoCasa.ad",
            "url": url or site["base_url"],
            "fecha_publicacion": fecha,
            "parking": has_parking,
            "terraza": has_terraza,
            "tipo_inmueble": tipo,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Pisos.com scraper ────────────────────────────────────────────────────────

def _scrape_pisoscom(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.ad-preview")
    if not cards:
        return _scrape_heuristic(html, site)

    base = "https://www.pisos.com"
    props = []
    for card in cards:
        a_tag = card.select_one("a[href]")
        href = a_tag["href"] if a_tag else ""
        url = _abs(href, base) if href else ""

        price_el = card.select_one("[class*='price'], [class*='precio']")
        precio = _price(price_el.get_text(strip=True)) if price_el else None
        if not precio:
            continue

        text = card.get_text(" ", strip=True)
        metros = _sqm(text)
        m_hab = re.search(r"(\d+)\s*habs?\.?", text, re.I)
        habs = int(m_hab.group(1)) if m_hab else None
        m_ban = re.search(r"(\d+)\s*baños?\.?", text, re.I)
        banos = int(m_ban.group(1)) if m_ban else None

        text_low = text.lower()
        has_parking = 1 if any(w in text_low for w in ("parking", "garaje", "garagem")) else None
        has_terraza = 1 if any(w in text_low for w in ("terraza", "terrassa", "jardín", "jardí")) else None

        # Location: typically "Nombre zona (municipio)" after title
        loc_el = card.select_one("[class*='location'], [class*='zona'], [class*='locality']")
        zona_raw = loc_el.get_text(strip=True) if loc_el else ""
        if not zona_raw:
            m_loc = re.search(r"\(([^)]{3,30})\)", text)
            zona_raw = m_loc.group(1) if m_loc else ""
        zona = _map_zona(zona_raw) if zona_raw else "Andorra"

        tipo_raw = text_low
        if "casa" in tipo_raw or "chalet" in tipo_raw or "villa" in tipo_raw:
            tipo = "casa"
        elif "local" in tipo_raw or "oficina" in tipo_raw:
            tipo = "local"
        elif "terreno" in tipo_raw or "solar" in tipo_raw:
            tipo = "terreno"
        else:
            tipo = "piso"

        props.append({
            "titulo": (a_tag.get_text(strip=True) if a_tag else "") or f"Piso en {zona}",
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": zona,
            "portal": "Pisos.com",
            "url": url or site["base_url"],
            "parking": has_parking,
            "terraza": has_terraza,
            "tipo_inmueble": tipo,
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


def _map_zona(text: str) -> str:
    """Map a raw location string to a canonical Andorran zone name."""
    t = text.lower()
    mapping = {
        "andorra la vella": "Andorra la Vella",
        "andorra vella": "Andorra la Vella",
        "escaldes": "Escaldes-Engordany",
        "engordany": "Escaldes-Engordany",
        "encamp": "Encamp",
        "massana": "La Massana",
        "la massana": "La Massana",
        "ordino": "Ordino",
        "canillo": "Canillo",
        "sant julià": "Sant Julià de Lòria",
        "sant julia": "Sant Julià de Lòria",
        "san julià": "Sant Julià de Lòria",
    }
    for key, val in mapping.items():
        if key in t:
            return val
    return text.title() if text else "Andorra"


# ─── Immobiliaria.ad scraper ──────────────────────────────────────────────────

def _scrape_immobiliaria_ad(html: str, site: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("ul.flats-listing li")
    if not items:
        return _scrape_heuristic(html, site)

    base = "https://immobiliaria.ad"
    props = []
    for item in items:
        preu_el = item.select_one(".field-preu p, .field-preu")
        price_text = preu_el.get_text(strip=True) if preu_el else ""
        if "venut" in price_text.lower() or "llogat" in price_text.lower():
            continue
        precio = _price(price_text)
        if not precio:
            continue

        interior_el = item.select_one(".field-interior")
        sqm_text = interior_el.get_text(strip=True) if interior_el else ""
        metros = _sqm(sqm_text.replace("M2", "m²").replace("M 2", "m²"))

        hab_el = item.select_one(".field-habitacions")
        habs = None
        if hab_el:
            m = re.search(r"(\d+)", hab_el.get_text(strip=True))
            habs = int(m.group(1)) if m else None

        ban_el = item.select_one(".field-banys")
        banos = None
        if ban_el:
            m = re.search(r"(\d+)", ban_el.get_text(strip=True))
            banos = int(m.group(1)) if m else None

        exterior_el = item.select_one(".field-exterior")
        has_terraza = 1 if exterior_el and re.search(r"\d", exterior_el.get_text()) else None

        planta_el = item.select_one(".field-planta")
        planta_text = planta_el.get_text(strip=True) if planta_el else ""
        m_planta = re.search(r"(\d+)", planta_text)
        planta = int(m_planta.group(1)) if m_planta else None

        title_el = item.select_one(".field-title")
        titulo = title_el.get_text(strip=True) if title_el else ""

        # URL: button link or any a inside item
        a_tag = item.select_one(".button a, a[href^='http']")
        url = a_tag["href"] if a_tag else site["base_url"]

        props.append({
            "titulo": titulo or "Inmueble Immobiliaria.ad",
            "precio": precio,
            "metros_cuadrados": metros,
            "habitaciones": habs,
            "banos": banos,
            "zona": "Andorra",
            "portal": "Immobiliaria.ad",
            "url": url,
            "terraza": has_terraza,
            "planta": planta,
            "tipo_inmueble": "piso",
            "site_id": site["id"],
            "estado": "desconocido",
        })
    return props


# ─── Dispatcher ───────────────────────────────────────────────────────────────

_PARSERS = {
    "fotocasa":         _scrape_fotocasa,
    "idealista":        _scrape_idealista,
    "habitaclia":       _scrape_habitaclia,
    "buscocasa":        _scrape_buscocasa,
    "trovit":           _scrape_trovit,
    "nuroa":            _scrape_nuroa,
    "pisosad":          _scrape_pisosad,
    "pisoscom":         _scrape_pisoscom,
    "immobiliaria_ad":  _scrape_immobiliaria_ad,
    "jsonld":           _scrape_jsonld,
    "generic":          _scrape_heuristic,
}

# Per-scraper browser impersonation overrides (some sites block chrome124)
_IMPERSONATE_MAP = {
    "habitaclia": "chrome116",
}


def scrape_site(site: Dict) -> Tuple[int, int, str]:
    """Scrape one site. Returns (found, new, error_msg)."""
    started = datetime.now().isoformat()
    error_msg = ""
    props: List[Dict] = []

    try:
        scraper_type = site.get("scraper_type", "generic")
        impersonate = _IMPERSONATE_MAP.get(scraper_type, "chrome124")
        proxy = _get_proxy() if scraper_type in _PROXY_SITES else None
        sels = json.loads(site.get("selectors_json") or "{}")
        parser = _PARSERS.get(scraper_type)

        def _parse(html: str) -> List[Dict]:
            if parser:
                return parser(html, site)
            if sels:
                return _scrape_with_selectors(html, site)
            return _scrape_heuristic(html, site)

        base_url = site["base_url"]
        html = _fetch(base_url, impersonate=impersonate, proxy=proxy)
        props = _parse(html)

        # Multi-page support
        if scraper_type in _PAGINATED_SITES and props:
            param, style, max_pages = _PAGINATED_SITES[scraper_type]
            sep = "&" if "?" in base_url else "?"
            seen_urls = {p.get("url") for p in props}
            for page in range(2, max_pages + 1):
                try:
                    if style == "path":
                        page_url = base_url.rstrip("/") + f"/{page}/"
                    else:
                        page_url = f"{base_url}{sep}{param}={page}"
                    page_html = _fetch(page_url, impersonate=impersonate, proxy=proxy)
                    page_props = _parse(page_html)
                    if not page_props:
                        break
                    new_on_page = [p for p in page_props if p.get("url") not in seen_urls]
                    if not new_on_page:
                        break
                    props.extend(new_on_page)
                    seen_urls.update(p.get("url") for p in new_on_page)
                except Exception as page_exc:
                    logger.warning("Page %d error for %s: %s", page, site["name"], page_exc)
                    break

    except Exception as exc:
        error_msg = str(exc)
        logger.warning("Error scraping %s: %s", site["name"], exc)

    new_count = sum(1 for p in props if db.save_property(p))
    finished = datetime.now().isoformat()
    status = "ok" if props else ("error" if error_msg else "vacío")

    db.log_scrape(
        site["id"], site["name"], started, finished,
        status, len(props), new_count, error_msg or None,
    )
    if props:
        db.update_site_stats(site["id"], len(props))

    return len(props), new_count, error_msg


def scrape_all_sites(
    site_ids: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    sites = db.get_enabled_sites()
    if site_ids:
        sites = [s for s in sites if s["id"] in site_ids]

    total_found = total_new = 0
    errors: List[str] = []

    for i, site in enumerate(sites):
        if progress_callback:
            progress_callback(i, len(sites), site["name"])
        found, new_c, err = scrape_site(site)
        total_found += found
        total_new += new_c
        if err:
            errors.append(f"{site['name']}: {err}")
        time.sleep(0.4)

    if progress_callback:
        progress_callback(len(sites), len(sites), "Completado")

    return {
        "sites_scraped": len(sites),
        "total_found": total_found,
        "total_new": total_new,
        "errors": errors,
    }


def test_proxy(proxy_url: str) -> Dict:
    """
    Test a proxy by fetching Idealista through it.
    Returns {"ok": bool, "ip": str, "country": str, "error": str}.
    """
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        # First check what IP the proxy exposes
        r_ip = _req_fallback.get(
            "https://ipinfo.io/json", proxies=proxies, timeout=12,
            headers={"User-Agent": "curl/7.85.0"},
        )
        info = r_ip.json() if r_ip.status_code == 200 else {}
        exposed_ip      = info.get("ip", "?")
        exposed_country = info.get("country", "?")
        exposed_city    = info.get("city", "")

        # Then try Idealista through the proxy
        idealista_ok = False
        if exposed_country in ("ES", "AD"):
            r_id = _req_fallback.get(
                "https://www.idealista.com/venta-viviendas/andorra-provincia/",
                proxies=proxies, timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept-Language": "es-ES,es;q=0.9",
                    "Referer": "https://www.google.es/",
                },
            )
            idealista_ok = r_id.status_code == 200
        return {
            "ok": True,
            "ip": exposed_ip,
            "country": exposed_country,
            "city": exposed_city,
            "idealista": idealista_ok,
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "ip": "", "country": "", "city": "", "idealista": False,
                "error": str(exc)[:200]}
