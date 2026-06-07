"""
data_loader.py - Carga y parseo de datos de anuncios inmobiliarios
"""

import pandas as pd
import numpy as np
import io
import re
from typing import Optional
from normalizer import normalize_dataframe


EXPECTED_COLUMNS = [
    'titulo', 'precio', 'metros_cuadrados', 'habitaciones', 'banos',
    'zona', 'direccion', 'portal', 'url', 'descripcion',
    'fecha_publicacion', 'planta', 'ascensor', 'terraza', 'parking', 'estado'
]


def load_csv(file_obj) -> pd.DataFrame:
    """Carga un CSV subido por el usuario."""
    try:
        # Intentar diferentes separadores
        for sep in [',', ';', '\t']:
            try:
                df = pd.read_csv(file_obj, sep=sep, encoding='utf-8')
                if len(df.columns) > 2:
                    break
            except Exception:
                continue
        df = _map_columns(df)
        return normalize_dataframe(df)
    except Exception as e:
        raise ValueError(f"Error cargando CSV: {e}")


def load_csv_path(path: str) -> pd.DataFrame:
    """Carga un CSV desde una ruta local."""
    try:
        for sep in [',', ';', '\t']:
            try:
                df = pd.read_csv(path, sep=sep, encoding='utf-8')
                if len(df.columns) > 2:
                    break
            except Exception:
                continue
        df = _map_columns(df)
        return normalize_dataframe(df)
    except Exception as e:
        raise ValueError(f"Error cargando CSV desde ruta: {e}")


def load_pasted_table(text: str) -> pd.DataFrame:
    """Parsea una tabla pegada manualmente (tab-separated o CSV)."""
    try:
        text = text.strip()
        for sep in ['\t', ',', ';', '|']:
            try:
                df = pd.read_csv(io.StringIO(text), sep=sep)
                if len(df.columns) > 2:
                    break
            except Exception:
                continue
        df = _map_columns(df)
        return normalize_dataframe(df)
    except Exception as e:
        raise ValueError(f"Error parseando tabla pegada: {e}")


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mapea nombres de columnas alternativos al esquema estándar."""
    column_map = {
        # título
        'title': 'titulo', 'name': 'titulo', 'nombre': 'titulo', 'anuncio': 'titulo',
        # precio
        'price': 'precio', 'coste': 'precio', 'cost': 'precio', 'importe': 'precio',
        # metros
        'metros': 'metros_cuadrados', 'm2': 'metros_cuadrados', 'superficie': 'metros_cuadrados',
        'sqm': 'metros_cuadrados', 'area': 'metros_cuadrados',
        # habitaciones
        'rooms': 'habitaciones', 'dormitorios': 'habitaciones', 'bedrooms': 'habitaciones',
        'hab': 'habitaciones', 'habs': 'habitaciones',
        # baños
        'baths': 'banos', 'bathrooms': 'banos', 'bath': 'banos', 'wc': 'banos',
        # zona
        'barrio': 'zona', 'district': 'zona', 'neighborhood': 'zona', 'location': 'zona',
        # portal
        'source': 'portal', 'fuente': 'portal', 'web': 'portal',
        # descripcion
        'description': 'descripcion', 'desc': 'descripcion', 'text': 'descripcion',
        # fecha
        'date': 'fecha_publicacion', 'fecha': 'fecha_publicacion', 'publicado': 'fecha_publicacion',
        # estado
        'condition': 'estado', 'condicion': 'estado',
    }
    df = df.copy()
    df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
    return df


def load_manual_urls(urls_text: str) -> pd.DataFrame:
    """
    Crea registros básicos a partir de URLs pegadas (una por línea).
    NO hace scraping; sólo registra las URLs para revisión manual.
    """
    urls = [u.strip() for u in urls_text.strip().split('\n') if u.strip()]
    records = []
    for url in urls:
        portal = _detect_portal(url)
        records.append({
            'titulo': f"Anuncio de {portal}",
            'url': url,
            'portal': portal,
            'precio': None,
            'metros_cuadrados': None,
            'habitaciones': None,
            'zona': '',
            'estado': 'desconocido',
            'descripcion': 'Introducido manualmente. Completa los datos.',
        })
    if not records:
        raise ValueError("No se encontraron URLs válidas")
    df = pd.DataFrame(records)
    return normalize_dataframe(df)


def _detect_portal(url: str) -> str:
    """Detecta el portal inmobiliario desde la URL."""
    url_lower = url.lower()
    if 'idealista' in url_lower:
        return 'Idealista'
    if 'fotocasa' in url_lower:
        return 'Fotocasa'
    if 'habitaclia' in url_lower:
        return 'Habitaclia'
    if 'pisos.com' in url_lower:
        return 'Pisos.com'
    if 'inmobiliaria' in url_lower:
        return 'Inmobiliaria'
    return 'Otro'


def create_empty_template() -> pd.DataFrame:
    """Crea un DataFrame vacío con las columnas esperadas."""
    return pd.DataFrame(columns=EXPECTED_COLUMNS)


def get_csv_template() -> str:
    """Devuelve el template CSV como string."""
    template_row = {
        'titulo': 'Piso de ejemplo',
        'precio': 300000,
        'metros_cuadrados': 80,
        'habitaciones': 3,
        'banos': 2,
        'zona': 'Eixample',
        'direccion': 'Carrer de Balmes 100',
        'portal': 'Idealista',
        'url': 'https://www.idealista.com/inmueble/XXXXX/',
        'descripcion': 'Descripción del inmueble...',
        'fecha_publicacion': '2024-01-15',
        'planta': 3,
        'ascensor': 'si',
        'terraza': 'no',
        'parking': 'no',
        'estado': 'buen estado',
    }
    df = pd.DataFrame([template_row])
    return df.to_csv(index=False)
