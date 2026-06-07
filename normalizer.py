"""
normalizer.py - Limpieza y normalización de datos inmobiliarios
"""

import pandas as pd
import numpy as np
import re
from typing import Optional


# Mapa de normalización de zonas/barrios
ZONE_ALIASES = {
    "eixample": ["eixample", "eixample dreta", "eixample esquerra", "l'eixample"],
    "gracia": ["gràcia", "gracia", "vila de gràcia", "camp d'en grassot"],
    "poblenou": ["poblenou", "poble nou", "el poblenou", "@22"],
    "barceloneta": ["barceloneta", "la barceloneta"],
    "sants": ["sants", "sants-montjuïc", "sants montjuic"],
    "les_corts": ["les corts", "les corts"],
    "sarria": ["sarrià", "sarria", "sarrià-sant gervasi", "sant gervasi"],
    "gracia_nova": ["nova gràcia", "gràcia nova"],
    "horta": ["horta", "horta-guinardó", "horta guinardo"],
    "nou_barris": ["nou barris", "nou barris"],
    "sant_andreu": ["sant andreu", "sant andreu de palomar"],
    "sant_marti": ["sant martí", "sant marti"],
    "sant_pere": ["sant pere", "sant pere, santa caterina", "barri gòtic", "barri gotic", "el raval", "raval"],
    "ciudad_vella": ["ciutat vella", "ciudad vieja"],
}


def normalize_zone(zone: str) -> str:
    """Normaliza el nombre de una zona/barrio."""
    if not zone or pd.isna(zone):
        return "Sin zona"
    zone_lower = str(zone).lower().strip()
    for canonical, aliases in ZONE_ALIASES.items():
        for alias in aliases:
            if alias in zone_lower or zone_lower in alias:
                return canonical.replace("_", " ").title()
    return str(zone).strip().title()


def clean_price(price_val) -> Optional[float]:
    """Limpia y convierte precio a float."""
    if price_val is None or (isinstance(price_val, float) and np.isnan(price_val)):
        return None
    price_str = str(price_val)
    price_str = re.sub(r'[€$£\s]', '', price_str)
    price_str = price_str.replace('.', '').replace(',', '.')
    price_str = re.sub(r'[^\d.]', '', price_str)
    try:
        val = float(price_str)
        if val < 1000:  # probablemente en miles
            val *= 1000
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def clean_sqm(sqm_val) -> Optional[float]:
    """Limpia y convierte metros cuadrados a float."""
    if sqm_val is None or (isinstance(sqm_val, float) and np.isnan(sqm_val)):
        return None
    sqm_str = str(sqm_val)
    sqm_str = re.sub(r'[m²\s]', '', sqm_str)
    sqm_str = sqm_str.replace(',', '.')
    sqm_str = re.sub(r'[^\d.]', '', sqm_str)
    try:
        val = float(sqm_str)
        return val if 5 < val < 2000 else None
    except (ValueError, TypeError):
        return None


