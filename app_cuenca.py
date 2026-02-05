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
# 📋 CATALOGO MAESTRO DE CAPAS (¡AQUÍ AGREGAS TUS NUEVAS ÁREAS!)
# ==============================================================================
# Formato: "CODIGO_CORTO": {"nombre": "Nombre Largo en Pantalla", "color": "Color Hexadecimal"}
CATALOGO_CAPAS = {
    "PSA": {"nombre": "Servicios Ambientales", "color": "#28a745"},     # Verde
    "PFC": {"nombre": "Plantaciones Forestales", "color": "#ffc107"},   # Amarillo
    "MFC": {"nombre": "Manejo Forestal Comunitario", "color": "#17a2b8"},           # Azul Cian
    "CUSTF": {"nombre": "Compensación Ambiental", "color": "#d63384"},          # Rosa (EJEMPLO NUEVO)
    #"INC": {"nombre": "Incendios", "color": "#fd7e14"},                 # Naranja (EJEMPLO NUEVO)
    #"OTRAS": {"nombre": "Otras Dependencias", "color": "#6f42c1"}       # Morado (EJEMPLO NUEVO)
}

# ==============================================================================
# 🔐 SISTEMA DE SEGURIDAD (DOBLE ROL)
# ==============================================================================
if 'rol' not in st.session_state:
    st.session_state.rol = None

