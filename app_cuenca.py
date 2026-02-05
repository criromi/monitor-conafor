import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import plotly.express as px
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

# ==============================================================================
# 📋 CATALOGO MAESTRO INTELIGENTE
# ==============================================================================
CATALOGO_CAPAS = {
    "PSA": {
        "nombre": "Servicios Ambientales", 
        "color_mapa": "#28a745",       
        "color_chart": COLOR_PRIMARIO  
    },
    "PFC": {
        "nombre": "Plantaciones Forestales", 
        "color_mapa": "#ffc107",       
        "color_chart": COLOR_SECUNDARIO 
    },
    "MFC": {
        "nombre": "Manejo Forestal", 
        "color_mapa": "#17a2b8",       
        "color_chart": COLOR_ACENTO    
    },
    "CUST": { # Ejemplo que tenías en la imagen
        "nombre": "Compensación Ambiental", 
        "color_mapa": "#ca520c", 
        "color_chart": "#6f42c1"
    }
}

# ==============================================================================
# 🔐 SISTEMA DE SEGURIDAD
# ==============================================================================
if 'rol' not in st.session_state:
    st.session_state.rol = None

if st.session_state.rol is None:
    ruta_logo = None
    posibles = ["logo 25 ani_conafor.png", "logo 25 ani_conafor.jpg", "logo 25 ani_conafor.jpeg"]
    for nombre in posibles:
        path = os.path.join("logos", nombre)
        if os.path.exists(path):
            ruta_logo = path
            break

    st.markdown(f"""
        <style>
        header, footer {{visibility: hidden;}}
        .stApp {{ background-color: #FFFF; }}
        div[data-testid="column"]:nth-of-type(2) {{
            background-color: white; padding: 2rem 3rem; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-top: 6px solid {COLOR_PRIMARIO};
        }}
        div.stButton > button {{
            background-color: {COLOR_PRIMARIO} !important; color: white !important;
            width: 100%; border-radius: 6px !important; font-weight: bold !important;
            padding: 0.6rem !important;
        }}
        </style>
    """, unsafe_allow_html=True)

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
        capa_sel = st.selectbox("Capa a actualizar:", opciones, format_func=lambda x: f"{x} - {CATALOGO_CAPAS[x]['nombre']}")
        up_zip = st.file_uploader("Shapefile (.zip)", type="zip")
        up_csv = st.file_uploader("Base de Datos (.csv/xlsx)", type=["csv", "xlsx"])
    with col_up2:
        st.subheader("2. Procesamiento")
        if st.button("🚀 PROCESAR Y GUARDAR", type="primary"):
            if up_zip:
                with st.spinner("Procesando..."):
                    try:
                        import backend_admin
                        df_ex = None
                        if up_csv:
                            # Corrección UTF-8 / Latin-1
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
                            gdf_res.to_parquet(os.path.join("datos_web", f"capa_{capa_sel}_procesada.parquet"))
                            st.cache_data.clear()
                            st.success(f"✅ ¡{capa_sel} actualizada!")
                        else: st.error(msg)
                    except Exception as e: st.error(f"Error: {e}")
    st.stop()

# ==============================================================================
# 🚀 DASHBOARD
# ==============================================================================

