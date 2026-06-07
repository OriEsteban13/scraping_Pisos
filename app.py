"""
Anàlisi Immobiliària d'Andorra – Streamlit dashboard
"""

import base64
import io
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from streamlit_option_menu import option_menu

import db
import scraper
import scheduler

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Anàlisi Immobiliària d'Andorra",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── DB init + scheduler ─────────────────────────────────────────────────────
SITES_JSON = Path(__file__).parent / "data" / "andorra_sites.json"
db.init_db()
if SITES_JSON.exists():
    db.load_sites_from_json(str(SITES_JSON))
scheduler.start()  # background thread, idempotent

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp { background-color: #0d1117 !important; }
.main .block-container { padding: 1.5rem 2rem 4rem 2rem; max-width: 1400px; }
/* Let dataframes grow to full content height */
[data-testid="stDataFrame"] > div { max-height: none !important; }
[data-testid="stDataFrame"] iframe { min-height: 100px; height: auto !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #111827 !important;
    border-right: 2px solid #2d3748 !important;
    min-width: 240px !important;
    max-width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] { padding: 0 !important; }

/* Sidebar collapse button (inside sidebar – the < arrow) */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebar"] button[data-testid="baseButton-header"] {
    background-color: #1e293b !important;
    border: 1px solid #2d3748 !important;
    border-radius: 6px !important;
    color: #e6edf3 !important;
}
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebar"] button[data-testid="baseButton-header"] svg {
    fill: #e6edf3 !important;
    stroke: #e6edf3 !important;
}

/* Sidebar expand button (the > that shows when sidebar is collapsed) */
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    background-color: #111827 !important;
    border-right: 2px solid #2d3748 !important;
    border-radius: 0 8px 8px 0 !important;
    width: 28px !important;
    padding: 8px 4px !important;
    top: 50% !important;
    z-index: 999 !important;
}
[data-testid="stSidebarCollapsedControl"] button {
    background: transparent !important;
    border: none !important;
    color: #e6edf3 !important;
    padding: 4px !important;
}
[data-testid="stSidebarCollapsedControl"] svg {
    fill: #e6edf3 !important;
    width: 18px !important;
    height: 18px !important;
}

.sidebar-logo {
    padding: 24px 12px 16px 12px;
    border-bottom: 1px solid #2d3748;
    margin-bottom: 6px;
    text-align: center;
}

