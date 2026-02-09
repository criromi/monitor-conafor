import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import plotly.express as px
import plotly.graph_objects as go 
from branca.element import MacroElement, Template
import base64
from io import BytesIO
import zipfile
import tempfile
from datetime import datetime 

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Monitor CONAFOR", page_icon="🌲")

# 🎨 COLORES INSTITUCIONALES
COLOR_PRIMARIO = "#13322B"      # Verde Oscuro Gobierno
COLOR_SECUNDARIO = "#9D2449"    # Guinda Institucional
COLOR_ACENTO = "#DDC9A3"        # Dorado

# RUTA ABSOLUTA
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# 📋 CATALOGO MAESTRO
# ==============================================================================
CATALOGO_CAPAS = {
    "PSA": {"nombre": "Servicios Ambientales", "color_mapa": "#28a745", "color_chart": COLOR_PRIMARIO},
    "PFC": {"nombre": "Plantaciones Forestales", "color_mapa": "#ffc107", "color_chart": COLOR_SECUNDARIO},
    "MFC": {"nombre": "Manejo Forestal", "color_mapa": "#17a2b8", "color_chart": COLOR_ACENTO},
    "CUSTF": {"nombre": "Compensación Ambiental", "color_mapa": "#ca520c", "color_chart": "#962121"}
}

# ==============================================================================
# 🎨 ESTILOS CSS
# ==============================================================================
st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    
    /* Estilos Generales */
    div[data-testid="column"] {{
        background-color: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    
    /* Pestañas */
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        height: 45px; white-space: pre-wrap; background-color: white;
        border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 8px; padding-bottom: 8px;
        border: 1px solid #ddd; border-bottom: none; font-size: 0.9rem;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold;
    }}

    /* Títulos y Métricas */
    .section-header {{
        color: {COLOR_PRIMARIO}; font-weight: 800; text-transform: uppercase;
        border-bottom: 3px solid {COLOR_ACENTO}; padding-bottom: 5px; margin-bottom: 20px; font-size: 1rem;
    }}
    .metric-container {{
        background-color: #F8F9FA; border-radius: 8px; padding: 10px;
        margin-bottom: 8px; text-align: center; border: 1px solid #eee;
    }}
    .metric-value {{ font-size: 1.2rem; font-weight: 800; color: {COLOR_PRIMARIO}; margin: 2px 0; }}
    .metric-value-total {{ font-size: 1.4rem; font-weight: 900; color: {COLOR_SECUNDARIO}; margin: 2px 0; }}
    
    /* Botón Discreto de Impresión */
    div[data-testid="stVerticalBlock"] > div:first-child {{
        padding-top: 0px;
    }}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🔐 LOGIN
# ==============================================================================
if 'rol' not in st.session_state: st.session_state.rol = None

if st.session_state.rol is None:
    ruta_logo = None
    posibles = ["logo 25 ani_conafor.png", "logo 25 ani_conafor.jpg", "logo 25 ani_conafor.jpeg"]
    for nombre in posibles:
        path = os.path.join(BASE_DIR, "logos", nombre)
        if os.path.exists(path):
            ruta_logo = path
            break

    col_izq, col_login, col_der = st.columns([1, 1, 1])
    with col_login:
        st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
        if ruta_logo: st.image(ruta_logo, use_container_width=True)
        else: st.markdown("<h1 style='text-align:center;'>🌲</h1>", unsafe_allow_html=True)
        st.markdown(f"""
            <h2 style='text-align: center; color: {COLOR_SECUNDARIO}; font-size: 1.2rem; margin-bottom: 5px;'>MONITOR DE PROYECTOS</h2>
            <p style='text-align: center; color: {COLOR_PRIMARIO}; font-size: 2.2rem; margin-bottom: 5px;'>Cuenca Lerma-Santiago</p>
        """, unsafe_allow_html=True)
        password = st.text_input("Código de Acceso", type="password", placeholder="Contraseña")
        if st.button("INGRESAR"):
            if password == "conafor2026":
                st.session_state.rol = "usuario"
                st.rerun()
            elif password == "admin2026":
                st.session_state.rol = "admin"
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop() 

# ==============================================================================
# 🛠️ MODO ADMINISTRADOR
# ==============================================================================
modo_edicion_activo = False
if st.session_state.rol == "admin":
    with st.sidebar:
        st.header("🔧 Panel Administrador")
        seleccion = st.radio("Acciones:", ["👁️ Ver Monitor", "📤 Subir/Actualizar Capas"])
        if seleccion == "📤 Subir/Actualizar Capas": modo_edicion_activo = True
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.rol = None
            st.rerun()