# Si no ha iniciado sesión, mostramos el Login
if st.session_state.rol is None:
    
    # BUSCAR EL LOGO
    ruta_logo = None
    posibles = ["logo 25 ani_conafor.png", "logo 25 ani_conafor.jpg", "logo 25 ani_conafor.jpeg"]
    for nombre in posibles:
        path = os.path.join("logos", nombre)
        if os.path.exists(path):
            ruta_logo = path
            break

    # CSS PARA CENTRAR Y ESTILAR LOGIN
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
        div.stButton > button:hover {{ background-color: {COLOR_SECUNDARIO} !important; }}
        div[data-testid="stTextInput"] input {{ border-radius: 6px; border: 1px solid #ddd; }}
        </style>
    """, unsafe_allow_html=True)

    col_izq, col_login, col_der = st.columns([1, 1, 1])

    with col_login:
        st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
        if ruta_logo: st.image(ruta_logo, use_container_width=True)
        else: st.markdown("<h1 style='text-align:center;'>🌲</h1>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <h2 style='text-align: center; color: {COLOR_SECUNDARIO}; font-size: 1.2rem; margin-bottom: 5px;'>
                MONITOR DE PROYECTOS
            </h2>
            <p style='text-align: center; color: {COLOR_PRIMARIO}; font-size: 2.2rem; margin-bottom: 5px;'>
                Cuenca Lerma-Santiago
            </p>
        """, unsafe_allow_html=True)

        password = st.text_input("Código de Acceso", type="password", placeholder="Contraseña")
        
        if st.button("INGRESAR"):
            if password == "conafor2026":
                st.session_state.rol = "usuario" # ROL VISITANTE
                st.rerun()
            elif password == "admin2026":        # ROL ADMIN
                st.session_state.rol = "admin"
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

        st.markdown("<div style='text-align: center; margin-top: 20px; font-size: 0.7rem; color: #aaa;'>Comisión Nacional Forestal &copy; 2026</div>", unsafe_allow_html=True)
    st.stop() 

# ==============================================================================
# 🛠️ MODO ADMINISTRADOR (PANEL DINÁMICO)
# ==============================================================================
modo_edicion_activo = False

if st.session_state.rol == "admin":
    with st.sidebar:
        st.header("🔧 Panel Administrador")
        st.success("Sesión: Administrador")
        
        seleccion = st.radio("Acciones:", ["👁️ Ver Monitor", "📤 Subir/Actualizar Capas"])
        
        # --- BOTÓN DE EMERGENCIA (SOLO VISIBLE PARA ADMIN) ---
        st.markdown("---")
        with st.expander("⚙️ Opciones Avanzadas"):
            if st.button("🔄 Forzar Recarga (Cache Clear)"):
                st.cache_data.clear()
                st.rerun()
        # -----------------------------------------------------

        if seleccion == "📤 Subir/Actualizar Capas":
            modo_edicion_activo = True
            
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.rol = None
            st.rerun()

# Si está en modo edición, mostramos el panel de carga y DETENEMOS el resto
if modo_edicion_activo:
    st.title("🛠️ Gestión de Datos - Multidependencia")
    st.markdown("Utiliza este panel para actualizar la información.")
    
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        st.subheader("1. Selección de Archivos")
        
        # USAMOS EL CATALOGO MAESTRO PARA EL DROPDOWN
        opciones_capas = list(CATALOGO_CAPAS.keys())
        capa_seleccionada = st.selectbox("Selecciona la capa/área a actualizar:", opciones_capas, format_func=lambda x: f"{x} - {CATALOGO_CAPAS[x]['nombre']}")
        
        uploaded_zip = st.file_uploader("Archivo Shapefile (.zip)", type="zip", help="Debe contener .shp, .shx, .dbf, .prj")
        uploaded_csv = st.file_uploader("Base de Datos Excel/CSV (Opcional)", type=["csv", "xlsx"])

    with col_up2:
        st.subheader("2. Procesamiento")
        st.info(f"Vas a actualizar: **{CATALOGO_CAPAS[capa_seleccionada]['nombre']}**")
        
        if st.button("🚀 PROCESAR Y GUARDAR", type="primary"):
            if uploaded_zip:
                with st.spinner("Procesando archivos..."):
                    try:
                        import backend_admin
                        df_extra = None
                        if uploaded_csv:
                            if uploaded_csv.name.endswith('.csv'): df_extra = pd.read_csv(uploaded_csv)
                            else: df_extra = pd.read_excel(uploaded_csv)
                        
                        # Procesar
                        gdf_result, msg = backend_admin.procesar_zip_upload(uploaded_zip, capa_seleccionada, df_extra)
                        
                        if gdf_result is not None:
                            ruta_out = os.path.join("datos_web", f"capa_{capa_seleccionada}_procesada.parquet")
                            os.makedirs("datos_web", exist_ok=True)
                            gdf_result.to_parquet(ruta_out)
                            
                            st.cache_data.clear() # Limpieza automática al guardar
                            st.success(f"✅ ¡{capa_seleccionada} actualizada con éxito!")
                            st.balloons()
                        else:
                            st.error(f"Error en backend: {msg}")
                    except Exception as e:
                        st.error(f"Error crítico: {e}")
            else:
                st.warning("Falta el archivo ZIP.")
    st.stop() 

# ==============================================================================
# 🚀 APLICACIÓN PRINCIPAL (DASHBOARD)
# ==============================================================================

def get_img_as_base64_app(file_path):
    try:
        with open(file_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except Exception: return None

nombre_logo_app = "logo 25 ani_conafor"
carpeta_logos_app = "logos"
logo_b64_app = None
ext_encontrada_app = ""
for ext in [".png", ".jpg", ".jpeg"]:
    ruta_posible = os.path.join(carpeta_logos_app, nombre_logo_app + ext)
    if os.path.exists(ruta_posible):
        logo_b64_app = get_img_as_base64_app(ruta_posible)
        ext_encontrada_app = "png" if ext == ".png" else "jpeg"
        break

# --- ESTILOS CSS ---
st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    div[data-testid="column"]:nth-of-type(1) > div {{
        background-color: white; border-radius: 12px; padding: 20px;
        border: 1px solid #e0e0e0; box-shadow: 0 4px 15px rgba(0,0,0,0.08); height: 100%;
    }}
    div[data-testid="stCheckbox"] label p {{
        font-weight: 700 !important; font-size: 0.9rem !important; color: #333 !important;
    }}
    div[data-testid="column"]:nth-of-type(2) > div,
    div[data-testid="column"]:nth-of-type(3) > div {{
        background-color: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    .section-header {{
        color: {COLOR_PRIMARIO}; font-weight: 800; text-transform: uppercase;
        border-bottom: 3px solid {COLOR_ACENTO}; padding-bottom: 5px;
        margin-bottom: 20px; font-size: 1.1rem;
    }}
    .metric-container {{
        background-color: #F8F9FA; border-radius: 8px; padding: 12px;
        margin-bottom: 8px; text-align: center; border: 1px solid #eee;
    }}
    .metric-value {{ font-size: 1.2rem; font-weight: 800; color: {COLOR_PRIMARIO}; }}
    .metric-value-total {{ font-size: 1.5rem; font-weight: 900; color: {COLOR_SECUNDARIO}; }}
    .chart-title {{
        font-size: 0.9rem; font-weight: bold; color: {COLOR_PRIMARIO};
        text-align: center; margin-top: 20px; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 3px;
    }}
    iframe {{ width: 100% !important; border-radius: 8px; }}
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
if logo_b64_app:
    html_header = f"""
    <div style="border-bottom: 4px solid {COLOR_ACENTO}; margin-bottom: 20px; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style='color: {COLOR_SECUNDARIO}; font-family: Arial, sans-serif; font-weight: 800; margin: 0; font-size: 2.2rem;'>
                MONITOR DE PROYECTOS <span style='font-weight:300; color:{COLOR_PRIMARIO};'>| CUENCA LERMA-SANTIAGO</span>
            </h1>
            <div style='color: #756f6c; font-size: 1rem; margin-top:5px; font-weight: 600;'>
                COMISIÓN NACIONAL FORESTAL <b style="color:#756f6c; font-size: 1.4rem;">(CONAFOR)</b>
            </div>
        </div>
        <img src="data:image/{ext_encontrada_app};base64,{logo_b64_app}" style="height: 70px; width: auto;">
    </div>
    """
else:
    html_header = f"""
    <div style="border-bottom: 4px solid {COLOR_ACENTO}; margin-bottom: 20px; padding-bottom: 10px;">
        <h1 style='color: {COLOR_SECUNDARIO}; font-family: Arial, sans-serif; font-weight: 800; margin: 0; font-size: 2.2rem;'>
            MONITOR DE PROYECTOS
        </h1>
    </div>
    """
st.markdown(html_header, unsafe_allow_html=True)

# --- CARGA DINÁMICA DE DATOS ---
@st.cache_data(ttl=60) 
def cargar_datos():
    carpeta_datos = 'datos_web'
    ruta_cuenca = os.path.join(carpeta_datos, 'cuenca_web.parquet')
    
    # 🔄 AQUÍ LA MAGIA: CARGAMOS LO QUE ESTÉ EN EL CATÁLOGO
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
        # Fallback master antiguo
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

# Inicializar hora (solo para debug interno)
if 'ultima_actualizacion' not in st.session_state:
    st.session_state.ultima_actualizacion = datetime.now().strftime("%H:%M:%S")

if df_total is None:
    st.info("👋 Hola Admin. El sistema no tiene datos. Sube capas en el menú lateral.")
    st.stop()

# --- LAYOUT ---
col_izq, col_centro, col_der = st.columns([1.1, 2.9, 1.4], gap="medium")

# =========================================================
# 1. CONTROLES DINÁMICOS (IZQUIERDA)
# =========================================================
with col_izq:
    st.markdown('<div class="section-header">🎛️ CAPAS DISPONIBLES</div>', unsafe_allow_html=True)
    
    # 🔄 CREACIÓN AUTOMÁTICA DE CHECKBOXES SEGÚN CATÁLOGO
    capas_activas = []
    for codigo, info in CATALOGO_CAPAS.items():
        # Verificamos si existen datos para esta capa en el dataframe cargado
        existe_en_datos = not df_total[df_total['TIPO_CAPA'] == codigo].empty
        
        # Si existe, mostramos el checkbox
        if existe_en_datos:
            label = f"{info['nombre']}"
            if st.checkbox(label, value=True, key=f"chk_{codigo}"):
                capas_activas.append(codigo)

    st.markdown(f"<p style='text-align:center; font-size:0.7rem; color:gray; margin-top:20px;'>Actualizado: {st.session_state.ultima_actualizacion}</p>", unsafe_allow_html=True)

# Lógica de filtrado
df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas_activas)].copy()

# ==============================================================================
# 🚨 CORRECCIÓN CONTEO + LIMPIEZA
# ==============================================================================
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
        nombres_excel = {
            'FOL_PROG': 'FOLIO', 'SOLICITANT': 'BENEFICIARIO', 'ESTADO': 'ESTADO', 
            'MUNICIPIO': 'MUNICIPIO', 'TIPO_PROP': 'RÉGIMEN', 'TIPO_CAPA': 'CATEGORÍA', 
            'CONCEPTO': 'CONCEPTO', 'MONTO_TOT': 'INVERSIÓN_TOTAL', 
            'MONTO_CNF': 'MONTO_CONAFOR', 'MONTO_PI': 'CONTRAPARTE',
            col_sup: 'SUPERFICIE_HA'
        }
        df_xlsx = df_filtrado.drop(columns=['geometry'], errors='ignore').copy()
        df_xlsx = df_xlsx.rename(columns=nombres_excel)
        cols_exportar = [c for c in nombres_excel.values() if c in df_xlsx.columns]
        
        buffer_excel = BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
            df_xlsx[cols_exportar].to_excel(writer, index=False, sheet_name='Proyectos')
        
        st.download_button("📊 Descargar Tabla (Excel)", data=buffer_excel.getvalue(), file_name="Base_Datos.xlsx", mime="application/vnd.ms-excel", use_container_width=True)

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                ruta_shp = os.path.join(tmp_dir, "Proyectos.shp")
                df_filtrado.to_file(ruta_shp, driver='ESRI Shapefile')
                buffer_zip = BytesIO()
                with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for archivo in os.listdir(tmp_dir): zf.write(os.path.join(tmp_dir, archivo), arcname=archivo)
                buffer_zip.seek(0)
                st.download_button("🌍 Descargar Capa (.zip SHP)", data=buffer_zip, file_name="Proyectos_Shapefile.zip", mime="application/zip", use_container_width=True)
        except Exception as e: st.error(f"Error generando Shapefile: {e}")

# =========================================================
# 2. MAPA (CENTRO)
# =========================================================
with col_centro:
    try:
        if not df_filtrado.empty:
            b = df_filtrado.total_bounds
            clat, clon = (b[1]+b[3])/2, (b[0]+b[2])/2
            zoom = 8
        else: clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7

    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False, prefer_canvas=True)
    folium.TileLayer("CartoDB positron", control=False).add_to(m)

    if cuenca is not None:
        folium.GeoJson(cuenca, name="Cuenca", style_function=lambda x: {'fillColor':'none','color':'#555','weight':2,'dashArray':'5,5'}).add_to(m)
        try:
            bounds = cuenca.total_bounds
            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        except: pass

    df_mapa = df_filtrado.copy()
    if 'MONTO_TOT' in df_mapa.columns: df_mapa['MONTO_FMT'] = df_mapa['MONTO_TOT'].apply(lambda x: "{:,.2f}".format(x))
    else: df_mapa['MONTO_FMT'] = "0.00"
    if col_sup: df_mapa['SUP_FMT'] = df_mapa[col_sup].apply(lambda x: "{:,.1f}".format(x))

    campos_deseados = ['SOLICITANT','FOL_PROG', 'ESTADO', 'MUNICIPIO', 'TIPO_PROP', 'MONTO_FMT', 'CONCEPTO']
    if col_sup: campos_deseados.append('SUP_FMT')
    campos_validos = [c for c in campos_deseados if c in df_mapa.columns]
    
    # Renderizar capas activas con su color del catálogo
    for codigo in capas_activas:
        subset = df_mapa[df_mapa['TIPO_CAPA'] == codigo]
        if not subset.empty:
            color_capa = CATALOGO_CAPAS.get(codigo, {}).get("color", "gray")
            folium.GeoJson(
                subset, name=CATALOGO_CAPAS[codigo]['nombre'], smooth_factor=2.0,
                style_function=lambda x, c=color_capa: {'fillColor': c, 'color': 'black', 'weight': 0.4, 'fillOpacity': 0.7},
                tooltip=folium.GeoJsonTooltip(fields=campos_validos)
            ).add_to(m)

    # Macro Leyenda Dinámica
    leyenda_html = ""
    for codigo in capas_activas:
        info = CATALOGO_CAPAS.get(codigo)
        leyenda_html += f"<div style='margin-bottom:5px;'><i style='background:{info['color']}; width:10px; height:10px; display:inline-block; border-radius:2px; margin-right:5px;'></i>{info['nombre']}</div>"

    macro = MacroElement()
    macro._template = Template(f"""
    {{% macro html(this, kwargs) %}}
    <div style="position: fixed; bottom: 30px; right: 30px; background:rgba(255,255,255,0.95); padding:12px; 
        border-radius:6px; border: 1px solid #ccc; box-shadow: 0 4px 10px rgba(0,0,0,0.1); z-index:999;">
        <div style="font-size:11px; font-family:Arial; color:black; font-weight:bold;">
        {leyenda_html}
        </div>
    </div>
    {{% endmacro %}}
    """)
    m.get_root().add_child(macro)
    st_folium(m, width="100%", height=600, returned_objects=[])

    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns(2, gap="medium")
    
    with col_chart1:
        if not df_filtrado.empty and 'MUNICIPIO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Municipios</div>', unsafe_allow_html=True)
            df_mun = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            fig_mun = px.bar(df_mun, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', color_discrete_sequence=[COLOR_PRIMARIO])
            fig_mun.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_mun, use_container_width=True)

    with col_chart2:
        if 'CONCEPTO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Conceptos</div>', unsafe_allow_html=True)
            df_con = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            df_con['CONCEPTO_CORTO'] = df_con['CONCEPTO'].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
            fig_con = px.bar(df_con, y='CONCEPTO_CORTO', x='MONTO_TOT', orientation='h', text_auto='.2s', color_discrete_sequence=[COLOR_SECUNDARIO])
            fig_con.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_con, use_container_width=True)