def clean_boolean(val) -> Optional[bool]:
    """Convierte valores variados a booleano."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, bool):
        return val
    val_str = str(val).lower().strip()
    if val_str in ['si', 'sí', 'yes', 'true', '1', 's', 'y']:
        return True
    if val_str in ['no', 'false', '0', 'n']:
        return False
    return None


def clean_floor(floor_val) -> Optional[int]:
    """Normaliza número de planta."""
    if floor_val is None or (isinstance(floor_val, float) and np.isnan(floor_val)):
        return None
    floor_str = str(floor_val).lower().strip()
    if 'bajo' in floor_str or 'planta baja' in floor_str or floor_str == 'pb':
        return 0
    if 'entresuelo' in floor_str or 'entresol' in floor_str:
        return 0
    if 'sotano' in floor_str or 'sótano' in floor_str:
        return -1
    nums = re.findall(r'\d+', floor_str)
    if nums:
        return int(nums[0])
    return None


def detect_keywords(description: str) -> dict:
    """Detecta palabras clave en la descripción."""
    if not description or pd.isna(description):
        return {}
    desc_lower = str(description).lower()
    keywords = {
        'a_reformar': any(kw in desc_lower for kw in ['a reformar', 'para reformar', 'necesita reforma', 'reformar']),
        'reformado': any(kw in desc_lower for kw in ['reformado', 'reformada', 'totalmente reformado', 'recién reformado']),
        'luminoso': any(kw in desc_lower for kw in ['luminoso', 'luminosa', 'muy luminoso', 'luz natural']),
        'terraza': any(kw in desc_lower for kw in ['terraza', 'terraça']),
        'balcon': any(kw in desc_lower for kw in ['balcón', 'balcon', 'balconada']),
        'ascensor': any(kw in desc_lower for kw in ['ascensor', 'elevador', 'lift']),
        'parking': any(kw in desc_lower for kw in ['parking', 'garaje', 'plaza de garaje', 'plaza garaje']),
        'exterior': any(kw in desc_lower for kw in ['exterior', 'exteriores', 'vistas a la calle']),
        'inversion': any(kw in desc_lower for kw in ['inversión', 'inversion', 'rentabilidad', 'alquilado', 'potencial']),
        'alquilado': any(kw in desc_lower for kw in ['alquilado', 'alquilada', 'con inquilino', 'con arrendatario']),
        'obra_nueva': any(kw in desc_lower for kw in ['obra nueva', 'nueva construcción', 'newly built']),
        'vistas': any(kw in desc_lower for kw in ['vistas', 'vista al mar', 'vista panorámica', 'panorámica']),
    }
    return keywords


def normalize_estado(estado: str) -> str:
    """Normaliza el estado del inmueble."""
    if not estado or pd.isna(estado):
        return "desconocido"
    estado_lower = str(estado).lower().strip()
    if any(kw in estado_lower for kw in ['reforma', 'reformado', 'reformada']):
        if any(kw in estado_lower for kw in ['a reformar', 'para reformar', 'necesita']):
            return "a reformar"
        return "reformado"
    if any(kw in estado_lower for kw in ['obra nueva', 'nuevo', 'nueva construcción']):
        return "obra nueva"
    if any(kw in estado_lower for kw in ['buen estado', 'buenas condiciones', 'bien conservado']):
        return "buen estado"
    if any(kw in estado_lower for kw in ['a reformar', 'para reformar']):
        return "a reformar"
    return estado_lower


def check_completeness(row: pd.Series) -> tuple[bool, list]:
    """Verifica completitud de datos y devuelve (completo, campos_faltantes)."""
    required_fields = ['precio', 'metros_cuadrados', 'habitaciones', 'zona']
    missing = []
    for field in required_fields:
        if field not in row or row[field] is None or (isinstance(row[field], float) and np.isnan(row[field])):
            missing.append(field)
    return len(missing) == 0, missing


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza todo el DataFrame de anuncios."""
    df = df.copy()

    # Columnas esperadas con valores por defecto
    expected_cols = {
        'titulo': '',
        'precio': None,
        'metros_cuadrados': None,
        'habitaciones': None,
        'banos': None,
        'zona': '',
        'direccion': '',
        'portal': 'Otro',
        'url': '',
        'descripcion': '',
        'fecha_publicacion': None,
        'planta': None,
        'ascensor': None,
        'terraza': None,
        'parking': None,
        'estado': 'desconocido',
    }
    for col, default in expected_cols.items():
        if col not in df.columns:
            df[col] = default

    # Limpiar y convertir campos
    df['precio'] = df['precio'].apply(clean_price)
    df['metros_cuadrados'] = df['metros_cuadrados'].apply(clean_sqm)
    df['habitaciones'] = pd.to_numeric(df['habitaciones'], errors='coerce')
    df['banos'] = pd.to_numeric(df['banos'], errors='coerce')
    df['planta'] = df['planta'].apply(clean_floor)
    df['ascensor'] = df['ascensor'].apply(clean_boolean)
    df['terraza'] = df['terraza'].apply(clean_boolean)
    df['parking'] = df['parking'].apply(clean_boolean)
    df['zona'] = df['zona'].apply(normalize_zone)
    df['estado'] = df['estado'].apply(normalize_estado)

    # Calcular precio/m²
    df['precio_m2'] = df.apply(
        lambda r: round(r['precio'] / r['metros_cuadrados'], 2)
        if pd.notna(r['precio']) and pd.notna(r['metros_cuadrados']) and r['metros_cuadrados'] > 0
        else None,
        axis=1
    )

    # Detectar keywords en descripción
    keywords_data = df['descripcion'].apply(detect_keywords)
    keywords_df = pd.DataFrame(list(keywords_data))
    for col in keywords_df.columns:
        df[f'kw_{col}'] = keywords_df[col]

    # Marcar completitud
    completeness = df.apply(check_completeness, axis=1)
    df['datos_completos'] = completeness.apply(lambda x: x[0])
    df['campos_faltantes'] = completeness.apply(lambda x: ', '.join(x[1]) if x[1] else '')

    # Fecha
    if 'fecha_publicacion' in df.columns:
        df['fecha_publicacion'] = pd.to_datetime(df['fecha_publicacion'], errors='coerce')

    # ID único
    df['id'] = range(1, len(df) + 1)

    return df