/* KPI cards */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}
.kpi-card {
    background: #161b27;
    border: 1px solid #21273a;
    border-radius: 12px;
    padding: 20px 22px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.kpi-card.blue::before  { background: linear-gradient(90deg,#58a6ff,#1f6feb); }
.kpi-card.green::before { background: linear-gradient(90deg,#3fb950,#2ea043); }
.kpi-card.purple::before{ background: linear-gradient(90deg,#bc8cff,#8957e5); }
.kpi-card.orange::before{ background: linear-gradient(90deg,#f0883e,#db6d28); }
.kpi-label {
    font-size: 11px;
    color: #8b949e;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 8px;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f0f6fc;
    line-height: 1;
    margin-bottom: 4px;
}
.kpi-sub { font-size: 12px; color: #8b949e; }
.kpi-icon {
    position: absolute;
    top: 16px; right: 16px;
    font-size: 22px;
    opacity: 0.12;
}

/* Section header */
.section-header {
    display: flex;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1e2030;
}
.section-title {
    font-size: 11px;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: .08em;
}

/* Typography */
h1 { color: #f0f6fc !important; font-size: 1.55rem !important; font-weight: 700 !important; margin-bottom: 0 !important; }
h2 { color: #f0f6fc !important; font-size: 1.15rem !important; font-weight: 600 !important; }
h3 { color: #e6edf3 !important; font-size: 1rem !important; font-weight: 600 !important; }
p  { color: #c9d1d9 !important; }
label, span { color: #c9d1d9; }

/* Streamlit metric cards */
[data-testid="metric-container"] {
    background-color: #161b27 !important;
    border: 1px solid #21273a !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
}
[data-testid="metric-container"] label {
    color: #8b949e !important; font-size: 11px !important;
    font-weight: 600 !important; text-transform: uppercase !important;
    letter-spacing: .06em !important;
}
[data-testid="metric-container"] [data-testid="metric-value"] {
    color: #f0f6fc !important; font-size: 1.8rem !important; font-weight: 700 !important;
}

/* Global text overrides – ensure nothing is too dark */
[data-testid="stMarkdown"] p,
[data-testid="stMarkdown"] li,
[data-testid="stMarkdown"] span,
[data-testid="stCaption"],
[data-testid="stText"] {
    color: #c9d1d9 !important;
}
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p {
    color: #c9d1d9 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
}
/* Expander summary text */
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p {
    color: #c9d1d9 !important;
}
/* Checkbox label */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p { color: #c9d1d9 !important; }
/* Slider labels */
[data-testid="stSlider"] label,
[data-testid="stSlider"] p { color: #c9d1d9 !important; }
/* Select / multiselect label */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label { color: #c9d1d9 !important; }
/* Text input label */
[data-testid="stTextInput"] label { color: #c9d1d9 !important; }
/* Dataframe column headers */
[data-testid="stDataFrame"] th { color: #c9d1d9 !important; }
[data-testid="stDataFrame"] td { color: #e6edf3 !important; }

/* Buttons */
[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg,#1f6feb,#388bfd) !important;
    border: none !important; border-radius: 7px !important;
    color: #fff !important; font-weight: 600 !important;
}
[data-testid="baseButton-secondary"] {
    background: #161b27 !important; border: 1px solid #30363d !important;
    border-radius: 7px !important; color: #c9d1d9 !important;
}

/* Progress bar */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg,#1f6feb,#58a6ff) !important;
    border-radius: 4px !important;
}

/* ── All inputs / selects / widgets ── */
input, textarea,
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] > div > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] {
    background-color: #161b27 !important;
    border-color: #2d333b !important;
    color: #c9d1d9 !important;
}

/* Selectbox / dropdown */
[data-testid="stSelectbox"] > div,
[data-baseweb="select"] > div:first-child,
[data-baseweb="popover"] {
    background-color: #161b27 !important;
    border-color: #2d333b !important;
    color: #c9d1d9 !important;
}
[data-baseweb="select"] svg { fill: #6e7b95 !important; }

/* Multiselect */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #1e2a40 !important;
    border-color: #2d333b !important;
    color: #c9d1d9 !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #1e2a40 !important;
    border: 1px solid #2d4a6e !important;
    color: #58a6ff !important;
    border-radius: 4px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span { color: #58a6ff !important; }
[data-testid="stMultiSelect"] [role="option"],
[data-baseweb="menu"] { background-color: #161b27 !important; color: #c9d1d9 !important; }

/* Expander */
[data-testid="stExpander"] {
    background-color: #161b27 !important;
    border: 1px solid #21273a !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] details {
    background-color: #161b27 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    background-color: #161b27 !important;
    color: #8b949e !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary:hover {
    color: #c9d1d9 !important;
}
[data-testid="stExpanderDetails"] {
    background-color: #161b27 !important;
    border-top: 1px solid #1e2030 !important;
}

/* Slider */
[data-testid="stSlider"] > div > div > div {
    background-color: #1f6feb !important;
}
[data-testid="stSlider"] [data-testid="stTickBar"] {
    color: #6e7b95 !important;
}

/* Checkbox */
[data-testid="stCheckbox"] label { color: #8b949e !important; }

/* Dataframe / table */
[data-testid="stDataFrame"] {
    border: 1px solid #21273a !important;
    border-radius: 8px !important;
}

/* Dropdown menu list items */
[role="listbox"] li, [role="option"] {
    background-color: #161b27 !important;
    color: #c9d1d9 !important;
}
[role="option"]:hover { background-color: #1e2a40 !important; }

/* Info/warning/success boxes */
[data-testid="stAlert"][kind="info"] {
    background-color: #0e1f3a !important;
    border-color: #1f4070 !important;
    color: #58a6ff !important;
}

/* Hide only footer, keep toolbar and menus */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }

/* Style the top-right toolbar to match dark theme */
[data-testid="stToolbar"] {
    background-color: #0d1117 !important;
    border-bottom: 1px solid #1e2535 !important;
}
[data-testid="stToolbar"] button {
    background: transparent !important;
    color: #c9d1d9 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 6px !important;
}
[data-testid="stToolbar"] button:hover {
    background: #1e293b !important;
    border-color: #3d4a63 !important;
}
[data-testid="stToolbar"] svg {
    fill: #c9d1d9 !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def fmt_price(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(v):,}".replace(",", ".") + " €"
    except (ValueError, TypeError):
        return str(v)


def fmt_sqm(v) -> str:
    if v is None:
        return "—"
    return f"{int(v)} m²"


def plotly_theme(fig, title: str = ""):
    fig.update_layout(
        title=title,
        paper_bgcolor="#161b27",
        plot_bgcolor="#161b27",
        font_color="#c9d1d9",
        title_font_color="#e6edf3",
        title_font_size=13,
        title_font_family="Inter",
        margin=dict(l=16, r=16, t=44 if title else 20, b=16),
        legend=dict(
            bgcolor="#1a2035",
            bordercolor="#2d333b",
            borderwidth=1,
            font_color="#8b949e",
            font_size=11,
        ),
        colorway=["#58a6ff","#3fb950","#f0883e","#bc8cff","#ff7b72","#79c0ff"],
        xaxis=dict(gridcolor="#1a2035", linecolor="#2d333b", tickfont_color="#6e7b95"),
        yaxis=dict(gridcolor="#1a2035", linecolor="#2d333b", tickfont_color="#6e7b95"),
    )
    return fig


def kpi_card(label: str, value: str, sub: str, color: str, icon: str) -> str:
    return (
        f'<div class="kpi-card {color}">'
        f'<div class="kpi-icon">{icon}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )


def section_hdr(title: str):
    st.markdown(
        f'<div class="section-header">'
        f'<span class="section-title">{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── Sidebar ─────────────────────────────────────────────────────────────────

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


def _logo_b64() -> str:
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return ""


with st.sidebar:
    b64 = _logo_b64()
    if b64:
        st.markdown(
            f'<div class="sidebar-logo">'
            f'<img src="data:image/png;base64,{b64}" alt="Logo" '
            f'style="width:88%;max-width:200px;object-fit:contain;display:block;margin:0 auto;"/>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="sidebar-logo">'
            '<span style="color:#58a6ff;font-weight:700;font-size:13px;letter-spacing:.04em;">'
            "ANÀLISI IMMOBILIÀRIA D'ANDORRA</span></div>",
            unsafe_allow_html=True,
        )

    page = option_menu(
        menu_title=None,
        options=["Dashboard", "Sitios", "Inmuebles", "Análisis", "Scraping", "Exportar", "Ajustes"],
        icons=[
            "grid-fill", "globe2", "house-fill",
            "bar-chart-fill", "cloud-arrow-down-fill", "download", "gear-fill",
        ],
        default_index=0,
        styles={
            "container": {
                "padding": "4px 0 12px 0",
                "background-color": "transparent",
            },
            "icon": {
                "color": "#8b949e",
                "font-size": "14px",
            },
            "nav-link": {
                "font-size": "13px",
                "font-weight": "400",
                "color": "#c9d1d9",
                "background-color": "transparent",
                "padding": "9px 14px",
                "border-radius": "6px",
                "margin": "1px 8px",
                "--hover-color": "#131826",
            },
            "nav-link-selected": {
                "background-color": "#0e1f3a",
                "color": "#58a6ff",
                "font-weight": "600",
                "border-left": "3px solid #1f6feb",
                "border-radius": "0 6px 6px 0",
            },
        },
    )

    # Bottom stats pill
    total_props = db.get_total_properties()
    n_sites = len(db.get_enabled_sites())
    st.markdown(
        f'<div style="margin:16px 12px 0 12px;">'
        f'<div style="background:#0d1117;border:1px solid #2d3748;border-radius:8px;padding:12px 14px;">'
        f'<div style="font-size:10px;color:#c9d1d9;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:8px;">Sistema</div>'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">'
        f'<span style="font-size:12px;color:#c9d1d9;">Inmuebles</span>'
        f'<span style="font-size:12px;color:#58a6ff;font-weight:600;">{total_props:,}</span>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;">'
        f'<span style="font-size:12px;color:#c9d1d9;">Sitios activos</span>'
        f'<span style="font-size:12px;color:#3fb950;font-weight:600;">{n_sites}</span>'
        f'</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ─── Pages ───────────────────────────────────────────────────────────────────

def page_dashboard():
    st.markdown(
        "<h1>Dashboard</h1>"
        f"<p style='color:#c9d1d9;font-size:12px;margin-bottom:20px;'>"
        f"Actualizado {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>",
        unsafe_allow_html=True,
    )

    total_props = db.get_total_properties()
    props_today = db.get_properties_today()
    avg_price   = db.get_avg_price()
    active_sites = len(db.get_enabled_sites())
    avg_str = fmt_price(avg_price) if avg_price else "—"

    st.markdown(
        '<div class="kpi-grid">'
        + kpi_card("Total inmuebles",  f"{total_props:,}",    "en la base de datos",  "blue",   "🏠")
        + kpi_card("Scraped hoy",      f"{props_today:,}",    "últimas 24 horas",     "green",  "📥")
        + kpi_card("Precio medio",     avg_str,               "precio de venta",      "purple", "💶")
        + kpi_card("Sitios activos",   str(active_sites),     "webs monitorizadas",   "orange", "🌐")
        + "</div>",
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        section_hdr("Tendencia de scraping – últimos 30 días")
        daily = db.get_daily_counts(30)
        if daily:
            df_d = pd.DataFrame(daily)
            df_d["day"] = pd.to_datetime(df_d["day"]).dt.date  # date only, no time
            fig = px.area(df_d, x="day", y="count",
                          labels={"day": "", "count": "Inmuebles"})
            fig.update_traces(
                fill="tozeroy",
                line_color="#1f6feb",
                fillcolor="rgba(31,111,235,0.12)",
            )
            plotly_theme(fig)
            fig.update_xaxes(
                tickformat="%d/%m",
                dtick="D1" if len(df_d) <= 14 else "D7",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart("Sin datos – ejecuta el scraper", 200)

    with col_r:
        section_hdr("Distribución por portal")
        portals = db.get_portal_distribution()
        if portals:
            df_p = pd.DataFrame(portals)
            fig = px.pie(df_p, names="portal", values="count", hole=0.55)
            fig.update_traces(
                textposition="outside",
                textfont_size=10,
                textfont_color="#8b949e",
                marker=dict(line=dict(color="#0d1117", width=2)),
            )
            plotly_theme(fig)
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="v", x=1.0, y=0.5, font_size=10),
                margin=dict(l=0, r=70, t=16, b=0),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart("Sin datos aún", 200)

    zones = db.get_zone_distribution()
    if zones:
        section_hdr("Precio medio y volumen por zona")
        df_z = pd.DataFrame(zones).head(10)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_z["zona"], y=df_z["avg_precio"],
            name="Precio medio (€)",
            marker_color="#1f6feb",
            marker_line_width=0,
        ))
        fig.add_trace(go.Scatter(
            x=df_z["zona"], y=df_z["count"],
            name="Nº inmuebles",
            yaxis="y2",
            line=dict(color="#3fb950", width=2),
            mode="lines+markers",
            marker=dict(size=5),
        ))
        fig.update_layout(
            yaxis=dict(title="Precio medio (€)"),
            yaxis2=dict(title="Nº inmuebles", overlaying="y", side="right"),
            bargap=0.3,
        )
        plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    logs = db.get_recent_logs(5)
    if logs:
        section_hdr("Últimas operaciones")
        df_l = pd.DataFrame(logs)[
            ["site_name","started_at","status","properties_found","properties_new","error_msg"]
        ].rename(columns={
            "site_name": "Sitio", "started_at": "Inicio", "status": "Estado",
            "properties_found": "Encontrados", "properties_new": "Nuevos", "error_msg": "Error",
        })
        df_l["Inicio"] = pd.to_datetime(df_l["Inicio"]).dt.strftime("%d/%m %H:%M")
        df_l["Error"]  = df_l["Error"].fillna("—").str[:60]
        st.dataframe(df_l, use_container_width=True, hide_index=True)


def _empty_chart(msg: str, h: int = 160):
    st.markdown(
        f"<div style='height:{h}px;display:flex;align-items:center;"
        f"justify-content:center;background:#161b27;border-radius:10px;"
        f"border:1px dashed #21273a;color:#8b949e;font-size:13px;'>{msg}</div>",
        unsafe_allow_html=True,
    )


def page_sitios():
    h_col, btn_col = st.columns([4, 1])
    with h_col:
        st.markdown(
            "<h1>Sitios</h1>"
            "<p style='color:#c9d1d9;font-size:12px;margin-bottom:16px;'>"
            "Gestiona las webs monitorizadas</p>",
            unsafe_allow_html=True,
        )
    with btn_col:
        st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
        add_clicked = st.button("➕  Añadir sitio", type="primary", use_container_width=True)

    # Show add-site panel immediately if button pressed
    if add_clicked:
        st.session_state["show_add_site"] = True

    if st.session_state.get("show_add_site"):
        st.markdown(
            '<div style="background:#132033;border:1px solid #1f6feb;border-radius:12px;'
            'padding:20px 24px;margin-bottom:20px;">',
            unsafe_allow_html=True,
        )
        st.markdown("**➕  Añadir nuevo sitio**", unsafe_allow_html=False)
        tab_manual, tab_csv = st.tabs(["✏️  Formulario", "📄  Importar CSV"])

        with tab_manual:
            with st.form("add_site_form_top", clear_on_submit=True):
                f1, f2 = st.columns(2)
                with f1:
                    new_name = st.text_input("Nombre *", placeholder="RE/MAX Andorra")
                    new_url  = st.text_input("URL *", placeholder="https://www.remax.ad")
                with f2:
                    new_type    = st.selectbox("Tipo", ["agency", "portal", "bank", "developer", "other"])
                    new_scraper = st.selectbox("Scraper", ["generic", "fotocasa", "idealista", "habitaclia"])
                new_notes = st.text_input("Notas (opcional)")
                c_save, c_cancel = st.columns([1, 1])
                submitted = c_save.form_submit_button("✓  Guardar", type="primary", use_container_width=True)
                cancelled = c_cancel.form_submit_button("✕  Cancelar", use_container_width=True)

            if cancelled:
                st.session_state["show_add_site"] = False
                st.rerun()
            if submitted:
                if not new_name or not new_url:
                    st.error("Nombre y URL son obligatorios.")
                elif not new_url.startswith("http"):
                    st.error("La URL debe empezar por https://")
                else:
                    import re as _re, hashlib
                    sid = _re.sub(r"[^a-z0-9]+", "-", new_name.lower()).strip("-")[:40]
                    existing = {s["id"] for s in db.get_sites()}
                    if sid in existing:
                        sid += "-" + hashlib.md5(new_url.encode()).hexdigest()[:4]
                    db.add_site({"id": sid, "name": new_name.strip(), "base_url": new_url.strip(),
                                 "site_type": new_type, "scraper_type": new_scraper,
                                 "notes": new_notes.strip(), "enabled": True})
                    st.session_state["show_add_site"] = False
                    st.success(f"✓ «{new_name}» añadido.")
                    st.rerun()

        with tab_csv:
            st.markdown(
                "<small style='color:#c9d1d9;'>CSV con columnas: <b>nombre</b>, <b>url</b>"
                " (+ opcionales: tipo, scraper, notas)</small>",
                unsafe_allow_html=True,
            )
            template = "nombre,url,tipo,scraper,notas\nRE/MAX Andorra,https://www.remax.ad,agency,generic,\n"
            st.download_button("⬇  Plantilla CSV", template, "plantilla_sitios.csv", "text/csv", type="secondary")
            uploaded = st.file_uploader("Subir CSV", type=["csv"], label_visibility="collapsed")
            if uploaded:
                import re as _re, hashlib
                df_csv = pd.read_csv(uploaded)
                df_csv.columns = df_csv.columns.str.strip().str.lower()
                if not {"nombre", "url"}.issubset(set(df_csv.columns)):
                    st.error("El CSV necesita columnas: nombre, url")
                else:
                    existing = {s["id"] for s in db.get_sites()}
                    added = skipped = 0
                    for _, row in df_csv.iterrows():
                        name = str(row.get("nombre","")).strip()
                        url  = str(row.get("url","")).strip()
                        if not name or not url or not url.startswith("http"):
                            skipped += 1; continue
                        sid = _re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")[:40]
                        if sid in existing:
                            sid += "-" + hashlib.md5(url.encode()).hexdigest()[:4]
                        try:
                            db.add_site({"id":sid,"name":name,"base_url":url,
                                         "site_type":str(row.get("tipo","agency")).strip() or "agency",
                                         "scraper_type":str(row.get("scraper","generic")).strip() or "generic",
                                         "notes":str(row.get("notas","")).strip(),"enabled":True})
                            existing.add(sid); added += 1
                        except Exception:
                            skipped += 1
                    st.success(f"✓ {added} importados, {skipped} omitidos.")
                    if added:
                        st.session_state["show_add_site"] = False
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    sites = db.get_sites()
    if not sites:
        st.info("No hay sitios. Usa el botón '➕ Añadir sitio' para empezar.")
        return

    col_a, col_b, col_c = st.columns([3, 2, 1])
    with col_a:
        search = st.text_input("", placeholder="Buscar nombre o URL…", label_visibility="collapsed")
    with col_b:
        tipos = sorted({s.get("site_type", "—") for s in sites})
        tipo_f = st.multiselect("", tipos, label_visibility="collapsed", placeholder="Todos los tipos")
    with col_c:
        solo_activos = st.checkbox("Solo activos")

    filtered = [
        s for s in sites
        if (not search or search.lower() in s["name"].lower() or search.lower() in s["base_url"].lower())
        and (not tipo_f or s.get("site_type") in tipo_f)
        and (not solo_activos or s["enabled"])
    ]

    st.markdown(
        f"<p style='color:#c9d1d9;font-size:11px;margin-bottom:10px;'>"
        f"{len(filtered)} de {len(sites)} sitios</p>",
        unsafe_allow_html=True,
    )

    cols_hdr = st.columns([3, 4, 1, 1, 1, 2])
    for col, h in zip(cols_hdr, ["Nombre", "URL de búsqueda", "Act.", "Scraper", "Editar", "Últ. scraping"]):
        col.markdown(
            f"<span style='font-size:10px;color:#c9d1d9;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.07em;'>{h}</span>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='border-bottom:1px solid #1a2035;margin-bottom:2px;'></div>",
                unsafe_allow_html=True)

    for s in filtered:
        c = st.columns([3, 4, 1, 1, 1, 2])
        c[0].markdown(
            f"<span style='color:#c9d1d9;font-size:13px;font-weight:500;'>{s['name']}</span>",
            unsafe_allow_html=True,
        )
        url_display = s["base_url"][:50] + "…" if len(s["base_url"]) > 50 else s["base_url"]
        c[1].markdown(
            f"<span style='color:#58a6ff;font-size:11px;'>{url_display}</span>",
            unsafe_allow_html=True,
        )
        enabled = c[2].checkbox("", value=bool(s["enabled"]), key=f"tog_{s['id']}",
                                 label_visibility="collapsed")
        if enabled != bool(s["enabled"]):
            db.toggle_site(s["id"], enabled)
            st.rerun()

        c[3].markdown(
            f"<span style='font-size:11px;color:#c9d1d9;'>{s.get('scraper_type','generic')}</span>",
            unsafe_allow_html=True,
        )

        edit_key = f"edit_{s['id']}"
        if c[4].button("✏️", key=f"btn_{s['id']}", help="Editar URL y nombre"):
            st.session_state[edit_key] = True

        last = s.get("last_scraped") or "Nunca"
        if last != "Nunca":
            try:
                last = datetime.fromisoformat(last).strftime("%d/%m %H:%M")
            except Exception:
                pass
        c[5].markdown(
            f"<span style='font-size:11px;color:#c9d1d9;'>{last}</span>",
            unsafe_allow_html=True,
        )

        # Inline edit panel
        if st.session_state.get(edit_key):
            with st.container():
                st.markdown(
                    f"<div style='background:#1a2035;border:1px solid #2d3748;border-radius:8px;"
                    f"padding:14px 16px;margin:4px 0 8px 0;'>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<p style='color:#58a6ff;font-size:12px;font-weight:600;margin-bottom:8px;'>"
                    f"✏️ Editando: {s['name']}</p>",
                    unsafe_allow_html=True,
                )
                ec1, ec2 = st.columns(2)
                new_name = ec1.text_input("Nombre", value=s["name"], key=f"name_{s['id']}")
                new_url  = ec2.text_input(
                    "URL de búsqueda",
                    value=s["base_url"],
                    key=f"url_{s['id']}",
                    help="Cambia la zona geográfica modificando esta URL. Ej: .../andorra/... → .../lleida-provincia/...",
                )
                scraper_opts = ["generic", "fotocasa", "idealista", "habitaclia", "trovit", "nuroa", "jsonld"]
                cur_scraper = s.get("scraper_type", "generic")
                scraper_idx = scraper_opts.index(cur_scraper) if cur_scraper in scraper_opts else 0
                new_scraper = st.selectbox(
                    "Tipo de scraper", scraper_opts, index=scraper_idx, key=f"scraper_{s['id']}"
                )
                sa, sb, _ = st.columns([1, 1, 4])
                if sa.button("💾 Guardar", key=f"save_{s['id']}", type="primary"):
                    db.update_site(s["id"], {
                        "name": new_name.strip(),
                        "base_url": new_url.strip(),
                        "scraper_type": new_scraper,
                    })
                    st.session_state[edit_key] = False
                    st.success(f"✅ {new_name} actualizado")
                    st.rerun()
                if sb.button("✖ Cancelar", key=f"cancel_{s['id']}"):
                    st.session_state[edit_key] = False
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)



def page_inmuebles():
    st.markdown(
        "<h1>Inmuebles</h1>"
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:16px;'>"
        "Explora y filtra todas las propiedades</p>",
        unsafe_allow_html=True,
    )

    _MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
              7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

    # Pre-load data ranges
    all_raw = db.get_properties(limit=99999)
    all_df = pd.DataFrame(all_raw) if all_raw else pd.DataFrame()
    precio_all = all_df["precio"].dropna() if not all_df.empty else pd.Series([0, 10_000_000])
    metros_all = all_df["metros_cuadrados"].dropna() if not all_df.empty else pd.Series([0, 1000])
    p_min_raw = int(precio_all.min()) if len(precio_all) else 0
    p_max_raw = int(precio_all.max()) if len(precio_all) else 10_000_000
    m_min_raw = int(metros_all.min()) if len(metros_all) else 0
    m_max_raw = int(metros_all.max()) if len(metros_all) else 1000

    # Available years/months for date filters
    def _date_opts(col):
        if all_df.empty or col not in all_df.columns:
            return [], []
        s = pd.to_datetime(all_df[col], errors="coerce").dropna()
        years  = sorted(s.dt.year.unique().tolist(), reverse=True)
        months = sorted(s.dt.month.unique().tolist())
        return [str(y) for y in years], months

    pub_years_opts,  pub_months_opts  = _date_opts("fecha_publicacion")
    scr_years_opts,  scr_months_opts  = _date_opts("scraped_at")

    with st.expander("🔍  Filtros", expanded=True):
        row1 = st.columns([3, 2, 2, 1])
        with row1[0]:
            search = st.text_input("Búsqueda", placeholder="Título, zona, descripción…", label_visibility="visible")
        with row1[1]:
            portals = db.get_portal_distribution()
            p_opts = [p["portal"] for p in portals]
            portal_f = st.multiselect("Portal", p_opts, placeholder="Todos")
        with row1[2]:
            zones = db.get_zone_distribution()
            z_opts = [z["zona"] for z in zones if z["zona"]]
            zona_f = st.multiselect("Zona", z_opts, placeholder="Todas")
        with row1[3]:
            tipos_opts = []
            if not all_df.empty and "tipo_inmueble" in all_df.columns:
                tipos_opts = sorted(all_df["tipo_inmueble"].dropna().unique().tolist())
            tipo_f = st.multiselect("Tipo", tipos_opts, placeholder="Todos")

        row2 = st.columns([2, 2, 1, 1, 1])
        with row2[0]:
            precio_range = st.slider(
                "Precio (€)",
                min_value=p_min_raw, max_value=p_max_raw,
                value=(p_min_raw, p_max_raw),
                step=max(1, (p_max_raw - p_min_raw) // 200),
                format="%d €",
            )
        with row2[1]:
            metros_range = st.slider(
                "Superficie (m²)",
                min_value=m_min_raw, max_value=m_max_raw,
                value=(m_min_raw, m_max_raw),
                step=max(1, (m_max_raw - m_min_raw) // 100),
                format="%d m²",
            )
        with row2[2]:
            hab_min = st.selectbox("Hab. mín.", [0, 1, 2, 3, 4, 5],
                                   format_func=lambda x: "—" if x == 0 else f"{x}+")
        with row2[3]:
            ban_min = st.selectbox("Baños mín.", [0, 1, 2, 3],
                                   format_func=lambda x: "—" if x == 0 else f"{x}+")
        with row2[4]:
            limite = st.selectbox("Mostrar", [100, 200, 500, 1000, 2000], index=1)

        row3 = st.columns([1, 2, 1, 2])
        with row3[0]:
            pub_years_f = st.multiselect("Año publicación", pub_years_opts, placeholder="Todos")
        with row3[1]:
            pub_months_f = st.multiselect(
                "Mes publicación",
                pub_months_opts,
                format_func=lambda m: _MESES[m],
                placeholder="Todos",
            )
        with row3[2]:
            scr_years_f = st.multiselect("Año scraped", scr_years_opts, placeholder="Todos")
        with row3[3]:
            scr_months_f = st.multiselect(
                "Mes scraped",
                scr_months_opts,
                format_func=lambda m: _MESES[m],
                placeholder="Todos",
            )

    props = db.get_properties(
        limit=limite,
        zona=zona_f or None,
        search=search or None,
        portal=portal_f or None,
        precio_min=float(precio_range[0]) if precio_range[0] > p_min_raw else None,
        precio_max=float(precio_range[1]) if precio_range[1] < p_max_raw else None,
        metros_min=float(metros_range[0]) if metros_range[0] > m_min_raw else None,
        metros_max=float(metros_range[1]) if metros_range[1] < m_max_raw else None,
        hab_min=int(hab_min) if hab_min > 0 else None,
        banos_min=int(ban_min) if ban_min > 0 else None,
        tipo=tipo_f or None,
    )

    if not props:
        _empty_chart("No hay inmuebles con los filtros actuales", 180)
        return

    df = pd.DataFrame(props)

    # Apply date filters in pandas
    if pub_years_f or pub_months_f:
        _pub = pd.to_datetime(df.get("fecha_publicacion", pd.Series(dtype=str)), errors="coerce")
        if pub_years_f:
            df = df[_pub.dt.year.isin([int(y) for y in pub_years_f])]
        if pub_months_f:
            df = df[_pub.dt.month.isin(pub_months_f)]
    if scr_years_f or scr_months_f:
        _scr = pd.to_datetime(df.get("scraped_at", pd.Series(dtype=str)), errors="coerce")
        if scr_years_f:
            df = df[_scr.dt.year.isin([int(y) for y in scr_years_f])]
        if scr_months_f:
            df = df[_scr.dt.month.isin(scr_months_f)]

    if df.empty:
        _empty_chart("No hay inmuebles con los filtros actuales", 180)
        return

    # Quick stats bar
    n = len(df)
    avg_p = df["precio"].mean() if "precio" in df.columns else None
    avg_m = df["metros_cuadrados"].mean() if "metros_cuadrados" in df.columns else None
    df_valid = df[(df["precio"] > 0) & (df["metros_cuadrados"] > 0)] if not df.empty else df
    avg_pm2 = (df_valid["precio"] / df_valid["metros_cuadrados"]).mean() if not df_valid.empty else None

    stat_cols = st.columns(4)
    def _mini_stat(col, label, value):
        col.markdown(
            f'<div style="background:#0e1525;border:1px solid #1a2035;border-radius:8px;'
            f'padding:10px 14px;text-align:center;">'
            f'<div style="font-size:10px;color:#c9d1d9;text-transform:uppercase;'
            f'letter-spacing:.07em;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:1.15rem;font-weight:700;color:#e6edf3;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    _mini_stat(stat_cols[0], "Resultados", f"{n:,}")
    _mini_stat(stat_cols[1], "Precio medio", fmt_price(avg_p))
    _mini_stat(stat_cols[2], "Superficie media", fmt_sqm(avg_m) if avg_m else "—")
    _mini_stat(stat_cols[3], "€/m² medio", f"{int(avg_pm2):,} €/m²" if avg_pm2 else "—")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # Table — pre-format numbers as strings so dots appear as thousand separators
    def _fmt_eur(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
        return f"{int(v):,}".replace(",", ".") + " €"
    def _fmt_m2(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
        return f"{int(v):,}".replace(",", ".") + " m²"

    cols_needed = ["titulo", "precio", "metros_cuadrados", "habitaciones", "banos",
                   "parking", "terraza", "zona", "portal", "tipo_inmueble",
                   "fecha_publicacion", "scraped_at", "url"]
    df_show = df[[c for c in cols_needed if c in df.columns]].copy()

    if "precio" in df_show.columns and "metros_cuadrados" in df_show.columns:
        valid = df_show["metros_cuadrados"] > 0
        df_show["precio_m2"] = (df_show["precio"] / df_show["metros_cuadrados"]).where(valid)

    # ── Scoring column: compare €/m² to zone avg, adjusted for amenities ──────
    _score_labels = {
        "chollo":      "🔥 Chollo",
        "interesante": "✅ Interesante",
        "normal":      "😐 Normal",
        "caro":        "⚠️ Caro",
        "muy_caro":    "❌ Muy caro",
        "sin_datos":   "❓ Sin datos",
    }
    if "precio_m2" in df_show.columns:
        # Zone averages from ALL available data (stable reference, not filtered)
        _all_valid = all_df[
            all_df["precio"].fillna(0) > 0
        ].copy() if not all_df.empty else pd.DataFrame()
        if not _all_valid.empty and "metros_cuadrados" in _all_valid.columns:
            _all_valid = _all_valid[_all_valid["metros_cuadrados"].fillna(0) > 0].copy()
            _all_valid["_pm2"] = _all_valid["precio"] / _all_valid["metros_cuadrados"]
            _zone_stats = _all_valid.groupby("zona")["_pm2"].agg(["mean", "count"]) if "zona" in _all_valid.columns else pd.DataFrame()
            _global_avg = float(_all_valid["_pm2"].mean()) if not _all_valid.empty else 0
        else:
            _zone_stats = pd.DataFrame()
            _global_avg = 0

        def _calc_score(row):
            pm2 = row.get("precio_m2")
            if pm2 is None or (isinstance(pm2, float) and pd.isna(pm2)) or pm2 <= 0:
                return _score_labels["sin_datos"]
            zona_r = str(row.get("zona", ""))
            # Use zone average if ≥3 data points, else global
            if (not _zone_stats.empty and zona_r in _zone_stats.index
                    and _zone_stats.loc[zona_r, "count"] >= 3):
                ref = float(_zone_stats.loc[zona_r, "mean"])
            else:
                ref = _global_avg
            if ref <= 0:
                return _score_labels["sin_datos"]
            ratio = pm2 / ref
            # Amenity adjustments — amenities add value so they lower the effective ratio
            if row.get("parking") == 1: ratio -= 0.05
            if row.get("terraza") == 1: ratio -= 0.03
            banos_v  = row.get("banos")
            habs_v   = row.get("habitaciones")
            if pd.notna(banos_v) and pd.notna(habs_v) and banos_v and habs_v and banos_v > 1:
                ratio -= 0.02 * (int(banos_v) - 1)
            if ratio < 0.75: return _score_labels["chollo"]
            if ratio < 0.90: return _score_labels["interesante"]
            if ratio < 1.10: return _score_labels["normal"]
            if ratio < 1.30: return _score_labels["caro"]
            return _score_labels["muy_caro"]

        df_show["Conclusión"] = df_show.apply(_calc_score, axis=1)

    # Format numbers as Spanish-style strings
    if "precio"           in df_show.columns: df_show["precio"]          = df_show["precio"].apply(_fmt_eur)
    if "metros_cuadrados" in df_show.columns: df_show["metros_cuadrados"] = df_show["metros_cuadrados"].apply(_fmt_m2)
    if "precio_m2"        in df_show.columns: df_show["precio_m2"]        = df_show["precio_m2"].apply(_fmt_eur)
    if "scraped_at"       in df_show.columns: df_show["scraped_at"] = pd.to_datetime(df_show["scraped_at"]).dt.strftime("%d/%m/%Y")
    if "fecha_publicacion" in df_show.columns:
        def _fmt_fecha(x):
            if x is None or (isinstance(x, float) and pd.isna(x)) or not x:
                return "—"
            if not isinstance(x, str):
                return "—"
            try:
                return pd.to_datetime(x).strftime("%d/%m/%Y")
            except Exception:
                return str(x)[:10] if len(str(x)) >= 10 else "—"
        df_show["fecha_publicacion"] = df_show["fecha_publicacion"].apply(_fmt_fecha)
    if "habitaciones" in df_show.columns: df_show["habitaciones"] = df_show["habitaciones"].apply(lambda x: str(int(x)) if pd.notna(x) else "—")
    if "banos"        in df_show.columns: df_show["banos"]        = df_show["banos"].apply(lambda x: str(int(x)) if pd.notna(x) else "—")
    if "parking"      in df_show.columns: df_show["parking"]      = df_show["parking"].apply(lambda x: "✅" if pd.notna(x) and x else "—")
    if "terraza"      in df_show.columns: df_show["terraza"]      = df_show["terraza"].apply(lambda x: "✅" if pd.notna(x) and x else "—")

    df_show.rename(columns={
        "titulo": "Título", "precio": "Precio", "metros_cuadrados": "Superficie",
        "habitaciones": "Hab.", "banos": "Baños", "parking": "Parking",
        "terraza": "Terraza", "zona": "Zona", "portal": "Portal", "tipo_inmueble": "Tipo",
        "fecha_publicacion": "Publicado", "scraped_at": "Scraped", "url": "Ver", "precio_m2": "€/m²",
    }, inplace=True)

    # Put Conclusión first
    if "Conclusión" in df_show.columns:
        other_cols = [c for c in df_show.columns if c != "Conclusión"]
        df_show = df_show[["Conclusión"] + other_cols]

    col_cfg = {
        "Conclusión": st.column_config.TextColumn("Conclusión", width="medium"),
        "Título":    st.column_config.TextColumn("Título", width="large"),
        "Precio":    st.column_config.TextColumn("Precio", width="medium"),
        "Superficie":st.column_config.TextColumn("Superficie", width="small"),
        "€/m²":      st.column_config.TextColumn("€/m²", width="small"),
        "Hab.":      st.column_config.TextColumn("Hab.", width="small"),
        "Baños":     st.column_config.TextColumn("Baños", width="small"),
        "Parking":   st.column_config.TextColumn("Parking", width="small"),
        "Terraza":   st.column_config.TextColumn("Terraza", width="small"),
        "Zona":      st.column_config.TextColumn("Zona", width="medium"),
        "Portal":    st.column_config.TextColumn("Portal", width="small"),
        "Tipo":      st.column_config.TextColumn("Tipo", width="small"),
        "Publicado": st.column_config.TextColumn("Publicado", width="small"),
        "Scraped":   st.column_config.TextColumn("Scraped", width="small"),
    }
    if "Ver" in df_show.columns:
        col_cfg["Ver"] = st.column_config.LinkColumn("Anuncio", display_text="Abrir ↗", width="small")

    # Height = all rows visible → page scroll, not table scroll
    row_h = 36
    table_h = (len(df_show) + 1) * row_h + 4
    st.dataframe(df_show, use_container_width=True, hide_index=True,
                 height=table_h, column_config=col_cfg)


def page_analisis():
    st.markdown(
        "<h1>Análisis del mercado</h1>"
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:20px;'>"
        "Todo lo que necesitas saber para comprar en Andorra</p>",
        unsafe_allow_html=True,
    )

    props = db.get_properties(limit=10000)
    if not props:
        _empty_chart("Sin datos – ejecuta el scraper primero", 220)
        return

    df = pd.DataFrame(props)
    df = df[df["precio"].notna() & (df["precio"] > 0)].copy()
    if df.empty:
        _empty_chart("No hay datos de precio disponibles", 220)
        return

    df_sqm = df[df["metros_cuadrados"].notna() & (df["metros_cuadrados"] > 0)].copy()
    df_sqm["pm2"] = df_sqm["precio"] / df_sqm["metros_cuadrados"]

    n_total  = len(df)
    avg_pr   = df["precio"].mean()
    min_pr   = df["precio"].min()
    max_pr   = df["precio"].max()
    avg_pm2  = df_sqm["pm2"].mean() if not df_sqm.empty else 0
    avg_sqm  = df["metros_cuadrados"].mean() if "metros_cuadrados" in df.columns else 0

    # ── KPIs ──────────────────────────────────────────────────────────────────
    kpi_cols = st.columns(4)
    _kpis = [
        ("Pisos en venta",    f"{n_total:,}",                "anuncios activos",           "blue"),
        ("Precio más bajo",   fmt_price(min_pr),             "la oferta más asequible",    "green"),
        ("Precio medio",      fmt_price(avg_pr),             "precio típico del mercado",  "purple"),
        ("Coste por m²",      f"{int(avg_pm2):,} €" if avg_pm2 else "—", "precio medio por metro cuadrado", "orange"),
    ]
    for col, (lbl, val, sub, clr) in zip(kpi_cols, _kpis):
        col.markdown(
            f'<div class="kpi-card {clr}" style="padding:14px 16px;">'
            f'<div class="kpi-label">{lbl}</div>'
            f'<div class="kpi-value" style="font-size:1.3rem;">{val}</div>'
            f'<div class="kpi-sub">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Zona ranking ──────────────────────────────────────────────────────────
    section_hdr("¿Dónde es más caro vivir?")
    st.markdown(
        "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
        "Precio medio de venta por zona, de más barato a más caro</p>",
        unsafe_allow_html=True,
    )
    zone_data = db.get_price_sqm_by_zone()
    if zone_data:
        df_z = pd.DataFrame(zone_data)
        df_z = df_z[df_z["count"] >= 2].sort_values("avg_precio", ascending=True)
        if not df_z.empty:
            global_avg_z = df_z["avg_precio"].mean()
            df_z["color"] = df_z["avg_precio"].apply(
                lambda x: "#3fb950" if x < global_avg_z * 0.9
                else ("#f0883e" if x > global_avg_z * 1.1 else "#1f6feb")
            )
            df_z["label"] = df_z["avg_precio"].apply(
                lambda x: f"{int(x):,} €".replace(",", ".")
            )
            fig = go.Figure(go.Bar(
                y=df_z["zona"],
                x=df_z["avg_precio"],
                orientation="h",
                marker_color=df_z["color"],
                marker_line_width=0,
                text=df_z["label"],
                textposition="outside",
                textfont=dict(color="#c9d1d9", size=12),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Precio medio: %{text}<br>"
                    "<extra></extra>"
                ),
            ))
            # Reference line at global avg
            fig.add_vline(
                x=global_avg_z, line_dash="dot", line_color="#8b949e", line_width=1,
                annotation_text="media general",
                annotation_font_color="#8b949e", annotation_font_size=10,
                annotation_position="top right",
            )
            plotly_theme(fig)
            fig.update_layout(
                height=max(260, len(df_z) * 40),
                margin=dict(l=0, r=100, t=10, b=10),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False),
                bargap=0.25,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Insight callout
            cheapest = df_z.iloc[0]
            dearest  = df_z.iloc[-1]
            st.markdown(
                f"<div style='background:#0e1525;border-left:3px solid #1f6feb;"
                f"padding:10px 14px;border-radius:0 8px 8px 0;font-size:12px;color:#c9d1d9;margin-top:4px;'>"
                f"💡 La zona más asequible es <b>{cheapest['zona']}</b> "
                f"({int(cheapest['avg_precio']):,} € de media). "
                f"La más cara es <b>{dearest['zona']}</b> "
                f"({int(dearest['avg_precio']):,} € de media), "
                f"un <b>{int((dearest['avg_precio']/cheapest['avg_precio']-1)*100)}% más cara</b>."
                f"</div>".replace(",", "."),
                unsafe_allow_html=True,
            )
    else:
        _empty_chart("Sin datos de zona", 200)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Precio por habitaciones ───────────────────────────────────────────────
    r2a, r2b = st.columns([3, 2], gap="large")

    with r2a:
        section_hdr("¿Cuánto cuesta según el número de habitaciones?")
        st.markdown(
            "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
            "Precio mínimo, medio y máximo según habitaciones</p>",
            unsafe_allow_html=True,
        )
        df_hab = df[df["habitaciones"].notna() & (df["habitaciones"] > 0) & (df["habitaciones"] <= 6)].copy()
        df_hab["hab_label"] = df_hab["habitaciones"].astype(int).apply(
            lambda x: f"{x} hab." if x < 6 else "6+ hab."
        )
        if not df_hab.empty:
            hab_stats = df_hab.groupby("hab_label")["precio"].agg(
                minimo="min", medio="mean", maximo="max", n="count"
            ).reset_index().sort_values("hab_label")

            fig = go.Figure()
            colors_hab = ["#3fb950", "#58a6ff", "#f0883e", "#bc8cff", "#ff7b72", "#79c0ff"]
            for i, row in hab_stats.iterrows():
                c = colors_hab[i % len(colors_hab)]
                fig.add_trace(go.Bar(
                    name=row["hab_label"],
                    x=[row["hab_label"]],
                    y=[row["medio"]],
                    marker_color=c,
                    marker_line_width=0,
                    error_y=dict(
                        type="data",
                        symmetric=False,
                        array=[row["maximo"] - row["medio"]],
                        arrayminus=[row["medio"] - row["minimo"]],
                        color=c,
                        thickness=2,
                        width=8,
                    ),
                    text=f"{int(row['medio']):,} €".replace(",", "."),
                    textposition="outside",
                    textfont=dict(size=12, color="#c9d1d9"),
                    hovertemplate=(
                        f"<b>{row['hab_label']}</b><br>"
                        f"Medio: {int(row['medio']):,} €<br>"
                        f"Desde: {int(row['minimo']):,} €<br>"
                        f"Hasta: {int(row['maximo']):,} €<br>"
                        f"Anuncios: {int(row['n'])}<extra></extra>"
                    ).replace(",", "."),
                    showlegend=False,
                ))
            plotly_theme(fig)
            fig.update_layout(
                height=340,
                margin=dict(l=0, r=10, t=30, b=10),
                yaxis=dict(showgrid=False, showticklabels=False),
                xaxis=dict(showgrid=False),
                bargap=0.3,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart("Sin datos de habitaciones", 280)

    with r2b:
        section_hdr("¿Qué tipo de inmueble hay en venta?")
        st.markdown(
            "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
            "Distribución de anuncios por tipo</p>",
            unsafe_allow_html=True,
        )
        tipo_data = db.get_tipo_distribution()
        if tipo_data:
            df_t = pd.DataFrame(tipo_data)
            # Human-readable labels
            tipo_map = {"piso": "Piso / Apartamento", "casa": "Casa / Chalet",
                        "local": "Local / Oficina", "terreno": "Terreno",
                        "garage": "Garaje", "duplex": "Dúplex"}
            df_t["tipo_label"] = df_t["tipo_inmueble"].map(
                lambda x: tipo_map.get(str(x).lower(), str(x).capitalize())
            )
            fig = px.pie(
                df_t, names="tipo_label", values="count",
                hole=0.55,
                color_discrete_sequence=["#1f6feb", "#3fb950", "#f0883e", "#bc8cff", "#ff7b72"],
            )
            fig.update_traces(
                textposition="outside",
                textfont=dict(size=11, color="#c9d1d9"),
                marker=dict(line=dict(color="#0d1117", width=2)),
            )
            plotly_theme(fig)
            fig.update_layout(
                height=320,
                showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                annotations=[dict(
                    text=f"<b>{df_t['count'].sum()}</b><br><span style='font-size:11px'>pisos</span>",
                    x=0.5, y=0.5, font_size=16,
                    font_color="#e6edf3",
                    showarrow=False,
                )],
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart("Sin datos de tipo", 260)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Estado del mercado (scoring) ──────────────────────────────────────────
    r3a, r3b = st.columns([2, 3], gap="large")

    with r3a:
        section_hdr("¿Cómo está el mercado ahora?")
        st.markdown(
            "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
            "Proporción de pisos baratos, a precio de mercado y caros</p>",
            unsafe_allow_html=True,
        )
        # Compute scoring for all properties
        if not df_sqm.empty:
            _zone_avg = df_sqm.groupby("zona")["pm2"].agg(["mean", "count"]) if "zona" in df_sqm.columns else pd.DataFrame()
            _glob_avg = float(df_sqm["pm2"].mean())

            def _quick_score(row):
                pm2 = row.get("pm2", 0)
                if not pm2: return None
                zona_r = str(row.get("zona", ""))
                ref = (float(_zone_avg.loc[zona_r, "mean"])
                       if not _zone_avg.empty and zona_r in _zone_avg.index
                       and _zone_avg.loc[zona_r, "count"] >= 3 else _glob_avg)
                ratio = pm2 / ref if ref > 0 else 1
                if row.get("parking") == 1: ratio -= 0.05
                if row.get("terraza") == 1: ratio -= 0.03
                if ratio < 0.75:  return "🔥 Chollo"
                if ratio < 0.90:  return "✅ Interesante"
                if ratio < 1.10:  return "😐 Precio de mercado"
                if ratio < 1.30:  return "⚠️ Algo caro"
                return "❌ Muy caro"

            df_sqm["score"] = df_sqm.apply(_quick_score, axis=1)
            score_counts = df_sqm["score"].value_counts().reset_index()
            score_counts.columns = ["score", "n"]
            score_order = ["🔥 Chollo", "✅ Interesante", "😐 Precio de mercado", "⚠️ Algo caro", "❌ Muy caro"]
            score_colors = {"🔥 Chollo": "#3fb950", "✅ Interesante": "#58a6ff",
                            "😐 Precio de mercado": "#8b949e", "⚠️ Algo caro": "#f0883e", "❌ Muy caro": "#f85149"}
            score_counts = score_counts[score_counts["score"].isin(score_order)]
            score_counts["score"] = pd.Categorical(score_counts["score"], categories=score_order, ordered=True)
            score_counts = score_counts.sort_values("score")

            if not score_counts.empty:
                fig = go.Figure(go.Bar(
                    x=score_counts["n"],
                    y=score_counts["score"],
                    orientation="h",
                    marker_color=[score_colors.get(s, "#1f6feb") for s in score_counts["score"]],
                    marker_line_width=0,
                    text=score_counts["n"],
                    textposition="outside",
                    textfont=dict(color="#c9d1d9", size=13),
                    hovertemplate="<b>%{y}</b><br>%{x} pisos<extra></extra>",
                ))
                plotly_theme(fig)
                fig.update_layout(
                    height=280,
                    margin=dict(l=0, r=40, t=10, b=10),
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False),
                    bargap=0.3,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart("Sin datos de superficie", 200)

    with r3b:
        section_hdr("Los mejores chollos ahora mismo")
        st.markdown(
            "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
            "Pisos por debajo del precio de mercado de su zona</p>",
            unsafe_allow_html=True,
        )
        if not df_sqm.empty and "score" in df_sqm.columns:
            df_chollos = df_sqm[df_sqm["score"].isin(["🔥 Chollo", "✅ Interesante"])].copy()
            df_chollos = df_chollos.sort_values("pm2").head(10)
            if not df_chollos.empty:
                def _fmt_eur_k(v):
                    if v >= 1_000_000:
                        return f"{v/1_000_000:.1f}M €"
                    if v >= 1_000:
                        return f"{int(v/1_000)}K €"
                    return f"{int(v)} €"

                tbl = pd.DataFrame({
                    "": df_chollos["score"],
                    "Zona": df_chollos["zona"].fillna("—"),
                    "Precio": df_chollos["precio"].apply(_fmt_eur_k),
                    "m²": df_chollos["metros_cuadrados"].apply(
                        lambda x: f"{int(x)} m²" if pd.notna(x) else "—"
                    ),
                    "Hab.": df_chollos["habitaciones"].apply(
                        lambda x: str(int(x)) if pd.notna(x) else "—"
                    ),
                    "€/m²": df_chollos["pm2"].apply(lambda x: f"{int(x):,} €".replace(",", ".")),
                    "Ver": df_chollos["url"].fillna(""),
                })
                col_cfg_ch = {
                    "":     st.column_config.TextColumn("", width="small"),
                    "Zona": st.column_config.TextColumn("Zona", width="medium"),
                    "Precio": st.column_config.TextColumn("Precio", width="small"),
                    "m²":   st.column_config.TextColumn("m²", width="small"),
                    "Hab.": st.column_config.TextColumn("Hab.", width="small"),
                    "€/m²": st.column_config.TextColumn("€/m²", width="small"),
                    "Ver":  st.column_config.LinkColumn("Ver", display_text="Abrir ↗", width="small"),
                }
                st.dataframe(tbl, use_container_width=True, hide_index=True,
                             height=(len(tbl) + 1) * 36 + 4, column_config=col_cfg_ch)
            else:
                st.info("No hay chollos detectados con los datos actuales.")
        else:
            _empty_chart("Sin datos suficientes", 200)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Tabla resumen por zona ────────────────────────────────────────────────
    section_hdr("Resumen por zona")
    st.markdown(
        "<p style='color:#8b949e;font-size:12px;margin:-8px 0 12px;'>"
        "Comparativa rápida: desde cuánto puedes comprar en cada zona</p>",
        unsafe_allow_html=True,
    )
    zone_tbl = db.get_price_sqm_by_zone()
    if zone_tbl:
        df_tbl = pd.DataFrame(zone_tbl)
        df_tbl = df_tbl[df_tbl["count"] >= 1].sort_values("avg_precio")

        def _fmtk(v):
            if not v or pd.isna(v): return "—"
            v = int(v)
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M €"
            return f"{v:,} €".replace(",", ".")

        df_tbl["Zona"]         = df_tbl["zona"]
        df_tbl["Anuncios"]     = df_tbl["count"].astype(int)
        df_tbl["Desde"]        = df_tbl["min_precio"].apply(_fmtk)
        df_tbl["Hasta"]        = df_tbl["max_precio"].apply(_fmtk)
        df_tbl["Precio medio"] = df_tbl["avg_precio"].apply(_fmtk)
        df_tbl["Coste / m²"]   = df_tbl["avg_pm2"].apply(
            lambda v: f"{int(v):,} €".replace(",", ".") if v and not pd.isna(v) else "—"
        )

        show_cols = ["Zona", "Anuncios", "Desde", "Hasta", "Precio medio", "Coste / m²"]
        col_cfg_tbl = {
            "Zona":          st.column_config.TextColumn("Zona", width="medium"),
            "Anuncios":      st.column_config.NumberColumn("Anuncios", format="%d", width="small"),
            "Desde":         st.column_config.TextColumn("Desde", width="small"),
            "Hasta":         st.column_config.TextColumn("Hasta", width="small"),
            "Precio medio":  st.column_config.TextColumn("Precio medio", width="small"),
            "Coste / m²":    st.column_config.TextColumn("Coste / m²", width="small"),
        }
        tbl_h = (len(df_tbl) + 1) * 36 + 4
        st.dataframe(df_tbl[show_cols], use_container_width=True, hide_index=True,
                     height=tbl_h, column_config=col_cfg_tbl)


def page_scraping():
    st.markdown(
        "<h1>Scraping</h1>"
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:20px;'>"
        "Ejecuta el scraper manualmente</p>",
        unsafe_allow_html=True,
    )

    sites = db.get_enabled_sites()
    site_names = {s["id"]: s["name"] for s in sites}

    with st.expander("Configuración", expanded=True):
        c_a, c_b = st.columns([3, 1])
        with c_a:
            selected_names = st.multiselect(
                "Sitios a scrapear",
                options=list(site_names.values()),
                default=list(site_names.values())[:5],
                placeholder="Selecciona sitios…",
            )
            selected_ids = [sid for sid, name in site_names.items() if name in selected_names]
        with c_b:
            st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
            run_btn = st.button("▶  Ejecutar", type="primary", use_container_width=True)

    if run_btn:
        if not selected_ids:
            st.warning("Selecciona al menos un sitio.")
        else:
            prog = st.progress(0)
            status_ph = st.empty()

            def on_progress(done, total, name):
                prog.progress(done / max(total, 1))
                status_ph.markdown(
                    f"<span style='color:#6e7b95;font-size:12px;'>"
                    f"Scraping {done}/{total} – "
                    f"<b style='color:#c9d1d9;'>{name}</b></span>",
                    unsafe_allow_html=True,
                )

            result = scraper.scrape_all_sites(selected_ids, on_progress)
            prog.progress(1.0)
            status_ph.empty()

            found = result["total_found"]
            new   = result["total_new"]
            errs  = result["errors"]

            st.markdown(
                f'<div style="background:#0a1f10;border:1px solid #1a4c28;border-radius:10px;'
                f'padding:18px 22px;margin-top:12px;">'
                f'<div style="font-size:13px;font-weight:700;color:#3fb950;margin-bottom:10px;">'
                f'✓ Completado</div>'
                f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">'
                f'<div><div style="font-size:10px;color:#c9d1d9;text-transform:uppercase;'
                f'letter-spacing:.07em;margin-bottom:4px;">Sitios</div>'
                f'<div style="font-size:1.4rem;font-weight:700;color:#e6edf3;">{result["sites_scraped"]}</div></div>'
                f'<div><div style="font-size:10px;color:#c9d1d9;text-transform:uppercase;'
                f'letter-spacing:.07em;margin-bottom:4px;">Encontrados</div>'
                f'<div style="font-size:1.4rem;font-weight:700;color:#58a6ff;">{found:,}</div></div>'
                f'<div><div style="font-size:10px;color:#c9d1d9;text-transform:uppercase;'
                f'letter-spacing:.07em;margin-bottom:4px;">Nuevos</div>'
                f'<div style="font-size:1.4rem;font-weight:700;color:#3fb950;">{new:,}</div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            if errs:
                with st.expander(f"⚠ {len(errs)} errores"):
                    for e in errs:
                        st.markdown(
                            f"<span style='color:#f85149;font-size:12px;'>• {e}</span>",
                            unsafe_allow_html=True,
                        )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    section_hdr("Historial")

    logs = db.get_recent_logs(50)
    if not logs:
        _empty_chart("Sin historial aún", 100)
        return

    df_l = pd.DataFrame(logs)
    df_l["started_at"] = pd.to_datetime(df_l["started_at"]).dt.strftime("%d/%m/%Y %H:%M")
    df_l["error_msg"]  = df_l["error_msg"].fillna("—").str[:80]

    st.dataframe(
        df_l[[
            "site_name","started_at","status",
            "properties_found","properties_new","error_msg",
        ]].rename(columns={
            "site_name": "Sitio", "started_at": "Inicio", "status": "Estado",
            "properties_found": "Encontrados", "properties_new": "Nuevos",
            "error_msg": "Mensaje",
        }),
        use_container_width=True,
        hide_index=True,
    )


def page_exportar():
    st.markdown(
        "<h1>Exportar</h1>"
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:20px;'>"
        "Descarga los datos en CSV o Excel</p>",
        unsafe_allow_html=True,
    )

    with st.expander("Filtros de exportación", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            zones = db.get_zone_distribution()
            z_opts = [z["zona"] for z in zones if z["zona"]]
            zona_f = st.multiselect("Zona", z_opts, placeholder="Todas")
        with c2:
            portals = db.get_portal_distribution()
            p_opts = [p["portal"] for p in portals]
            portal_f = st.multiselect("Portal", p_opts, placeholder="Todos")
        with c3:
            limite = st.slider("Máximo registros", 100, 10000, 5000, 100)

    props = db.get_properties(
        limit=limite,
        zona=zona_f or None,
        portal=portal_f or None,
    )

    if not props:
        st.info("No hay datos con los filtros actuales.")
        return

    df = pd.DataFrame(props)
    st.markdown(
        f"<p style='color:#c9d1d9;font-size:11px;margin-bottom:14px;'>"
        f"{len(df):,} registros listos para exportar</p>",
        unsafe_allow_html=True,
    )

    c_csv, c_xlsx = st.columns(2)
    with c_csv:
        st.download_button(
            "⬇  Descargar CSV",
            data=df.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"andorra_inmuebles_{datetime.now():%Y%m%d}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
    with c_xlsx:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Inmuebles")
        buf.seek(0)
        st.download_button(
            "⬇  Descargar Excel",
            data=buf.getvalue(),
            file_name=f"andorra_inmuebles_{datetime.now():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="secondary",
            use_container_width=True,
        )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)


def page_ajustes():
    st.markdown(
        "<h1>Ajustes</h1>"
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:24px;'>"
        "Configuración del scraper automático y preferencias</p>",
        unsafe_allow_html=True,
    )

    # ── Programación automática ───────────────────────────────────────────────
    section_hdr("Programación automática")

    current_interval = db.get_setting("schedule_interval", "manual")
    current_time     = db.get_setting("schedule_time", "08:00")
    last_run         = db.get_setting("schedule_last_run", "")
    last_result      = db.get_setting("schedule_last_result", "—")
    sched_status     = db.get_setting("schedule_status", "")

    nxt = scheduler.get_next_run()

    # Status card
    status_color = "#3fb950" if sched_status == "ok" else ("#f85149" if sched_status == "error" else "#8b949e")
    status_label = "✓ OK" if sched_status == "ok" else ("✗ Error" if sched_status == "error" else "—")
    last_run_fmt = ""
    if last_run:
        try:
            last_run_fmt = datetime.fromisoformat(last_run).strftime("%d/%m/%Y %H:%M")
        except Exception:
            last_run_fmt = last_run

    nxt_fmt = nxt.strftime("%d/%m/%Y %H:%M") if nxt else "—  (modo manual)"

    st.markdown(
        f'<div style="background:#161b27;border:1px solid #21273a;border-radius:12px;'
        f'padding:20px 24px;margin-bottom:20px;display:grid;'
        f'grid-template-columns:repeat(4,1fr);gap:16px;">'
        f'<div><div style="font-size:10px;color:#8b949e;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:4px;">Estado</div>'
        f'<div style="font-size:1.1rem;font-weight:700;color:{status_color};">{status_label}</div></div>'
        f'<div><div style="font-size:10px;color:#8b949e;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:4px;">Último scraping</div>'
        f'<div style="font-size:0.9rem;font-weight:600;color:#e6edf3;">{last_run_fmt or "Nunca"}</div></div>'
        f'<div><div style="font-size:10px;color:#8b949e;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:4px;">Próxima ejecución</div>'
        f'<div style="font-size:0.9rem;font-weight:600;color:#58a6ff;">{nxt_fmt}</div></div>'
        f'<div><div style="font-size:10px;color:#8b949e;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:4px;">Resultado</div>'
        f'<div style="font-size:0.75rem;color:#c9d1d9;">{last_result[:80]}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Config form
    with st.form("schedule_form"):
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            interval_opts = list(scheduler.INTERVAL_LABELS.keys())
            interval_labels = list(scheduler.INTERVAL_LABELS.values())
            sel_idx = interval_opts.index(current_interval) if current_interval in interval_opts else 0
            new_interval = st.selectbox(
                "Frecuencia de scraping automático",
                options=interval_opts,
                index=sel_idx,
                format_func=lambda k: scheduler.INTERVAL_LABELS[k],
            )
        with sc2:
            new_time = st.text_input(
                "Hora de ejecución (HH:MM)",
                value=current_time,
                help="Hora local en la que se ejecutará el scraper cada día/intervalo",
            )

        save_btn = st.form_submit_button("💾  Guardar configuración", type="primary")

    if save_btn:
        # Validate time
        import re as _re
        if not _re.match(r"^\d{2}:\d{2}$", new_time.strip()):
            st.error("Formato de hora incorrecto. Usa HH:MM (p.ej. 08:00)")
        else:
            db.set_setting("schedule_interval", new_interval)
            db.set_setting("schedule_time", new_time.strip())
            st.success(
                f"✓ Programación guardada: {scheduler.INTERVAL_LABELS[new_interval]}"
                + (f" a las {new_time}" if new_interval != 'manual' else "")
            )
            st.rerun()

    if new_interval == "manual":
        st.info("ℹ️  Modo manual: el scraper solo se ejecuta desde la página Scraping.")
    else:
        st.markdown(
            f"<p style='color:#c9d1d9;font-size:12px;margin-top:4px;'>"
            f"ℹ️  El scraper se ejecutará automáticamente mientras la aplicación esté abierta. "
            f"Para scraping sin abrir la app, configura un cron job.</p>",
            unsafe_allow_html=True,
        )

    # ── Cron helper ───────────────────────────────────────────────────────────
    with st.expander("⚙️  Configurar cron job (scraping sin abrir la app)"):
        import sys
        python_path = sys.executable
        app_dir = str(Path(__file__).parent)
        cron_examples = {
            "1":  f"0 8 * * *",
            "2":  f"0 8 */2 * *",
            "3":  f"0 8 */3 * *",
            "7":  f"0 8 * * 1",
            "14": f"0 8 1,15 * *",
        }
        cron_expr = cron_examples.get(current_interval, "0 8 * * *")
        cron_cmd = f'{cron_expr}  cd {app_dir} && {python_path} -c "import scraper, db; db.init_db(); scraper.scrape_all_sites()" >> {app_dir}/scraping.log 2>&1'
        st.markdown(
            "<p style='color:#c9d1d9;font-size:12px;'>Añade esta línea a tu crontab "
            "(<code>crontab -e</code>) para ejecutar el scraper sin abrir la app:</p>",
            unsafe_allow_html=True,
        )
        st.code(cron_cmd, language="bash")

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Proxy HTTP ────────────────────────────────────────────────────────────
    section_hdr("Proxy HTTP (para Idealista)")

    st.markdown(
        "<p style='color:#c9d1d9;font-size:12px;margin-bottom:12px;'>"
        "Idealista bloquea IPs de Andorra. Configura un proxy con IP española para desbloquearlo.<br>"
        "Formato: <code>http://usuario:contraseña@host:puerto</code> "
        "o <code>http://host:puerto</code> si no requiere autenticación.</p>",
        unsafe_allow_html=True,
    )

    current_proxy_url     = db.get_setting("proxy_url", "")
    current_proxy_enabled = db.get_setting("proxy_enabled", "0") == "1"

    with st.form("proxy_form"):
        px1, px2 = st.columns([3, 1])
        with px1:
            new_proxy_url = st.text_input(
                "URL del proxy",
                value=current_proxy_url,
                placeholder="http://usuario:contraseña@proxy.es:8080",
            )
        with px2:
            new_proxy_enabled = st.checkbox("Activar proxy", value=current_proxy_enabled)

        pc1, pc2 = st.columns([1, 1])
        with pc1:
            save_proxy = st.form_submit_button("💾  Guardar proxy", type="primary")
        with pc2:
            test_proxy_btn = st.form_submit_button("🔌  Probar conexión")

    if save_proxy:
        db.set_setting("proxy_url", new_proxy_url.strip())
        db.set_setting("proxy_enabled", "1" if new_proxy_enabled else "0")
        if new_proxy_url.strip() and new_proxy_enabled:
            db.toggle_site("idealista-andorra", True)
            st.success("✓ Proxy guardado. Idealista activado automáticamente.")
        elif not new_proxy_enabled:
            st.success("✓ Proxy desactivado.")
        else:
            st.success("✓ Proxy guardado.")
        st.rerun()

    if test_proxy_btn:
        url_to_test = new_proxy_url.strip() or current_proxy_url
        if not url_to_test:
            st.error("Introduce una URL de proxy antes de probar.")
        else:
            with st.spinner("Probando proxy…"):
                result = scraper.test_proxy(url_to_test)
            if result["ok"]:
                flag = "🇪🇸" if result["country"] == "ES" else ("🇦🇩" if result["country"] == "AD" else "🌍")
                idealista_msg = "✅ Idealista accesible" if result["idealista"] else "⚠️ Proxy funciona pero Idealista sigue bloqueado (IP no española)"
                st.success(
                    f"{flag} Proxy OK — IP: `{result['ip']}` | "
                    f"País: {result['country']} {result['city']} | {idealista_msg}"
                )
            else:
                st.error(f"❌ Error al conectar con el proxy: {result['error']}")

    if current_proxy_url and current_proxy_enabled:
        st.markdown(
            f"<div style='background:#0f2a1a;border:1px solid #196027;border-radius:8px;"
            f"padding:10px 14px;font-size:12px;color:#3fb950;margin-top:8px;'>"
            f"🟢 Proxy activo: <code>{current_proxy_url[:70]}{'…' if len(current_proxy_url)>70 else ''}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
    elif current_proxy_url and not current_proxy_enabled:
        st.markdown(
            "<div style='background:#1a1a1a;border:1px solid #30363d;border-radius:8px;"
            "padding:10px 14px;font-size:12px;color:#8b949e;margin-top:8px;'>"
            "⚪ Proxy configurado pero desactivado"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── DB info ───────────────────────────────────────────────────────────────
    section_hdr("Información de la base de datos")
    total_p = db.get_total_properties()
    total_s = len(db.get_sites())
    total_l = len(db.get_recent_logs(9999))
    db_path = Path(__file__).parent / "data" / "realestate.db"
    db_size = f"{db_path.stat().st_size / 1024:.1f} KB" if db_path.exists() else "—"

    info_cols = st.columns(4)
    for col, (lbl, val) in zip(info_cols, [
        ("Inmuebles", f"{total_p:,}"),
        ("Sitios", f"{total_s:,}"),
        ("Logs scraping", f"{total_l:,}"),
        ("Tamaño BD", db_size),
    ]):
        col.markdown(
            f'<div style="background:#161b27;border:1px solid #21273a;border-radius:8px;'
            f'padding:14px 16px;">'
            f'<div style="font-size:10px;color:#8b949e;text-transform:uppercase;'
            f'letter-spacing:.07em;margin-bottom:4px;">{lbl}</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:#e6edf3;">{val}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    with st.expander("⚠️  Zona de peligro"):
        st.warning("Las siguientes acciones son irreversibles.")
        c_del1, c_del2 = st.columns(2)
        with c_del1:
            if st.button("🗑  Borrar todos los logs", type="secondary", use_container_width=True):
                with db.get_conn() as conn:
                    conn.execute("DELETE FROM scrape_logs")
                st.success("Logs eliminados.")
                st.rerun()
        with c_del2:
            confirm = st.text_input("Escribe BORRAR para eliminar todos los inmuebles")
            if st.button("🗑  Borrar todos los inmuebles", type="secondary", use_container_width=True):
                if confirm == "BORRAR":
                    with db.get_conn() as conn:
                        conn.execute("DELETE FROM properties")
                    st.success("Todos los inmuebles eliminados.")
                    st.rerun()
                else:
                    st.error("Escribe exactamente BORRAR para confirmar.")


# ─── Router ──────────────────────────────────────────────────────────────────

PAGES = {
    "Dashboard": page_dashboard,
    "Sitios":    page_sitios,
    "Inmuebles": page_inmuebles,
    "Análisis":  page_analisis,
    "Scraping":  page_scraping,
    "Exportar":  page_exportar,
    "Ajustes":   page_ajustes,
}
PAGES.get(page, page_dashboard)()