# =========================================================
# 3. ESTADÍSTICAS (DERECHA)
# =========================================================
with col_der:
    st.markdown('<div class="section-header">💰 INVERSIÓN (MXN)</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <small>CONAFOR + PARTE INTERESADA</small><br>
        <b style="color:{COLOR_PRIMARIO}; font-size:1.2rem;">${monto_cnf:,.0f} + ${monto_pi:,.0f}</b>
    </div>
    <div class="metric-container" style="border-left: 5px solid {COLOR_SECUNDARIO};">
        <small>TOTAL EJERCIDO</small><br>
        <b style="color:{COLOR_SECUNDARIO}; font-size:1.5rem;">${monto_tot:,.0f}</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top: 25px;">🌲 AVANCE FÍSICO</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <small>Superficie Total</small><br>
        <b style="color:{COLOR_PRIMARIO}; font-size:1.4rem;">{sup_tot:,.1f} ha</b>
    </div>
    <div class="metric-container">
        <small>PROYECTOS APOYADOS</small><br>
        <b style="color:{COLOR_PRIMARIO}; font-size:1.6rem;">{num_proy}</b>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_filtrado.empty:
        if 'TIPO_PROP' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Tenencia de la Tierra</div>', unsafe_allow_html=True)
            df_pie = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
            fig_pie = px.pie(df_pie, values='MONTO_TOT', names='TIPO_PROP', hole=0.5, color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO])
            fig_pie.update_layout(height=200, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown('<div class="chart-title">Inversión por Dependencia</div>', unsafe_allow_html=True)
        df_bar = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
        # Mapeamos colores dinámicamente
        color_map = {code: info['color'] for code, info in CATALOGO_CAPAS.items()}
        fig_bar = px.bar(df_bar, x='TIPO_CAPA', y='MONTO_TOT', color='TIPO_CAPA', color_discrete_map=color_map, text_auto='.2s')
        fig_bar.update_layout(height=200, showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

# TABLA
with st.expander("📋 Ver Base de Datos Completa"):
    st.dataframe(df_filtrado.drop(columns='geometry', errors='ignore'), use_container_width=True)