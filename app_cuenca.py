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
import shutil
from datetime import datetime 

# Intentamos importar el backend de admin si existe
try:
    import backend_admin
except ImportError:
    backend_admin = None

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
# 🎨 ESTILOS CSS (INTERFAZ WEB)
# ==============================================================================
st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    
    div[data-testid="column"] {{
        background-color: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        height: 45px; white-space: pre-wrap; background-color: white;
        border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 8px; padding-bottom: 8px;
        border: 1px solid #ddd; border-bottom: none; font-size: 0.9rem;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold;
    }}

    .section-header {{
        color: {COLOR_PRIMARIO}; font-weight: 800; text-transform: uppercase;
        border-bottom: 3px solid {COLOR_ACENTO}; padding-bottom: 5px; margin-bottom: 20px; font-size: 1rem;
    }}
    .chart-title {{
        font-size: 0.85rem; font-weight: bold; color: {COLOR_PRIMARIO};
        text-align: center; margin-top: 2px; margin-bottom: 2px; border-bottom: 1px solid #eee; padding-bottom: 2px;
    }}
    
    .metric-container {{
        background-color: #F8F9FA; border-radius: 8px; padding: 10px;
        margin-bottom: 8px; text-align: center; border: 1px solid #eee;
    }}
    .metric-value {{ font-size: 1.2rem; font-weight: 800; color: {COLOR_PRIMARIO}; margin: 2px 0; }}
    .metric-value-total {{ font-size: 1.4rem; font-weight: 900; color: {COLOR_SECUNDARIO}; margin: 2px 0; }}
    
    div[data-testid="stVerticalBlock"] > div:first-child {{
        padding-top: 0px;
    }}
    div.stButton > button {{ width: 100%; }}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🔐 LOGIN
# ==============================================================================
if 'rol' not in st.session_state:
    st.session_state.rol = None

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
        st.markdown("---")
        with st.expander("⚙️ Opciones Avanzadas"):
            if st.button("🔄 Forzar Recarga"):
                st.cache_data.clear()
                st.rerun()
        if seleccion == "📤 Subir/Actualizar Capas":
            modo_edicion_activo = True
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.rol = None
            st.rerun()

if modo_edicion_activo:
    st.title("🛠️ Gestión de Datos - Multidependencia")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.subheader("1. Selección")
        opciones = list(CATALOGO_CAPAS.keys())
        capa_sel = st.selectbox("Capa:", opciones)
        up_zip = st.file_uploader("Shapefile (.zip)", type="zip")
        up_csv = st.file_uploader("Base de Datos (.csv/xlsx)", type=["csv", "xlsx"])
    with col_up2:
        st.subheader("2. Procesamiento")
        if st.button("🚀 PROCESAR CAPA", type="primary"):
            if up_zip:
                with st.spinner("Procesando..."):
                    try:
                        if backend_admin is None:
                            st.error("Error: backend_admin no encontrado.")
                        else:
                            df_ex = None
                            if up_csv:
                                df_ex = pd.read_csv(up_csv, encoding='latin-1') if up_csv.name.endswith('.csv') else pd.read_excel(up_csv)
                            
                            gdf_res, msg = backend_admin.procesar_zip_upload(up_zip, capa_sel, df_ex)
                            
                            if gdf_res is not None:
                                os.makedirs("datos_web", exist_ok=True)
                                gdf_res.to_parquet(os.path.join("datos_web", f"capa_{capa_sel}_procesada.parquet"))
                                st.cache_data.clear()
                                st.success("✅ ¡Capa procesada exitosamente!")
                            else: st.error(msg)
                    except Exception as e: st.error(f"Error: {e}")
            else: st.warning("Sube el ZIP.")
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
    st.info("⚠️ No hay datos cargados.")
    st.stop()