if modo_edicion_activo:
    st.title("🛠️ Gestión de Datos")
    st.info("Panel de carga de archivos activo.")
    st.stop()

# ==============================================================================
# 📡 CARGA DE DATOS
# ==============================================================================
@st.cache_data(ttl=60) 
def cargar_datos():
    carpeta_datos = 'datos_web'
    ruta_datos_abs = os.path.join(BASE_DIR, carpeta_datos)
    ruta_cuenca = os.path.join(ruta_datos_abs, 'cuenca_web.parquet')
    
    gdfs_lista = []
    for capa in CATALOGO_CAPAS.keys():
        ruta = os.path.join(ruta_datos_abs, f"capa_{capa}_procesada.parquet")
        if os.path.exists(ruta):
            try:
                g = gpd.read_parquet(ruta)
                if g.crs and g.crs.to_string() != "EPSG:4326": g = g.to_crs("EPSG:4326")
                if 'TIPO_CAPA' not in g.columns: g['TIPO_CAPA'] = capa
                gdfs_lista.append(g)
            except: pass
            
    if gdfs_lista:
        gdf = pd.concat(gdfs_lista, ignore_index=True)
    else:
        ruta_master = os.path.join(ruta_datos_abs, 'db_master.parquet')
        gdf = gpd.read_parquet(ruta_master) if os.path.exists(ruta_master) else None

    if gdf is not None:
        cols_text = ['FOL_PROG', 'MUNICIPIO', 'TIPO_CAPA', 'TIPO_PROP', 'CONCEPTO', 'ESTADO', 'SOLICITANT', 'GERENCIA']
        for c in cols_text:
            if c in gdf.columns: gdf[c] = gdf[c].astype(str)
        
        col_anio = next((c for c in gdf.columns if any(x in c.upper() for x in ['ANIO', 'AÑO', 'EJERCICIO', 'YEAR'])), None)
        if col_anio: gdf.rename(columns={col_anio: 'ANIO'}, inplace=True)
        else: gdf['ANIO'] = 0

        for col in ['MONTO_CNF', 'MONTO_PI', 'MONTO_TOT', 'SUPERFICIE', 'ANIO']:
            if col not in gdf.columns: gdf[col] = 0.0
            else: gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0)

    cuenca = gpd.read_parquet(ruta_cuenca) if os.path.exists(ruta_cuenca) else None
    return gdf, cuenca

df_total, cuenca = cargar_datos()
if df_total is None:
    st.info("Sin datos cargados.")
    st.stop()