def get_img_as_base64_app(file_path):
    try:
        with open(file_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except Exception: return None

logo_b64 = None
ext_enc = ""
for ext in [".png", ".jpg", ".jpeg"]:
    path = os.path.join("logos", "logo 25 ani_conafor" + ext)
    if os.path.exists(path):
        logo_b64 = get_img_as_base64_app(path)
        ext_enc = "png" if ext == ".png" else "jpeg"
        break

st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    
    div[data-testid="column"]:nth-of-type(1) > div {{
        background-color: white; border-radius: 12px; padding: 20px;
        border: 1px solid #e0e0e0; box-shadow: 0 4px 15px rgba(0,0,0,0.08); height: 100%;
    }}
    div[data-testid="column"]:nth-of-type(2) > div,
    div[data-testid="column"]:nth-of-type(3) > div {{
        background-color: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    div[data-testid="stCheckbox"] label p {{
        font-weight: 700 !important; font-size: 1rem !important; color: #333 !important;
    }}
    .section-header {{
        color: {COLOR_PRIMARIO}; font-weight: 800; text-transform: uppercase;
        border-bottom: 3px solid {COLOR_ACENTO}; padding-bottom: 5px; margin-bottom: 20px; font-size: 1.1rem;
    }}
    .metric-container {{
        background-color: #F8F9FA; border-radius: 8px; padding: 12px;
        margin-bottom: 8px; text-align: center; border: 1px solid #eee;
    }}
    .metric-label {{ font-size: 0.85rem; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
    .metric-value {{ font-size: 1.3rem; font-weight: 800; color: {COLOR_PRIMARIO}; margin: 5px 0; }}
    .metric-value-total {{ font-size: 1.6rem; font-weight: 900; color: {COLOR_SECUNDARIO}; margin: 5px 0; }}
    .chart-title {{
        font-size: 0.9rem; font-weight: bold; color: {COLOR_PRIMARIO};
        text-align: center; margin-top: 20px; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 3px;
    }}
    iframe {{ width: 100% !important; border-radius: 8px; }}
    </style>
""", unsafe_allow_html=True)

if logo_b64:
    st.markdown(f"""
    <div style="border-bottom: 4px solid {COLOR_ACENTO}; margin-bottom: 20px; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style='color: {COLOR_SECUNDARIO}; font-family: Arial, sans-serif; font-weight: 800; margin: 0; font-size: 2.2rem;'>
                MONITOR DE PROYECTOS <span style='font-weight:300; color:{COLOR_PRIMARIO};'>| CUENCA LERMA-SANTIAGO</span>
            </h1>
            <div style='color: #756f6c; font-size: 1rem; margin-top:5px; font-weight: 600;'>
                COMISIÓN NACIONAL FORESTAL <b style="color:#756f6c; font-size: 1.4rem;">(CONAFOR)</b>
            </div>
        </div>
        <img src="data:image/{ext_enc};base64,{logo_b64}" style="height: 70px; width: auto;">
    </div>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=60) 
def cargar_datos():
    carpeta_datos = 'datos_web'
    ruta_cuenca = os.path.join(carpeta_datos, 'cuenca_web.parquet')
    capas_a_cargar = list(CATALOGO_CAPAS.keys())
    gdfs_lista = []
    
    for capa in capas_a_cargar:
        ruta = os.path.join(carpeta_datos, f"capa_{capa}_procesada.parquet")
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
        ruta_master = os.path.join(carpeta_datos, 'db_master.parquet')
        gdf = gpd.read_parquet(ruta_master) if os.path.exists(ruta_master) else None

    if gdf is not None:
        for c in ['FOL_PROG', 'MUNICIPIO', 'TIPO_CAPA', 'TIPO_PROP', 'CONCEPTO', 'ESTADO', 'SOLICITANT']:
            if c in gdf.columns: gdf[c] = gdf[c].astype(str)
        for col in ['MONTO_CNF', 'MONTO_PI', 'MONTO_TOT', 'SUPERFICIE']:
            if col not in gdf.columns: gdf[col] = 0.0
            else: gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0)

    cuenca = gpd.read_parquet(ruta_cuenca) if os.path.exists(ruta_cuenca) else None
    return gdf, cuenca

df_total, cuenca = cargar_datos()
if df_total is None:
    st.info("Sin datos cargados.")
    st.stop()

# --- LAYOUT ---
col_izq, col_centro, col_der = st.columns([1.1, 2.9, 1.4], gap="medium")

# 1. FILTROS
with col_izq:
    st.markdown('<div class="section-header">🎛️ CAPAS DISPONIBLES</div>', unsafe_allow_html=True)
    capas_activas = []
    for codigo, info in CATALOGO_CAPAS.items():
        if not df_total[df_total['TIPO_CAPA'] == codigo].empty:
            if st.checkbox(info['nombre'], value=True, key=f"chk_{codigo}"):
                capas_activas.append(codigo)

# Lógica
df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas_activas)].copy()
df_filtrado['FOL_PROG'] = df_filtrado['FOL_PROG'].astype(str).str.strip()
valores_invalidos = ['nan', 'None', '', 'Sin Dato', 'NAN', 'null']

monto_cnf = df_filtrado['MONTO_CNF'].sum()
monto_pi = df_filtrado['MONTO_PI'].sum()
monto_tot = df_filtrado['MONTO_TOT'].sum()
col_sup = next((c for c in df_filtrado.columns if c.upper() in ['SUPERFICIE', 'SUP_HA', 'HECTAREAS', 'HA']), None)
sup_tot = df_filtrado[col_sup].sum() if col_sup else 0
num_proy = df_filtrado[~df_filtrado['FOL_PROG'].isin(valores_invalidos)]['FOL_PROG'].nunique()

# DESCARGAS
with col_izq:
    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">📥 DESCARGAR DATOS</div>', unsafe_allow_html=True)
    if not df_filtrado.empty:
        nombres = {'FOL_PROG':'FOLIO', 'MONTO_TOT':'INVERSIÓN', 'TIPO_CAPA':'CATEGORÍA', col_sup:'SUPERFICIE'}
        df_ex = df_filtrado.drop(columns='geometry', errors='ignore').rename(columns=nombres)
        buff = BytesIO()
        with pd.ExcelWriter(buff, engine='xlsxwriter') as w: df_ex.to_excel(w, index=False)
        st.download_button("📊 Descargar Tabla (Excel)", buff.getvalue(), "Datos_CONAFOR.xlsx", "application/vnd.ms-excel", use_container_width=True)
        try:
            with tempfile.TemporaryDirectory() as td:
                df_filtrado.to_file(os.path.join(td, "Proy.shp"))
                bz = BytesIO()
                with zipfile.ZipFile(bz, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in os.listdir(td): z.write(os.path.join(td, f), f)
                st.download_button("🌍 Descargar Capa (.zip SHP)", bz.getvalue(), "Capa_CONAFOR.zip", "application/zip", use_container_width=True)
        except: pass

# 2. MAPA (CENTRO) - CORREGIDO PARA CENTRAR CUENCA
with col_centro:
    # Lógica de centrado mejorada: Prioridad a la Cuenca
    try:
        if cuenca is not None:
            # Si hay cuenca, usamos sus límites
            b = cuenca.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        elif not df_filtrado.empty:
            # Si no hay cuenca pero hay puntos, usamos los puntos
            b = df_filtrado.total_bounds
            clat, clon, zoom = (b[1]+b[3])/2, (b[0]+b[2])/2, 8
        else:
            clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7
    
    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False, prefer_canvas=True)
    folium.TileLayer("CartoDB positron", control=False).add_to(m)
    
    # Agregar Cuenca
    if cuenca is not None:
        folium.GeoJson(cuenca, style_function=lambda x: {'fillColor':'none','color':'#555','weight':2,'dashArray':'5,5'}).add_to(m)
        # Forzar ajuste a la cuenca si existe
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

    ley_html = "".join([f"<div style='margin-bottom:5px;'><i style='background:{CATALOGO_CAPAS[c]['color_mapa']}; width:10px; height:10px; display:inline-block; margin-right:5px;'></i>{CATALOGO_CAPAS[c]['nombre']}</div>" for c in capas_activas])
    macro = MacroElement()
    macro._template = Template(f"""
    {{% macro html(this, kwargs) %}}
    <div style="position: fixed; bottom: 30px; right: 30px; background:rgba(255,255,255,0.95); padding:10px; border-radius:5px; border:1px solid #ccc; z-index:999; font-size:11px; font-family:Arial; font-weight:bold;">
        {ley_html}
    </div>
    {{% endmacro %}}""")
    m.get_root().add_child(macro)
    st_folium(m, width="100%", height=600, returned_objects=[])
    
    # Gráficas inferiores (CORREGIDAS ETIQUETAS)
    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if 'MUNICIPIO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Municipios</div>', unsafe_allow_html=True)
            d = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            # FIX: labels
            f = px.bar(d, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', 
                       color_discrete_sequence=[COLOR_PRIMARIO],
                       labels={'MONTO_TOT': 'MONTO TOTAL', 'MUNICIPIO': 'MUNICIPIO'})
            f.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10,b=10))
            st.plotly_chart(f, use_container_width=True, config={'displayModeBar': False})
    with c2:
        if 'CONCEPTO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Conceptos</div>', unsafe_allow_html=True)
            d = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            d['C'] = d['CONCEPTO'].apply(lambda x: x[:30]+'...' if len(x)>30 else x)
            # FIX: labels
            f = px.bar(d, y='C', x='MONTO_TOT', orientation='h', text_auto='.2s', 
                       color_discrete_sequence=[COLOR_SECUNDARIO],
                       labels={'MONTO_TOT': 'MONTO TOTAL', 'C': 'CONCEPTO'})
            f.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10,b=10), yaxis_title="")
            st.plotly_chart(f, use_container_width=True, config={'displayModeBar': False})