# ==============================================================================
# 🏗️ GENERADOR DE REPORTE COMPLETO (SINTAXIS CORREGIDA)
# ==============================================================================
def generar_reporte_completo_html(df_raw, map_html, figuras_html, logo_b64):
    # 1. Cálculos de TODOS los KPIs
    m_cnf = df_raw['MONTO_CNF'].sum() if 'MONTO_CNF' in df_raw.columns else 0
    m_pi = df_raw['MONTO_PI'].sum() if 'MONTO_PI' in df_raw.columns else 0
    m_tot = df_raw['MONTO_TOT'].sum() if 'MONTO_TOT' in df_raw.columns else 0
    s_tot = df_raw['SUPERFICIE'].sum() if 'SUPERFICIE' in df_raw.columns else 0
    n_proy = len(df_raw)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 2. Renombrar para Tabla Visual
    CONFIG_RENOMBRE = {
        "FOL_PROG": "FOLIO", "ESTADO": "ESTADO", "MUNICIPIO": "MUNICIPIO", 
        "SOLICITANT": "BENEFICIARIO", "TIPO_PROP": "REGIMEN", "CONCEPTO": "CONCEPTO", 
        "SUPERFICIE": "SUP (HA)", "MONTO_TOT": "TOTAL", "ANIO": "EJERCICIO"
    }
    cols_ok = [c for c in CONFIG_RENOMBRE.keys() if c in df_raw.columns]
    df_visual = df_raw[cols_ok].rename(columns=CONFIG_RENOMBRE)

    # 3. Escapar mapa
    map_srcdoc = map_html.replace('"', '&quot;')

    # 4. CSS DISEÑO PROFESIONAL (DOBLES LLAVES PARA ESCAPAR f-strings)
    css = f"""
    <style>
        @page {{ size: letter portrait; margin: 1cm; }}
        body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; color: #333; background: #fff; }}
        .page-break {{ page-break-before: always; }}
        .no-print {{ display: none; }}

        /* HEADER */
        .header {{ border-bottom: 3px solid {COLOR_ACENTO}; padding-bottom: 15px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }}
        .titulo {{ font-size: 32px; font-weight: 900; color: {COLOR_SECUNDARIO}; margin: 0; text-transform: uppercase; letter-spacing: 1px; }}
        .subtitulo {{ font-size: 18px; color: {COLOR_PRIMARIO}; font-weight: 600; margin-top: 5px; }}
        .meta-info {{ font-size: 12px; color: #666; margin-top: 10px; }}
        
        /* KPIs IMPACTANTES */
        .kpi-section {{ margin-bottom: 30px; }}
        .kpi-grid-top {{ display: grid; grid-template-columns: 1fr 1fr 1.2fr; gap: 20px; margin-bottom: 20px; }}
        .kpi-grid-bot {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        
        .kpi-card {{
            background: #fff;
            padding: 25px 20px;
            border-radius: 12px;
            box-shadow: 0 6px 15px rgba(0,0,0,0.08);
            text-align: center;
            border-bottom: 5px solid {COLOR_PRIMARIO};
            transition: all 0.3s ease;
        }}
        
        .kpi-card.highlight {{
            background: {COLOR_PRIMARIO};
            border-bottom-color: {COLOR_ACENTO};
        }}
        /* Nota: highlight usa color blanco forzado en etiquetas hijas */
        .kpi-card.highlight .kpi-lbl, .kpi-card.highlight .kpi-val {{ color: #fff !important; }}

        .kpi-val {{ font-size: 26px; font-weight: 800; color: {COLOR_PRIMARIO}; display: block; margin-bottom: 5px; }}
        .kpi-lbl {{ font-size: 13px; text-transform: uppercase; color: #777; font-weight: 700; letter-spacing: 0.5px; }}
        
        /* MAPA GRANDE */
        .map-wrapper {{
            width: 100%;
            height: 65vh;
            min-height: 600px;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .map-wrapper iframe {{ width: 100%; height: 100%; border: none; }}

        /* GRÁFICOS */
        .section-title {{ font-size: 24px; font-weight: bold; color: {COLOR_PRIMARIO}; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #eee; }}
        
        .chart-container-full {{
            width: 100%;
            background: #fff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            margin-bottom: 30px;
        }}
        
        .chart-grid-2up {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}
        
        .chart-item {{
            background: #fff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            height: 380px;
            display: flex; align-items: center; justify-content: center;
        }}

        /* TABLA */
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: 10px; border: 1px solid #eee; border-radius: 8px; overflow: hidden; }}
        th {{ background-color: {COLOR_PRIMARIO}; color: white; padding: 10px; text-align: left; font-weight: 600; }}
        td {{ border-bottom: 1px solid #eee; padding: 8px; }}
        tr:nth-child(even) {{ background-color: #f8f9fa; }}
        
        /* Botón flotante */
        .floating-print-btn {{
            position: fixed; top: 20px; right: 20px; z-index: 9999;
            background: {COLOR_PRIMARIO}; color: white; border: none;
            padding: 12px 25px; font-weight: bold; border-radius: 30px;
            cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: background 0.2s;
        }}
        .floating-print-btn:hover {{ background: {COLOR_SECUNDARIO}; }}
    </style>
    """
    
    logo_img = f'<img src="data:image/png;base64,{logo_b64}" height="70">' if logo_b64 else ''
    
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte CONAFOR</title>
        {css}
    </head>
    <body>
        <button class="floating-print-btn no-print" onclick="window.print()">🖨️ IMPRIMIR REPORTE PDF</button>

        <div class="header">
            <div>
                <div class="titulo">REPORTE EJECUTIVO DE PROYECTOS</div>
                <div class="subtitulo">CUENCA LERMA-SANTIAGO | CONAFOR</div>
                <div class="meta-info">Fecha de corte: {fecha}</div>
            </div>
            {logo_img}
        </div>

        <div class="kpi-section">
            <div class="kpi-grid-top">
                <div class="kpi-card">
                    <span class="kpi-lbl">Aportación CONAFOR</span>
                    <span class="kpi-val">${m_cnf:,.2f}</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-lbl">Aportación Socios</span>
                    <span class="kpi-val">${m_pi:,.2f}</span>
                </div>
                <div class="kpi-card highlight">
                    <span class="kpi-lbl">INVERSIÓN TOTAL EJERCIDA</span>
                    <span class="kpi-val" style="font-size: 32px;">${m_tot:,.2f}</span>
                </div>
            </div>
            <div class="kpi-grid-bot">
                <div class="kpi-card" style="border-bottom-color: {COLOR_SECUNDARIO};">
                    <span class="kpi-lbl">Superficie Total Apoyada</span>
                    <span class="kpi-val">{s_tot:,.2f} ha</span>
                </div>
                <div class="kpi-card" style="border-bottom-color: {COLOR_SECUNDARIO};">
                    <span class="kpi-lbl">Total de Proyectos</span>
                    <span class="kpi-val">{n_proy}</span>
                </div>
            </div>
        </div>

        <div class="section-title">📍 Ubicación Geográfica de Proyectos</div>
        <div class="map-wrapper">
            <iframe srcdoc="{map_srcdoc}"></iframe>
        </div>
        
        <div class="page-break"></div>
        <div class="header">
            <div class="titulo">ANÁLISIS ESTADÍSTICO</div>
            {logo_img}
        </div>
        
        <div class="chart-container-full">
            {figuras_html.get('linea', '')}
        </div>
        
        <div class="chart-grid-2up">
            <div class="chart-item">{figuras_html.get('barras', '')}</div>
            <div class="chart-item">{figuras_html.get('muni', '')}</div>
        </div>
        <div class="chart-grid-2up">
            <div class="chart-item">{figuras_html.get('pastel', '')}</div>
            <div class="chart-item">{figuras_html.get('concepto', '')}</div>
        </div>

        <div class="page-break"></div>
        <div class="header">
            <div class="titulo">DETALLE DE DATOS</div>
            {logo_img}
        </div>
        <div style="overflow-x: auto;">
            {df_visual.to_html(index=False, border=0, classes='table')}
        </div>
    </body>
    </html>
    """
    return html.encode('utf-8')

# ==============================================================================
# 🏁 HEADER PRINCIPAL
# ==============================================================================
def get_logo():
    for ext in [".png", ".jpg", ".jpeg"]:
        p = os.path.join(BASE_DIR, "logos", "logo 25 ani_conafor" + ext)
        if os.path.exists(p):
            with open(p, "rb") as f: return base64.b64encode(f.read()).decode(), "png" if ext==".png" else "jpeg"
    return None, None

logo_b64, ext_enc = get_logo()

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

# --- 2. MAPA (PANTALLA) ---
with col_centro:
    try:
        if cuenca is not None:
            b = cuenca.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        elif not df_filtrado.empty:
            b = df_filtrado.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        else: clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7
    
    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False, prefer_canvas=True)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite", overlay=False, control=True).add_to(m)
    folium.TileLayer("CartoDB positron", name="Mapa Claro", overlay=False, control=True).add_to(m)
    
    if cuenca is not None:
        folium.GeoJson(cuenca, name="Límite de Cuenca", style_function=lambda x: {'fillColor': 'none', 'color': '#FFD700', 'weight': 3, 'dashArray': '10, 5'}).add_to(m)
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
    <div style="position: fixed; bottom: 30px; right: 30px; background:rgba(255,255,255,0.95); padding:10px; border-radius:5px; border:1px solid #ccc; z-index:999; font-size:11px; font-family:Arial; font-weight:bold;">{ley_html}</div>{{% endmacro %}}""")
    m.get_root().add_child(macro)
    st_folium(m, width="100%", height=550, returned_objects=[])