# ==============================================================================
# 🏗️ GENERADOR DE REPORTE COMPLETO (CORREGIDO)
# ==============================================================================
def generar_reporte_completo_html(df_raw, map_html, figuras_html, logo_b64):
    """
    Recibe df_raw (con columnas originales como MONTO_TOT) para cálculos,
    y luego renombra internamente para mostrar la tabla bonita.
    """
    # 1. Cálculos de KPIs usando nombres originales
    m_tot = df_raw['MONTO_TOT'].sum() if 'MONTO_TOT' in df_raw.columns else 0
    s_tot = df_raw['SUPERFICIE'].sum() if 'SUPERFICIE' in df_raw.columns else 0
    n_proy = len(df_raw)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 2. Preparar Tabla Visual (Renombrar aquí)
    CONFIG_RENOMBRE = {
        "FOL_PROG": "FOLIO", "ESTADO": "ESTADO", "MUNICIPIO": "MUNICIPIO", 
        "SOLICITANT": "BENEFICIARIO", "TIPO_PROP": "REGIMEN", "CONCEPTO": "CONCEPTO", 
        "SUPERFICIE": "SUP (HA)", "MONTO_TOT": "TOTAL", "ANIO": "EJERCICIO"
    }
    cols_ok = [c for c in CONFIG_RENOMBRE.keys() if c in df_raw.columns]
    df_visual = df_raw[cols_ok].rename(columns=CONFIG_RENOMBRE)

    # 3. Estilos CSS
    css = f"""
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        .page-break {{ page-break-before: always; }}
        .header {{ border-bottom: 4px solid {COLOR_ACENTO}; padding-bottom: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
        .titulo {{ font-size: 28px; font-weight: bold; color: {COLOR_SECUNDARIO}; margin: 0; }}
        .subtitulo {{ font-size: 16px; color: {COLOR_PRIMARIO}; font-weight: bold; }}
        
        /* KPIs */
        .kpi-row {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .kpi-card {{ flex: 1; background: #f4f4f4; padding: 15px; border-left: 6px solid {COLOR_PRIMARIO}; text-align: center; }}
        .kpi-val {{ font-size: 24px; font-weight: bold; color: {COLOR_PRIMARIO}; display: block; }}
        .kpi-lbl {{ font-size: 12px; text-transform: uppercase; color: #666; }}
        
        /* Mapa */
        .map-container {{ width: 100%; height: 500px; border: 1px solid #ccc; margin-bottom: 20px; }}
        
        /* Gráficos */
        .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .chart-full {{ width: 100%; margin-bottom: 20px; }}
        
        /* Tabla */
        table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
        th {{ background-color: {COLOR_PRIMARIO}; color: white; padding: 5px; text-align: left; }}
        td {{ border-bottom: 1px solid #ddd; padding: 5px; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        
        @media print {{
            .no-print {{ display: none; }}
            body {{ -webkit-print-color-adjust: exact; }}
        }}
    </style>
    """
    
    logo_img = f'<img src="data:image/png;base64,{logo_b64}" height="60">' if logo_b64 else ''
    
    # 4. Construcción del HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>{css}</head>
    <body>
        <div class="no-print" style="position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border: 1px solid #ccc; z-index: 9999;">
            <button onclick="window.print()" style="background: {COLOR_PRIMARIO}; color: white; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer;">🖨️ IMPRIMIR A PDF</button>
            <div style="font-size: 10px; color: #666; margin-top: 5px;">* Activa "Gráficos de fondo" en opciones de impresión</div>
        </div>

        <div class="header">
            <div>
                <div class="titulo">REPORTE INTEGRAL DE PROYECTOS</div>
                <div class="subtitulo">CUENCA LERMA-SANTIAGO | CONAFOR</div>
                <div style="font-size: 12px; margin-top: 5px;">Generado el: {fecha}</div>
            </div>
            {logo_img}
        </div>

        <div class="kpi-row">
            <div class="kpi-card"><span class="kpi-lbl">Inversión Total</span><span class="kpi-val">${m_tot:,.2f}</span></div>
            <div class="kpi-card"><span class="kpi-lbl">Superficie</span><span class="kpi-val">{s_tot:,.2f} ha</span></div>
            <div class="kpi-card"><span class="kpi-lbl">Proyectos</span><span class="kpi-val">{n_proy}</span></div>
        </div>

        <h3>📍 Ubicación Geográfica</h3>
        <div class="map-container">
            {map_html}
        </div>
        
        <div class="page-break"></div>
        <div class="header">
            <div class="titulo">ANÁLISIS ESTADÍSTICO</div>
            {logo_img}
        </div>
        
        <div class="chart-full">{figuras_html.get('linea', '')}</div>
        
        <div class="chart-grid">
            <div>{figuras_html.get('barras', '')}</div>
            <div>{figuras_html.get('muni', '')}</div>
            <div>{figuras_html.get('pastel', '')}</div>
            <div>{figuras_html.get('concepto', '')}</div>
        </div>

        <div class="page-break"></div>
        <div class="header">
            <div class="titulo">DETALLE DE DATOS</div>
            {logo_img}
        </div>
        
        {df_visual.to_html(index=False, border=0)}
        
    </body>
    </html>
    """
    return html.encode('utf-8')

# ==============================================================================
# 🏁 HEADER PRINCIPAL Y BOTÓN DISCRETO
# ==============================================================================
def get_logo():
    for ext in [".png", ".jpg", ".jpeg"]:
        p = os.path.join(BASE_DIR, "logos", "logo 25 ani_conafor" + ext)
        if os.path.exists(p):
            with open(p, "rb") as f: return base64.b64encode(f.read()).decode(), "png" if ext==".png" else "jpeg"
    return None, None

logo_b64, ext_enc = get_logo()

# --- LAYOUT SUPERIOR ---
col_head_tit, col_head_btn = st.columns([9, 1], vertical_alignment="top")

with col_head_tit:
    if logo_b64:
        st.markdown(f"""
        <div style="border-bottom: 4px solid {COLOR_ACENTO}; margin-bottom: 10px; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style='color: {COLOR_SECUNDARIO}; font-family: Arial, sans-serif; font-weight: 800; margin: 0; font-size: 2rem;'>
                    MONITOR DE PROYECTOS <span style='font-weight:300; color:{COLOR_PRIMARIO};'>| CUENCA LERMA-SANTIAGO</span>
                </h1>
                <div style='color: #756f6c; font-size: 0.9rem; font-weight: 600;'>
                    COMISIÓN NACIONAL FORESTAL (CONAFOR)
                </div>
            </div>
            <img src="data:image/{ext_enc};base64,{logo_b64}" style="height: 60px; width: auto;">
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 🧱 LAYOUT 3 COLUMNAS
# ==============================================================================
col_izq, col_centro, col_der = st.columns([1.1, 2.9, 1.4], gap="medium")

