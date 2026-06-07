"""
exporter.py - Exportación de datos en CSV, Excel y PDF
"""

import pandas as pd
import numpy as np
import io
import os
from datetime import datetime
from typing import Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


EXPORT_DIR = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(EXPORT_DIR, exist_ok=True)


def _clean_df_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia el DataFrame para exportación (quita listas/dicts)."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(
                lambda x: ', '.join(x) if isinstance(x, list)
                else str(x) if isinstance(x, dict)
                else x
            )
    return df


def export_csv(df: pd.DataFrame) -> bytes:
    """Exporta como CSV en memoria."""
    df_clean = _clean_df_for_export(df)
    cols = [c for c in [
        'id', 'titulo', 'precio', 'metros_cuadrados', 'precio_m2',
        'habitaciones', 'banos', 'zona', 'portal', 'estado',
        'score', 'decision', 'motivos_str', 'alertas_str', 'url',
        'descripcion', 'fecha_publicacion'
    ] if c in df_clean.columns]
    return df_clean[cols].to_csv(index=False).encode('utf-8')


def export_excel(df: pd.DataFrame) -> bytes:
    """Exporta como Excel con múltiples pestañas."""
    output = io.BytesIO()
    df_clean = _clean_df_for_export(df)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Pestaña 1: Todos los anuncios
        cols_anuncios = [c for c in [
            'id', 'titulo', 'precio', 'metros_cuadrados', 'precio_m2',
            'habitaciones', 'banos', 'zona', 'portal', 'estado',
            'ascensor', 'terraza', 'parking', 'planta', 'url',
            'descripcion', 'fecha_publicacion', 'datos_completos'
        ] if c in df_clean.columns]
        df_clean[cols_anuncios].to_excel(writer, sheet_name='Anuncios', index=False)

        # Pestaña 2: Ranking oportunidades
        cols_ranking = [c for c in [
            'id', 'titulo', 'score', 'decision', 'precio', 'precio_m2',
            'metros_cuadrados', 'zona', 'motivos_str', 'alertas_str', 'url'
        ] if c in df_clean.columns]
        ranking = df_clean.sort_values('score', ascending=False) if 'score' in df_clean.columns else df_clean
        ranking[cols_ranking].to_excel(writer, sheet_name='Ranking Oportunidades', index=False)

        # Pestaña 3: Análisis por zonas
        if 'zona' in df_clean.columns and 'precio_m2' in df_clean.columns:
            zone_stats = df_clean.groupby('zona').agg(
                precio_m2_medio=('precio_m2', 'mean'),
                precio_m2_mediano=('precio_m2', 'median'),
                precio_medio=('precio', 'mean'),
                num_anuncios=('id', 'count'),
                score_medio=('score', 'mean') if 'score' in df_clean.columns else ('id', 'count'),
            ).reset_index()
            zone_stats = zone_stats.round(2)
            zone_stats.to_excel(writer, sheet_name='Análisis por Zonas', index=False)

        # Pestaña 4: Alertas
        if 'alertas_str' in df_clean.columns:
            alertas_df = df_clean[df_clean['alertas_str'].notna() & (df_clean['alertas_str'] != '')].copy()
            cols_alertas = [c for c in [
                'id', 'titulo', 'zona', 'precio', 'score', 'alertas_str', 'decision', 'url'
            ] if c in alertas_df.columns]
            alertas_df[cols_alertas].to_excel(writer, sheet_name='Alertas', index=False)

    return output.getvalue()


def export_pdf_summary(df: pd.DataFrame) -> Optional[bytes]:
    """Exporta un resumen ejecutivo en PDF."""
    if not REPORTLAB_AVAILABLE:
        return None

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    story.append(Paragraph("Analizador Inmobiliario — Resumen Ejecutivo", title_style))
    story.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1a237e')))
    story.append(Spacer(1, 0.5*cm))

    # Resumen global
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], textColor=colors.HexColor('#283593'))
    story.append(Paragraph("Resumen del mercado analizado", h2_style))

    total = len(df)
    precio_medio = df['precio'].mean() if 'precio' in df.columns else 0
    precio_m2_medio = df['precio_m2'].mean() if 'precio_m2' in df.columns else 0

    summary_data = [
        ['Total anuncios', str(total)],
        ['Precio medio', f"{precio_medio:,.0f} €" if pd.notna(precio_medio) else '-'],
        ['Precio/m² medio', f"{precio_m2_medio:,.0f} €/m²" if pd.notna(precio_m2_medio) else '-'],
        ['Zonas analizadas', str(df['zona'].nunique()) if 'zona' in df.columns else '-'],
    ]
    if 'decision' in df.columns:
        for d in ['Muy interesante', 'Interesante', 'Revisar', 'Descartar']:
            summary_data.append([d, str(len(df[df['decision'] == d]))])

    t = Table(summary_data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.8*cm))

    # Top oportunidades
    if 'score' in df.columns:
        story.append(Paragraph("Top 10 Oportunidades", h2_style))
        top10 = df.nlargest(10, 'score')
        table_data = [['#', 'Título', 'Zona', 'Precio', '€/m²', 'Score', 'Decisión']]
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            table_data.append([
                str(i),
                str(row.get('titulo', ''))[:40],
                str(row.get('zona', '-')),
                f"{row.get('precio', 0):,.0f} €" if pd.notna(row.get('precio')) else '-',
                f"{row.get('precio_m2', 0):,.0f}" if pd.notna(row.get('precio_m2')) else '-',
                f"{row.get('score', 0):.0f}",
                str(row.get('decision', '-')),
            ])
        t2 = Table(table_data, colWidths=[0.8*cm, 5.5*cm, 3*cm, 2.5*cm, 2*cm, 1.5*cm, 2.5*cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.8*cm))

    # Análisis por zonas
    if 'zona' in df.columns and 'precio_m2' in df.columns:
        story.append(Paragraph("Análisis por Zonas", h2_style))
        zone_stats = df.groupby('zona').agg(
            precio_m2_medio=('precio_m2', 'mean'),
            num=('id', 'count'),
        ).reset_index().sort_values('precio_m2_medio', ascending=False)
        z_data = [['Zona', 'Precio/m² medio', 'Nº anuncios']]
        for _, row in zone_stats.iterrows():
            z_data.append([
                str(row['zona']),
                f"{row['precio_m2_medio']:,.0f} €/m²" if pd.notna(row['precio_m2_medio']) else '-',
                str(int(row['num'])),
            ])
        t3 = Table(z_data, colWidths=[7*cm, 5*cm, 5*cm])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#283593')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t3)

    doc.build(story)
    return output.getvalue()


def save_export(data: bytes, filename: str) -> str:
    """Guarda un export en disco y devuelve la ruta."""
    path = os.path.join(EXPORT_DIR, filename)
    with open(path, 'wb') as f:
        f.write(data)
    return path