# --- 3. TARJETAS KPI (PANTALLA) ---
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
# 📊 GRÁFICOS PARA REPORTE (ALTURA AJUSTADA PARA TARJETAS)
# ==============================================================================
figs_reporte = {}
if not df_filtrado.empty:
    # Altura estándar para los gráficos dentro de las tarjetas del reporte
    REPORT_CHART_HEIGHT = 340

    d_anio = df_filtrado.groupby('ANIO')['MONTO_TOT'].sum().reset_index().sort_values('ANIO')
    d_anio = d_anio[d_anio['ANIO'] > 0]
    fig_linea = px.line(d_anio, x='ANIO', y='MONTO_TOT', markers=True, color_discrete_sequence=[COLOR_SECUNDARIO], labels={'MONTO_TOT': 'MONTO', 'ANIO': 'AÑO'}, title="Evolución Histórica de la Inversión")
    fig_linea.update_traces(line=dict(width=4), marker=dict(size=10, color=COLOR_PRIMARIO))
    fig_linea.update_layout(height=REPORT_CHART_HEIGHT, margin=dict(t=40,b=20,l=20,r=20), plot_bgcolor='rgba(0,0,0,0)')
    figs_reporte['linea'] = fig_linea.to_html(full_html=False, include_plotlyjs='cdn')

    d_prog = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
    colors = [CATALOGO_CAPAS.get(c, {}).get('color_chart', 'grey') for c in d_prog['TIPO_CAPA']]
    fig_bar = go.Figure(data=[go.Bar(x=d_prog['TIPO_CAPA'], y=d_prog['MONTO_TOT'], text=d_prog['MONTO_TOT'], texttemplate='$%{text:.2s}', marker_color=colors)])
    fig_bar.update_layout(title="Inversión por Programa", height=REPORT_CHART_HEIGHT, margin=dict(t=40,b=20,l=20,r=20), plot_bgcolor='rgba(0,0,0,0)')
    figs_reporte['barras'] = fig_bar.to_html(full_html=False, include_plotlyjs='cdn')

    d_mun = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
    fig_mun = px.bar(d_mun, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', color_discrete_sequence=[COLOR_PRIMARIO], title="Top 10 Municipios por Inversión")
    fig_mun.update_layout(height=REPORT_CHART_HEIGHT, margin=dict(t=40,b=20,l=20,r=20), plot_bgcolor='rgba(0,0,0,0)')
    figs_reporte['muni'] = fig_mun.to_html(full_html=False, include_plotlyjs='cdn')

    d_reg = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
    fig_pie = px.pie(d_reg, values='MONTO_TOT', names='TIPO_PROP', hole=0.6, color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO], title="Distribución por Régimen de Propiedad")
    fig_pie.update_layout(height=REPORT_CHART_HEIGHT, margin=dict(t=40,b=20,l=20,r=20))
    figs_reporte['pastel'] = fig_pie.to_html(full_html=False, include_plotlyjs='cdn')

    d_con = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
    d_con['C'] = d_con['CONCEPTO'].apply(lambda x: x[:30]+'...' if len(x)>30 else x)
    fig_con = px.bar(d_con, y='C', x='MONTO_TOT', orientation='h', color_discrete_sequence=[COLOR_SECUNDARIO], title="Top 10 Conceptos de Apoyo", text_auto='.2s')
    fig_con.update_layout(height=REPORT_CHART_HEIGHT, margin=dict(t=40,b=20,l=20,r=20), plot_bgcolor='rgba(0,0,0,0)', yaxis_title=None)
    figs_reporte['concepto'] = fig_con.to_html(full_html=False, include_plotlyjs='cdn')

# ==============================================================================
# 🖨️ BOTÓN HEADER
# ==============================================================================
with col_head_btn:
    st.write("") 
    if not df_filtrado.empty:
        map_html = m.get_root().render()
        html_reporte = generar_reporte_completo_html(df_filtrado, map_html, figs_reporte, logo_b64)
        st.download_button("🖨️", html_reporte, f"Reporte_CONAFOR_{datetime.now().strftime('%Y%m%d')}.html", "text/html", use_container_width=True, help="Descargar Reporte Ejecutivo para Imprimir")

# ==============================================================================
# 📑 PESTAÑAS (UI PANTALLA)
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)
tab_graficos, tab_tabla = st.tabs(["📊 GRÁFICOS", "📑 BASE DE DATOS"])

with tab_graficos:
    if not df_filtrado.empty:
        with st.container(border=True): st.plotly_chart(fig_linea, use_container_width=True, config={'displayModeBar': False})
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

    st.dataframe(df_tabla, use_container_width=True, hide_index=True, column_config={"TOTAL": st.column_config.NumberColumn(format="$ %.2f"), "SUP (HA)": st.column_config.NumberColumn(format="%.2f ha"), "EJERCICIO": st.column_config.NumberColumn(format="%d")})