# --- 1. FILTROS ---
with col_izq:
    st.markdown('<div class="section-header">🔍 BUSCADOR</div>', unsafe_allow_html=True)
    busqueda = st.text_input("Buscar:", placeholder="Beneficiario, Folio o Municipio...", help="Escribe para filtrar")
    
    st.markdown('<div style="margin-top:15px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">🎛️ CAPAS DISPONIBLES</div>', unsafe_allow_html=True)
    
    capas_activas = []
    for codigo, info in CATALOGO_CAPAS.items():
        if not df_total[df_total['TIPO_CAPA'] == codigo].empty:
            if st.checkbox(info['nombre'], value=True, key=f"chk_{codigo}"):
                capas_activas.append(codigo)

    df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas_activas)].copy()

    if busqueda:
        busqueda = busqueda.upper()
        mask = (df_filtrado['SOLICITANT'].str.upper().str.contains(busqueda, na=False)) | \
               (df_filtrado['FOL_PROG'].str.upper().str.contains(busqueda, na=False)) | \
               (df_filtrado['MUNICIPIO'].str.upper().str.contains(busqueda, na=False))
        df_filtrado = df_filtrado[mask]

# --- 2. MAPA ---
with col_centro:
    try:
        if cuenca is not None:
            b = cuenca.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        elif not df_filtrado.empty:
            b = df_filtrado.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        else:
            clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7
    
    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False, prefer_canvas=True)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite", overlay=False, control=True).add_to(m)
    folium.TileLayer("CartoDB positron", name="Mapa Claro", overlay=False, control=True).add_to(m)
    
    if cuenca is not None:
        folium.GeoJson(
            cuenca, name="Límite de Cuenca", 
            style_function=lambda x: {'fillColor': 'none', 'color': '#FFD700', 'weight': 3, 'dashArray': '10, 5'}
        ).add_to(m)
        try:
            bounds = cuenca.total_bounds
            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        except: pass

    df_mapa = df_filtrado.copy()
    if 'MONTO_TOT' in df_mapa.columns: df_mapa['MONTO_FMT'] = df_mapa['MONTO_TOT'].apply(lambda x: "{:,.2f}".format(x))
    else: df_mapa['MONTO_FMT'] = "0.00"
    
    campos = ['SOLICITANT','FOL_PROG', 'ESTADO', 'MUNICIPIO', 'TIPO_PROP', 'MONTO_FMT', 'CONCEPTO']
    alias = ['BENEFICIARIO: ', 'FOLIO: ', 'ESTADO: ', 'MUNICIPIO: ', 'REGIMEN: ', 'INVERSIÓN: ', 'CONCEPTO: ']
    
    for cod in capas_activas:
        sub = df_mapa[df_mapa['TIPO_CAPA'] == cod]
        if not sub.empty:
            c_mapa = CATALOGO_CAPAS.get(cod, {}).get("color_mapa", "blue")
            folium.GeoJson(
                sub, name=CATALOGO_CAPAS[cod]['nombre'], smooth_factor=2.0,
                style_function=lambda x, c=c_mapa: {'fillColor':c, 'color':'black', 'weight':0.4, 'fillOpacity':0.7},
                tooltip=folium.GeoJsonTooltip(fields=campos, aliases=alias, style="background-color: white; color: #333; font-family: arial; font-size: 10px; padding: 8px;")
            ).add_to(m)

    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    ley_html = "".join([f"<div style='margin-bottom:5px;'><i style='background:{CATALOGO_CAPAS[c]['color_mapa']}; width:10px; height:10px; display:inline-block; margin-right:5px;'></i>{CATALOGO_CAPAS[c]['nombre']}</div>" for c in capas_activas])
    macro = MacroElement()
    macro._template = Template(f"""{{% macro html(this, kwargs) %}}
    <div style="position: fixed; bottom: 30px; right: 30px; background:rgba(255,255,255,0.95); padding:10px; border-radius:5px; border:1px solid #ccc; z-index:999; font-size:11px; font-family:Arial; font-weight:bold;">
        {ley_html}
    </div>{{% endmacro %}}""")
    m.get_root().add_child(macro)
    st_folium(m, width="100%", height=550, returned_objects=[])

