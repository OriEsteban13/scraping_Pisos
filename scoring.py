"""
scoring.py - Sistema de puntuación de oportunidades inmobiliarias (0-100)
"""

import pandas as pd
import numpy as np
from typing import Optional


ESTADO_SCORES = {
    "reformado": 10,
    "obra nueva": 8,
    "buen estado": 5,
    "a reformar": 2,
    "desconocido": 0,
}

DECISION_THRESHOLDS = {
    "Muy interesante": 70,
    "Interesante": 50,
    "Revisar": 30,
    "Descartar": 0,
}


def get_zone_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadísticas de precio/m² por zona."""
    stats = df.groupby('zona').agg(
        precio_m2_media=('precio_m2', 'mean'),
        precio_m2_mediana=('precio_m2', 'median'),
        precio_m2_std=('precio_m2', 'std'),
        count=('precio_m2', 'count')
    ).reset_index()
    return stats


def score_property(row: pd.Series, zone_stats: pd.DataFrame, user_budget: Optional[float] = None,
                   min_sqm: Optional[float] = None, min_rooms: Optional[int] = None) -> dict:
    """
    Calcula el score de una propiedad (0-100) con motivos y alertas.
    Devuelve dict con score, motivos, alertas.
    """
    score = 0.0
    motivos = []
    alertas = []
    breakdown = {}

    # --- 1. Precio/m² vs media de zona (máx 30 pts) ---
    zone_row = zone_stats[zone_stats['zona'] == row.get('zona', '')] if not zone_stats.empty else pd.DataFrame()
    if not zone_row.empty and pd.notna(row.get('precio_m2')):
        zona_media = zone_row.iloc[0]['precio_m2_media']
        zona_std = zone_row.iloc[0].get('precio_m2_std', zona_media * 0.15)
        if pd.notna(zona_media) and zona_media > 0:
            ratio = row['precio_m2'] / zona_media
            if ratio <= 0.80:
                pts = 30
                motivos.append(f"Precio/m² un {round((1-ratio)*100)}% por debajo de la media de la zona (muy atractivo)")
            elif ratio <= 0.90:
                pts = 22
                motivos.append(f"Precio/m² un {round((1-ratio)*100)}% por debajo de la media de la zona")
            elif ratio <= 1.00:
                pts = 15
                motivos.append("Precio/m² en línea con la media de la zona")
            elif ratio <= 1.10:
                pts = 8
                alertas.append(f"Precio/m² un {round((ratio-1)*100)}% por encima de la media")
            else:
                pts = 0
                alertas.append(f"Precio/m² un {round((ratio-1)*100)}% por encima de la media de la zona (caro)")
            score += pts
            breakdown['precio_m2_zona'] = pts
        else:
            score += 10  # sin referencia, puntuación neutra
            breakdown['precio_m2_zona'] = 10
    elif pd.notna(row.get('precio_m2')):
        score += 10
        breakdown['precio_m2_zona'] = 10
        alertas.append("Sin datos de zona para comparar precio/m²")
    else:
        alertas.append("Sin precio/m² calculable")
        breakdown['precio_m2_zona'] = 0

    # --- 2. Precio vs presupuesto (máx 15 pts) ---
    if user_budget and pd.notna(row.get('precio')):
        ratio_budget = row['precio'] / user_budget
        if ratio_budget <= 0.75:
            pts = 15
            motivos.append(f"Precio muy por debajo del presupuesto ({round((1-ratio_budget)*100)}% de margen)")
        elif ratio_budget <= 0.90:
            pts = 10
            motivos.append(f"Precio cómodo dentro del presupuesto")
        elif ratio_budget <= 1.0:
            pts = 5
        else:
            pts = 0
            alertas.append(f"Precio supera el presupuesto en {round((ratio_budget-1)*100)}%")
        score += pts
        breakdown['presupuesto'] = pts
    else:
        score += 7  # neutro
        breakdown['presupuesto'] = 7

    # --- 3. Metros cuadrados (máx 15 pts) ---
    sqm = row.get('metros_cuadrados')
    if pd.notna(sqm):
        if min_sqm and sqm < min_sqm:
            alertas.append(f"Metros ({sqm}m²) por debajo del mínimo requerido ({min_sqm}m²)")
            pts = 0
        elif sqm >= 120:
            pts = 15
            motivos.append(f"Gran superficie ({sqm}m²)")
        elif sqm >= 90:
            pts = 12
        elif sqm >= 70:
            pts = 9
        elif sqm >= 50:
            pts = 6
        else:
            pts = 3
        score += pts
        breakdown['metros'] = pts
    else:
        alertas.append("Sin metros cuadrados")
        breakdown['metros'] = 0

    # --- 4. Características positivas (máx 15 pts) ---
    feat_pts = 0
    if row.get('kw_terraza') or row.get('terraza') is True:
        feat_pts += 5
        motivos.append("Tiene terraza")
    if row.get('kw_ascensor') or row.get('ascensor') is True:
        feat_pts += 3
        motivos.append("Tiene ascensor")
    if row.get('kw_parking') or row.get('parking') is True:
        feat_pts += 4
        motivos.append("Parking incluido")
    if row.get('kw_exterior'):
        feat_pts += 3
        motivos.append("Piso exterior/luminoso")
    score += min(feat_pts, 15)
    breakdown['caracteristicas'] = min(feat_pts, 15)

    # --- 5. Estado del inmueble (máx 10 pts) ---
    estado = str(row.get('estado', 'desconocido')).lower()
    estado_pts = ESTADO_SCORES.get(estado, 0)
    score += estado_pts
    breakdown['estado'] = estado_pts
    if estado == 'reformado':
        motivos.append("Inmueble reformado, listo para entrar")
    elif estado == 'a reformar':
        alertas.append("Necesita reforma (coste adicional)")
    elif estado == 'obra nueva':
        motivos.append("Obra nueva")

    # --- 6. Potencial de inversión (máx 10 pts) ---
    inv_pts = 0
    if row.get('kw_inversion') or row.get('kw_alquilado'):
        inv_pts += 5
        motivos.append("Potencial de inversión detectado en descripción")
    if pd.notna(row.get('precio_m2')) and not zone_row.empty:
        if not zone_row.empty:
            zona_media = zone_row.iloc[0]['precio_m2_media']
            if pd.notna(zona_media) and row['precio_m2'] < zona_media * 0.85:
                inv_pts += 5
                motivos.append("Excelente precio/m² para inversión")
    score += min(inv_pts, 10)
    breakdown['inversion'] = min(inv_pts, 10)

    # --- 7. Habitaciones (máx 5 pts) ---
    rooms = row.get('habitaciones')
    if pd.notna(rooms):
        if min_rooms and rooms < min_rooms:
            alertas.append(f"Habitaciones ({int(rooms)}) por debajo del mínimo ({min_rooms})")
        pts = min(int(rooms), 5)
        score += pts
        breakdown['habitaciones'] = pts
    else:
        breakdown['habitaciones'] = 0

    # --- 8. Penalizaciones ---
    # Planta alta sin ascensor
    planta = row.get('planta')
    ascensor = row.get('ascensor')
    if pd.notna(planta) and planta is not None:
        if int(planta) >= 4 and ascensor is False:
            score -= 10
            alertas.append("Planta alta sin ascensor (penalización)")
            breakdown['penalty_sin_ascensor'] = -10

    # Datos incompletos
    if not row.get('datos_completos', True):
        score -= 5
        alertas.append(f"Datos incompletos: {row.get('campos_faltantes', '')}")
        breakdown['penalty_datos'] = -5

    # Precio/m² muy alto
    if pd.notna(row.get('precio_m2')) and not zone_row.empty:
        if not zone_row.empty:
            zona_media = zone_row.iloc[0]['precio_m2_media']
            if pd.notna(zona_media) and row['precio_m2'] > zona_media * 1.3:
                score -= 8
                alertas.append("Precio/m² muy superior a la media de la zona")
                breakdown['penalty_precio_alto'] = -8

    # Descripción poco clara
    if not row.get('descripcion') or len(str(row.get('descripcion', ''))) < 30:
        score -= 3
        alertas.append("Descripción muy corta o sin descripción")
        breakdown['penalty_desc'] = -3

    # Clamp 0-100
    score = max(0.0, min(100.0, score))

    # Decisión sugerida
    decision = "Descartar"
    for label, threshold in DECISION_THRESHOLDS.items():
        if score >= threshold:
            decision = label
            break

    return {
        'score': round(score, 1),
        'decision': decision,
        'motivos': motivos,
        'alertas': alertas,
        'breakdown': breakdown,
    }


def score_dataframe(df: pd.DataFrame, user_budget: Optional[float] = None,
                    min_sqm: Optional[float] = None, min_rooms: Optional[int] = None) -> pd.DataFrame:
    """Aplica scoring a todo el DataFrame."""
    df = df.copy()
    zone_stats = get_zone_stats(df)

    scores = df.apply(
        lambda row: score_property(row, zone_stats, user_budget, min_sqm, min_rooms),
        axis=1
    )

    df['score'] = scores.apply(lambda x: x['score'])
    df['decision'] = scores.apply(lambda x: x['decision'])
    df['motivos'] = scores.apply(lambda x: x['motivos'])
    df['alertas'] = scores.apply(lambda x: x['alertas'])
    df['score_breakdown'] = scores.apply(lambda x: x['breakdown'])

    # Motivos y alertas como string para mostrar
    df['motivos_str'] = df['motivos'].apply(lambda x: ' | '.join(x) if x else '')
    df['alertas_str'] = df['alertas'].apply(lambda x: ' | '.join(x) if x else '')

    return df.sort_values('score', ascending=False).reset_index(drop=True)
