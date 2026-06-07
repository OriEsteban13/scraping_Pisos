"""
analytics.py - Análisis de mercado y generación de gráficos
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def compute_zone_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Estadísticas por zona."""
    if df.empty:
        return pd.DataFrame()
    stats = df.groupby('zona').agg(
        precio_medio=('precio', 'mean'),
        precio_mediano=('precio', 'median'),
        precio_m2_medio=('precio_m2', 'mean'),
        precio_m2_mediano=('precio_m2', 'median'),
        metros_medios=('metros_cuadrados', 'mean'),
        num_anuncios=('id', 'count'),
        score_medio=('score', 'mean'),
    ).reset_index()
    stats = stats.sort_values('precio_m2_medio', ascending=False)
    return stats


def plot_precio_m2_por_zona(df: pd.DataFrame) -> go.Figure:
    """Gráfico de barras: precio/m² por zona."""
    stats = compute_zone_stats(df)
    if stats.empty:
        return go.Figure()
    fig = px.bar(
        stats.sort_values('precio_m2_medio', ascending=True),
        x='precio_m2_medio',
        y='zona',
        orientation='h',
        color='precio_m2_medio',
        color_continuous_scale='RdYlGn_r',
        text=stats.sort_values('precio_m2_medio', ascending=True)['precio_m2_medio'].apply(
            lambda x: f"{x:,.0f} €/m²" if pd.notna(x) else "-"
        ),
        title='Precio medio por m² según zona',
        labels={'precio_m2_medio': 'Precio/m² (€)', 'zona': 'Zona'},
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        height=max(350, len(stats) * 45),
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
    )
    return fig


def plot_distribucion_precios(df: pd.DataFrame) -> go.Figure:
    """Histograma de distribución de precios."""
    datos = df['precio'].dropna()
    if datos.empty:
        return go.Figure()
    fig = px.histogram(
        df[df['precio'].notna()],
        x='precio',
        nbins=20,
        color='zona',
        title='Distribución de precios',
        labels={'precio': 'Precio (€)', 'count': 'Nº anuncios'},
        opacity=0.8,
    )
    fig.update_layout(
        barmode='overlay',
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def plot_precio_vs_metros(df: pd.DataFrame) -> go.Figure:
    """Scatter: precio vs metros cuadrados, coloreado por zona."""
    sub = df[df['precio'].notna() & df['metros_cuadrados'].notna()].copy()
    if sub.empty:
        return go.Figure()
    fig = px.scatter(
        sub,
        x='metros_cuadrados',
        y='precio',
        color='zona',
        size='score',
        hover_name='titulo',
        hover_data={'precio_m2': ':.0f', 'zona': True, 'score': True},
        title='Precio vs Metros cuadrados',
        labels={'metros_cuadrados': 'Metros cuadrados (m²)', 'precio': 'Precio (€)'},
        size_max=30,
    )
    fig.update_layout(
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def plot_score_ranking(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Ranking de inmuebles por score."""
    sub = df.nlargest(top_n, 'score')[['titulo', 'score', 'zona', 'decision']].copy()
    if sub.empty:
        return go.Figure()
    color_map = {
        'Muy interesante': '#00ff88',
        'Interesante': '#88ff00',
        'Revisar': '#ffaa00',
        'Descartar': '#ff4444',
    }
    sub['color'] = sub['decision'].map(color_map).fillna('#888888')
    fig = go.Figure(go.Bar(
        x=sub['score'],
        y=sub['titulo'].apply(lambda t: t[:40] + '...' if len(str(t)) > 40 else t),
        orientation='h',
        marker_color=sub['color'],
        text=sub['score'].apply(lambda s: f"{s:.0f}"),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Score: %{x}<extra></extra>',
    ))
    fig.update_layout(
        title=f'Top {top_n} oportunidades por score',
        xaxis_title='Score (0-100)',
        height=max(300, len(sub) * 40),
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def plot_evolucion_temporal(df: pd.DataFrame) -> go.Figure:
    """Evolución de precio/m² en el tiempo si hay fechas."""
    sub = df[df['fecha_publicacion'].notna() & df['precio_m2'].notna()].copy()
    if sub.empty or len(sub) < 3:
        return go.Figure()
    sub['mes'] = sub['fecha_publicacion'].dt.to_period('M').astype(str)
    monthly = sub.groupby(['mes', 'zona'])['precio_m2'].mean().reset_index()
    fig = px.line(
        monthly,
        x='mes',
        y='precio_m2',
        color='zona',
        title='Evolución del precio/m² por zona',
        labels={'mes': 'Mes', 'precio_m2': 'Precio/m² (€)', 'zona': 'Zona'},
        markers=True,
    )
    fig.update_layout(
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def plot_comparativa_zonas(df: pd.DataFrame) -> go.Figure:
    """Box plot de precio/m² por zona."""
    sub = df[df['precio_m2'].notna() & df['zona'].notna()]
    if sub.empty:
        return go.Figure()
    fig = px.box(
        sub,
        x='zona',
        y='precio_m2',
        color='zona',
        title='Distribución de precio/m² por zona',
        labels={'precio_m2': 'Precio/m² (€)', 'zona': 'Zona'},
        points='all',
    )
    fig.update_layout(
        showlegend=False,
        plot_bgcolor='#0f0f23',
        paper_bgcolor='#0f0f23',
        font_color='#e0e0e0',
        xaxis_tickangle=-30,
        margin=dict(l=10, r=10, t=50, b=60),
    )
    return fig


def plot_score_gauge(score: float) -> go.Figure:
    """Gauge circular para el score de un inmueble."""
    if score >= 70:
        color = "#00ff88"
    elif score >= 50:
        color = "#88ff00"
    elif score >= 30:
        color = "#ffaa00"
    else:
        color = "#ff4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Score de oportunidad", 'font': {'color': '#e0e0e0', 'size': 16}},
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': '#e0e0e0'},
            'bar': {'color': color},
            'bgcolor': '#1a1a3e',
            'borderwidth': 2,
            'bordercolor': '#333',
            'steps': [
                {'range': [0, 30], 'color': '#2a0a0a'},
                {'range': [30, 50], 'color': '#2a1a0a'},
                {'range': [50, 70], 'color': '#1a2a0a'},
                {'range': [70, 100], 'color': '#0a2a1a'},
            ],
        },
        number={'font': {'color': color, 'size': 40}},
    ))
    fig.update_layout(
        height=250,
        paper_bgcolor='#0f0f23',
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def get_market_summary(df: pd.DataFrame) -> dict:
    """Resumen ejecutivo del mercado."""
    if df.empty:
        return {}
    return {
        'total_anuncios': len(df),
        'precio_medio': df['precio'].mean(),
        'precio_m2_medio': df['precio_m2'].mean(),
        'metros_medios': df['metros_cuadrados'].mean(),
        'score_medio': df['score'].mean() if 'score' in df.columns else 0,
        'muy_interesante': len(df[df.get('decision', pd.Series()) == 'Muy interesante']) if 'decision' in df.columns else 0,
        'interesante': len(df[df.get('decision', pd.Series()) == 'Interesante']) if 'decision' in df.columns else 0,
        'revisar': len(df[df.get('decision', pd.Series()) == 'Revisar']) if 'decision' in df.columns else 0,
        'descartar': len(df[df.get('decision', pd.Series()) == 'Descartar']) if 'decision' in df.columns else 0,
        'zonas': df['zona'].nunique(),
        'portales': df['portal'].nunique() if 'portal' in df.columns else 0,
    }