# --- 3. TARJETAS KPI ---
with col_der:
    monto_cnf = df_filtrado['MONTO_CNF'].sum()
    monto_pi = df_filtrado['MONTO_PI'].sum()
    monto_tot = df_filtrado['MONTO_TOT'].sum()
    col_sup = next((c for c in df_filtrado.columns if c.upper() in ['SUPERFICIE', 'SUP_HA', 'HECTAREAS', 'HA']), None)
    sup_tot = df_filtrado[col_sup].sum() if col_sup else 0
    num_proy = df_filtrado['FOL_PROG'].nunique()

    st.markdown('<div class="section-header">💰 INVERSIÓN (MXN)</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">CONAFOR vs PARTE INTERESADA</div>
        <div class="metric-value">${monto_cnf:,.0f}</div>
        <div style="font-size: 0.8rem; color: #666; font-weight:bold;">+ ${monto_pi:,.0f} (Part.)</div>
    </div>
    <div class="metric-container" style="border-left: 5px solid {COLOR_SECUNDARIO}; background:white;">
        <div class="metric-label">TOTAL EJERCIDO</div>
        <div class="metric-value-total">${monto_tot:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top: 25px;">🌲 AVANCE FÍSICO</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">Superficie Total</div>
        <div class="metric-value" style="color:{COLOR_PRIMARIO}; font-size:1.4rem;">{sup_tot:,.1f} ha</div>
    </div>
    <div class="metric-container">
        <div class="metric-label">PROYECTOS APOYADOS</div>
        <span style="font-size:1.6rem; font-weight:bold; color:{COLOR_PRIMARIO};">{num_proy}</span>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 📊 PREPARACIÓN DE GRÁFICOS (PARA REPORTE)
# ==============================================================================
figs_reporte = {} 

if not df_filtrado.empty:
    # 1. LÍNEA
    d_anio = df_filtrado.groupby('ANIO')['MONTO_TOT'].sum().reset_index().sort_values('ANIO')
    d_anio = d_anio[d_anio['ANIO'] > 0]
    fig_linea = px.line(d_anio, x='ANIO', y='MONTO_TOT', markers=True, color_discrete_sequence=[COLOR_SECUNDARIO], labels={'MONTO_TOT': 'MONTO', 'ANIO': 'AÑO'}, title="Evolución Histórica")
    fig_linea.update_traces(line=dict(width=3), marker=dict(size=8, color=COLOR_PRIMARIO))
    fig_linea.update_layout(height=300, margin=dict(t=30,b=10))
    figs_reporte['linea'] = fig_linea.to_html(full_html=False, include_plotlyjs='cdn')

    # 2. BARRAS PROGRAMA
    d_prog = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
    colors = [CATALOGO_CAPAS.get(c, {}).get('color_chart', 'grey') for c in d_prog['TIPO_CAPA']]
    fig_bar = go.Figure(data=[go.Bar(x=d_prog['TIPO_CAPA'], y=d_prog['MONTO_TOT'], text=d_prog['MONTO_TOT'], texttemplate='$%{text:.2s}', marker_color=colors)])
    fig_bar.update_layout(title="Inversión por Programa", height=250, margin=dict(t=30,b=10))
    figs_reporte['barras'] = fig_bar.to_html(full_html=False, include_plotlyjs='cdn')

    # 3. MUNICIPIOS
    d_mun = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
    fig_mun = px.bar(d_mun, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', color_discrete_sequence=[COLOR_PRIMARIO], title="Top Municipios")
    fig_mun.update_layout(height=250, margin=dict(t=30,b=10))
    figs_reporte['muni'] = fig_mun.to_html(full_html=False, include_plotlyjs='cdn')

    # 4. PASTEL
    d_reg = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
    fig_pie = px.pie(d_reg, values='MONTO_TOT', names='TIPO_PROP', hole=0.5, color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO], title="Régimen")
    fig_pie.update_layout(height=250, margin=dict(t=30,b=10))
    figs_reporte['pastel'] = fig_pie.to_html(full_html=False, include_plotlyjs='cdn')

    # 5. CONCEPTOS
    d_con = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
    d_con['C'] = d_con['CONCEPTO'].apply(lambda x: x[:25]+'...' if len(x)>25 else x)
    fig_con = px.bar(d_con, y='C', x='MONTO_TOT', orientation='h', color_discrete_sequence=[COLOR_SECUNDARIO], title="Conceptos")
    fig_con.update_layout(height=250, margin=dict(t=30,b=10))
    figs_reporte['concepto'] = fig_con.to_html(full_html=False, include_plotlyjs='cdn')

# ==============================================================================
# 🖨️ BOTÓN "DISIMULADO" EN HEADER
# ==============================================================================
with col_head_btn:
    st.write("") 
    if not df_filtrado.empty:
        map_html = m.get_root().render()
        
        # FIX: Pasamos df_filtrado DIRECTAMENTE (con las columnas originales)
        html_reporte = generar_reporte_completo_html(df_filtrado, map_html, figs_reporte, logo_b64)
        
        st.download_button(
            label="🖨️",
            data=html_reporte,
            file_name=f"Proyecto_Cuenca_{datetime.now().strftime('%Y%m%d')}.html",
            mime="text/html",
            help="Descargar Proyecto Completo para Imprimir (Mapa + Gráficos + Tablas)",
            use_container_width=True
        )

# ==============================================================================
# 📑 PESTAÑAS VISUALES (UI)
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)
tab_graficos, tab_tabla = st.tabs(["📊 DASHBOARD GRÁFICO", "📑 BASE DE DATOS DETALLADA"])

with tab_graficos:
    if not df_filtrado.empty:
        with st.container(border=True):
            st.plotly_chart(fig_linea, use_container_width=True, config={'displayModeBar': False})
        
        c1, c2 = st.columns(2)
        with c1: 
            with st.container(border=True): st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
        with c2: 
            with st.container(border=True): st.plotly_chart(fig_mun, use_container_width=True, config={'displayModeBar': False})
            
        c3, c4 = st.columns(2)
        with c3: 
            with st.container(border=True): st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        with c4: 
            with st.container(border=True): st.plotly_chart(fig_con, use_container_width=True, config={'displayModeBar': False})

with tab_tabla:
    c_tit, c_btns = st.columns([5, 2])
    with c_tit: st.subheader("📑 Detalle de Apoyos")
    
    CONFIG_COLUMNAS = {"FOL_PROG": "FOLIO", "ESTADO": "ESTADO", "MUNICIPIO": "MUNICIPIO", "SOLICITANT": "BENEFICIARIO", "TIPO_PROP": "REGIMEN", "CONCEPTO": "CONCEPTO", "SUPERFICIE": "SUP (HA)", "MONTO_TOT": "TOTAL", "ANIO": "EJERCICIO"}
    cols_presentes = [c for c in CONFIG_COLUMNAS.keys() if c in df_filtrado.columns]
    df_tabla = df_filtrado[cols_presentes].rename(columns=CONFIG_COLUMNAS)

    def generar_excel(df):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df.to_excel(w, index=False)
        return out.getvalue()
        
    def generar_shp(gdf):
        with tempfile.TemporaryDirectory() as td:
            gdf.to_file(os.path.join(td, "Proyectos.shp"))
            mem = BytesIO()
            with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
                for r, d, f in os.walk(td):
                    for file in f: z.write(os.path.join(r, file), file)
            return mem.getvalue()

    with c_btns:
        b1, b2 = st.columns(2)
        with b1: st.download_button("📥 Excel", generar_excel(df_tabla), "Datos.xlsx", "application/vnd.ms-excel")
        with b2: st.download_button("🌍 Shape", generar_shp(df_filtrado), "Mapa.zip", "application/zip")

    st.dataframe(
        df_tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            "TOTAL": st.column_config.NumberColumn(format="$ %.2f"),
            "SUP (HA)": st.column_config.NumberColumn(format="%.2f ha"),
            "EJERCICIO": st.column_config.NumberColumn(format="%d"),
            "BENEFICIARIO": st.column_config.TextColumn(width="large"),
        }
    )