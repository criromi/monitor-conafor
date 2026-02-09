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

# Intento de importar el backend para modo admin
try:
    import backend_admin
except ImportError:
    pass 

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Monitor CONAFOR", page_icon="🌲")

# 🎨 COLORES INSTITUCIONALES
COLOR_PRIMARIO = "#13322B"      # Verde Oscuro Gobierno
COLOR_SECUNDARIO = "#9D2449"    # Guinda Institucional
COLOR_ACENTO = "#DDC9A3"        # Dorado
COLOR_FONDO = "#F5F5F5"

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
# 🎨 ESTILOS CSS PERSONALIZADOS
# ==============================================================================
st.markdown(f"""
    <style>
    /* Estilo General */
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    
    /* Tarjetas de Métricas */
    div[data-testid="metric-container"] {{
        background-color: white;
        border: 1px solid #e0e0e0;
        padding: 10px;
        border-radius: 8px;
        border-left: 5px solid {COLOR_PRIMARIO};
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}

    /* Pestañas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        height: 50px; white-space: pre-wrap; background-color: white;
        border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px;
        border: 1px solid #ddd; border-bottom: none;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold;
    }}

    /* Títulos de Secciones */
    .sub-header {{
        color: {COLOR_PRIMARIO}; font-size: 1.2rem; font-weight: 800;
        border-bottom: 2px solid {COLOR_ACENTO}; margin-bottom: 15px; padding-bottom: 5px;
    }}
    
    /* Botones */
    div.stButton > button {{
        background-color: {COLOR_PRIMARIO} !important; color: white !important;
        border-radius: 6px !important; font-weight: bold !important;
    }}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🔐 SISTEMA DE SEGURIDAD Y LOGIN (COMPLETO)
# ==============================================================================
if 'rol' not in st.session_state:
    st.session_state.rol = None

if st.session_state.rol is None:
    # Búsqueda robusta del logo
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
# 🛠️ MODO ADMINISTRADOR (COMPLETO)
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
    st.markdown("⚠️ **IMPORTANTE:** Al procesar, descarga el archivo `.parquet` y súbelo manualmente a GitHub.")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.subheader("1. Selección")
        opciones = list(CATALOGO_CAPAS.keys())
        capa_sel = st.selectbox("Capa a actualizar:", opciones, format_func=lambda x: f"{x} - {CATALOGO_CAPAS[x]['nombre']}")
        up_zip = st.file_uploader("Shapefile (.zip)", type="zip")
        up_csv = st.file_uploader("Base de Datos (.csv/xlsx)", type=["csv", "xlsx"])
    with col_up2:
        st.subheader("2. Procesamiento")
        if st.button("🚀 PROCESAR CAPA", type="primary"):
            if up_zip:
                with st.spinner("Procesando..."):
                    try:
                        import backend_admin
                        df_ex = None
                        if up_csv:
                            if up_csv.name.endswith('.csv'):
                                try:
                                    df_ex = pd.read_csv(up_csv, encoding='utf-8')
                                except UnicodeDecodeError:
                                    up_csv.seek(0)
                                    df_ex = pd.read_csv(up_csv, encoding='latin-1')
                            else:
                                df_ex = pd.read_excel(up_csv)
                                
                        gdf_res, msg = backend_admin.procesar_zip_upload(up_zip, capa_sel, df_ex)
                        
                        if gdf_res is not None:
                            os.makedirs("datos_web", exist_ok=True)
                            nombre_archivo = f"capa_{capa_sel}_procesada.parquet"
                            ruta_salida = os.path.join("datos_web", nombre_archivo)
                            gdf_res.to_parquet(ruta_salida)
                            
                            st.cache_data.clear()
                            st.success(f"✅ ¡Capa {capa_sel} procesada!")
                            
                            with open(ruta_salida, "rb") as f:
                                st.download_button(
                                    label=f"💾 DESCARGAR {nombre_archivo}",
                                    data=f,
                                    file_name=nombre_archivo,
                                    mime="application/octet-stream",
                                    type="secondary"
                                )
                            st.info(f"👆 Descarga este archivo y súbelo a GitHub.")
                        else: st.error(msg)
                    except Exception as e: st.error(f"Error: {e}")
            else: st.warning("Sube el archivo ZIP.")
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
        # Normalización
        cols_text = ['FOL_PROG', 'MUNICIPIO', 'TIPO_CAPA', 'TIPO_PROP', 'CONCEPTO', 'ESTADO', 'SOLICITANT', 'GERENCIA']
        for c in cols_text:
            if c in gdf.columns: gdf[c] = gdf[c].astype(str)
        
        # Detectar Año
        col_anio = next((c for c in gdf.columns if any(x in c.upper() for x in ['ANIO', 'AÑO', 'EJERCICIO', 'YEAR'])), None)
        if col_anio: gdf.rename(columns={col_anio: 'ANIO'}, inplace=True)
        else: gdf['ANIO'] = 0

        # Numéricos
        for col in ['MONTO_CNF', 'MONTO_PI', 'MONTO_TOT', 'SUPERFICIE', 'ANIO']:
            if col not in gdf.columns: gdf[col] = 0.0
            else: gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0)

    cuenca = gpd.read_parquet(ruta_cuenca) if os.path.exists(ruta_cuenca) else None
    return gdf, cuenca

df_total, cuenca = cargar_datos()
if df_total is None:
    st.info("⚠️ No hay datos cargados. Sube capas en el panel Admin.")
    st.stop()

# ==============================================================================
# 🏁 HEADER & KPI SUPERIOR
# ==============================================================================
# Header con Logo
def get_logo():
    for ext in [".png", ".jpg", ".jpeg"]:
        p = os.path.join(BASE_DIR, "logos", "logo 25 ani_conafor" + ext)
        if os.path.exists(p):
            with open(p, "rb") as f: return base64.b64encode(f.read()).decode(), "png" if ext==".png" else "jpeg"
    return None, None

logo_b64, ext_enc = get_logo()
if logo_b64:
    header_html = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; padding-bottom:10px; border-bottom:4px solid {COLOR_ACENTO};">
        <div>
            <h1 style='color:{COLOR_SECUNDARIO}; font-size:2rem; margin:0;'>MONITOR DE PROYECTOS</h1>
            <h3 style='color:{COLOR_PRIMARIO}; font-size:1.2rem; margin:0;'>CUENCA LERMA-SANTIAGO</h3>
        </div>
        <img src="data:image/{ext_enc};base64,{logo_b64}" style="height:60px;">
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

# FILTROS
col_filtro1, col_filtro2, col_filtro3 = st.columns([2, 1, 1])
with col_filtro1:
    busqueda = st.text_input("🔍 Buscar:", placeholder="Beneficiario, Folio o Municipio...")
with col_filtro2:
    st.write("") # Espacio
    st.caption("Filtro por Capas:")
with col_filtro3:
    st.write("") # Espacio
    capas_activas = []
    # Checkbox compactos
    cols_chk = st.columns(len(CATALOGO_CAPAS))
    for i, (cod, info) in enumerate(CATALOGO_CAPAS.items()):
        if not df_total[df_total['TIPO_CAPA'] == cod].empty:
            if cols_chk[i].checkbox(cod, value=True, help=info['nombre']):
                capas_activas.append(cod)

# LÓGICA DE FILTRADO
df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas_activas)].copy()
if busqueda:
    b = busqueda.upper()
    mask = (df_filtrado['SOLICITANT'].str.upper().str.contains(b, na=False)) | \
           (df_filtrado['FOL_PROG'].str.upper().str.contains(b, na=False)) | \
           (df_filtrado['MUNICIPIO'].str.upper().str.contains(b, na=False))
    df_filtrado = df_filtrado[mask]

# MÉTRICAS GLOBALES (BARRA SUPERIOR)
m_tot = df_filtrado['MONTO_TOT'].sum()
m_cnf = df_filtrado['MONTO_CNF'].sum()
col_sup = next((c for c in df_filtrado.columns if c.upper() in ['SUPERFICIE', 'SUP_HA', 'HECTAREAS', 'HA']), None)
s_tot = df_filtrado[col_sup].sum() if col_sup else 0
n_proy = df_filtrado['FOL_PROG'].nunique()

st.markdown("<br>", unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)
k1.metric("INVERSIÓN TOTAL", f"${m_tot:,.0f}")
k2.metric("APORTACIÓN CONAFOR", f"${m_cnf:,.0f}")
k3.metric("SUPERFICIE (HA)", f"{s_tot:,.1f}")
k4.metric("PROYECTOS", f"{n_proy}")

st.markdown("---")

# ==============================================================================
# 🗺️ SECCIÓN PRINCIPAL: MAPA
# ==============================================================================
col_mapa_main = st.container()

with col_mapa_main:
    # Centrado del Mapa
    try:
        if cuenca is not None and not busqueda:
            b = cuenca.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        elif not df_filtrado.empty:
            b = df_filtrado.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 9
        else: clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7

    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False)
    folium.TileLayer("CartoDB positron", name="Mapa Base").add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Satélite").add_to(m)

    # Capa Cuenca
    if cuenca is not None:
        folium.GeoJson(cuenca, style_function=lambda x: {'fillColor':'none','color':'#333','weight':2,'dashArray':'5,5'}).add_to(m)

    # Capas Proyectos
    df_mapa = df_filtrado.copy()
    df_mapa['MONTO_FMT'] = df_mapa['MONTO_TOT'].apply(lambda x: f"${x:,.2f}")
    
    campos = ['SOLICITANT','FOL_PROG', 'ESTADO', 'MUNICIPIO', 'TIPO_PROP', 'MONTO_FMT', 'CONCEPTO']
    alias = ['BENEFICIARIO: ', 'FOLIO: ', 'ESTADO: ', 'MUNICIPIO: ', 'REGIMEN: ', 'INVERSIÓN: ', 'CONCEPTO: ']

    for cod in capas_activas:
        sub = df_mapa[df_mapa['TIPO_CAPA'] == cod]
        if not sub.empty:
            color = CATALOGO_CAPAS.get(cod, {}).get("color_mapa", "blue")
            folium.GeoJson(
                sub,
                name=CATALOGO_CAPAS[cod]['nombre'],
                style_function=lambda x, c=color: {'fillColor':c, 'color':'black', 'weight':0.5, 'fillOpacity':0.7},
                tooltip=folium.GeoJsonTooltip(fields=campos, aliases=alias)
            ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, height=550, use_container_width=True)

# ==============================================================================
# 📑 SECCIÓN INFERIOR: PESTAÑAS (GRÁFICOS vs TABLA)
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)

tab_graficos, tab_tabla = st.tabs(["📊 DASHBOARD GRÁFICO", "📑 BASE DE DATOS DETALLADA"])

# --- PESTAÑA 1: GRÁFICOS ---
with tab_graficos:
    st.markdown('<div class="sub-header">Análisis Estadístico</div>', unsafe_allow_html=True)
    
    # Fila 1 de Gráficos
    g_col1, g_col2 = st.columns(2)
    
    with g_col1:
        st.write("**Inversión por Programa**")
        d = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
        colors = [CATALOGO_CAPAS.get(c, {}).get('color_chart', 'grey') for c in d['TIPO_CAPA']]
        
        fig = go.Figure(data=[go.Bar(
            x=d['TIPO_CAPA'], y=d['MONTO_TOT'],
            text=d['MONTO_TOT'], texttemplate='$%{text:.2s}', textposition='auto',
            marker_color=colors
        )])
        fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    with g_col2:
        if 'MUNICIPIO' in df_filtrado.columns:
            st.write("**Top 10 Municipios (Inversión)**")
            d = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            fig = px.bar(d, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', color_discrete_sequence=[COLOR_PRIMARIO])
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    # Fila 2 de Gráficos
    g_col3, g_col4 = st.columns(2)
    
    with g_col3:
        if 'TIPO_PROP' in df_filtrado.columns:
            st.write("**Tenencia de la Tierra**")
            d = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
            fig = px.pie(d, values='MONTO_TOT', names='TIPO_PROP', hole=0.4, 
                         color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO])
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
            
    with g_col4:
        if 'CONCEPTO' in df_filtrado.columns:
            st.write("**Top Conceptos de Apoyo**")
            d = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(8, 'MONTO_TOT')
            d['CONCEPTO'] = d['CONCEPTO'].apply(lambda x: x[:40]+"..." if len(x)>40 else x)
            fig = px.bar(d, y='CONCEPTO', x='MONTO_TOT', orientation='h', color_discrete_sequence=[COLOR_SECUNDARIO])
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

# --- PESTAÑA 2: TABLA ---
with tab_tabla:
    col_t1, col_t2 = st.columns([5, 1])
    with col_t1:
        st.markdown('<div class="sub-header">Relación de Apoyos</div>', unsafe_allow_html=True)
    
    # Configuración de Columnas para Tabla
    CONFIG_COLS = {
        "FOL_PROG": "FOLIO", "ESTADO": "ESTADO", "MUNICIPIO": "MUNICIPIO",
        "SOLICITANT": "BENEFICIARIO", "TIPO_PROP": "REGIMEN", "CONCEPTO": "CONCEPTO",
        "SUPERFICIE": "SUP (HA)", "MONTO_TOT": "TOTAL", "ANIO": "AÑO"
    }
    
    cols_ok = [c for c in CONFIG_COLS.keys() if c in df_filtrado.columns]
    df_t = df_filtrado[cols_ok].rename(columns=CONFIG_COLS)

    # Botón Descarga
    def to_excel(df):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Reporte')
            writer.sheets['Reporte'].set_column(0, len(df.columns), 20)
        return out.getvalue()

    with col_t2:
        st.download_button(
            "📥 Descargar Excel",
            data=to_excel(df_t),
            file_name="Reporte_Cuenca.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

    # Tabla Estilizada
    st.dataframe(
        df_t,
        use_container_width=True,
        hide_index=True,
        column_config={
            "TOTAL": st.column_config.NumberColumn(format="$ %.2f"),
            "SUP (HA)": st.column_config.NumberColumn(format="%.2f ha"),
            "AÑO": st.column_config.NumberColumn(format="%d"),
            "BENEFICIARIO": st.column_config.TextColumn(width="large"),
        }
    )