# 3. ESTADISTICAS
with col_der:
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
    
    if not df_filtrado.empty:
        st.markdown('<div class="chart-title">Inversión por Dependencia</div>', unsafe_allow_html=True)
        d = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
        color_map_chart = {code: info['color_chart'] for code, info in CATALOGO_CAPAS.items()}
        
        # FIX: labels
        f = px.bar(d, x='TIPO_CAPA', y='MONTO_TOT', color='TIPO_CAPA', 
                   color_discrete_map=color_map_chart, text_auto='.2s',
                   labels={'MONTO_TOT': 'MONTO TOTAL', 'TIPO_CAPA': 'DEPENDENCIA'})
        
        f.update_layout(height=250, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10,b=10))
        st.plotly_chart(f, use_container_width=True, config={'displayModeBar': False})

        if 'TIPO_PROP' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Tenencia de la Tierra</div>', unsafe_allow_html=True)
            d = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
            # FIX: labels
            f = px.pie(d, values='MONTO_TOT', names='TIPO_PROP', hole=0.5, 
                       color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO],
                       labels={'MONTO_TOT': 'MONTO TOTAL', 'TIPO_PROP': 'RÉGIMEN'})
            f.update_layout(height=250, showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10,b=10), legend=dict(orientation="h"))
            st.plotly_chart(f, use_container_width=True, config={'displayModeBar': False})

with st.expander("📋 Ver Base de Datos Completa"):
    st.dataframe(df_filtrado.drop(columns='geometry', errors='ignore'), use_container_width=True)