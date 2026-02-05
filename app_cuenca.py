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

# Colores Mapa
COLOR_PSA_MAPA = "#28a745"
COLOR_PFC_MAPA = "#ffc107"
COLOR_MFC_MAPA = "#17a2b8"

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

    # CSS PARA CENTRAR Y ESTILAR LA TARJETA DE LOGIN
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
# 🛠️ MODO ADMINISTRADOR (SOLO SI ENTRO CON admin2026)
# ==============================================================================
modo_edicion_activo = False

if st.session_state.rol == "admin":
    with st.sidebar:
        st.header("🔧 Panel Administrador")
        st.success("Sesión: Administrador")
        
        seleccion = st.radio("Acciones:", ["👁️ Ver Monitor", "📤 Subir/Actualizar Capas"])
        
        # --- AQUÍ ESTÁ TU BOTÓN DE ACTUALIZAR (SOLO PARA ADMIN) ---
        st.markdown("---")
        st.write("Gestion de Memoria:")
        if st.button("🔄 Forzar Recarga de Datos"):
            st.cache_data.clear()
            st.rerun()
        # -----------------------------------------------------------

        if seleccion == "📤 Subir/Actualizar Capas":
            modo_edicion_activo = True
            
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.rol = None
            st.rerun()

# Si está en modo edición, mostramos el panel de carga y DETENEMOS el resto
if modo_edicion_activo:
    st.title("🛠️ Gestión de Datos - Cuenca Lerma Santiago")
    st.markdown("Utiliza este panel para actualizar la información del mapa y las bases de datos.")
    
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        st.subheader("1. Selección de Archivos")
        capa_seleccionada = st.selectbox("Selecciona la capa a actualizar:", ["PSA", "PFC", "MFC"])
        uploaded_zip = st.file_uploader("Archivo Shapefile (.zip)", type="zip", help="Debe contener .shp, .shx, .dbf, .prj")
        uploaded_csv = st.file_uploader("Base de Datos Excel/CSV (Opcional)", type=["csv", "xlsx"])

    with col_up2:
        st.subheader("2. Procesamiento")
        st.info(f"Vas a actualizar la capa: **{capa_seleccionada}**")
        
        if st.button("🚀 PROCESAR Y GUARDAR", type="primary"):
            if uploaded_zip:
                with st.spinner("Procesando archivos..."):
                    try:
                        import backend_admin
                        # Convertir excel a dataframe si es necesario
                        df_extra = None
                        if uploaded_csv:
                            if uploaded_csv.name.endswith('.csv'):
                                df_extra = pd.read_csv(uploaded_csv)
                            else:
                                df_extra = pd.read_excel(uploaded_csv)
                        
                        # Procesar
                        gdf_result, msg = backend_admin.procesar_zip_upload(uploaded_zip, capa_seleccionada, df_extra)
                        
                        if gdf_result is not None:
                            # Guardar
                            ruta_out = os.path.join("datos_web", f"capa_{capa_seleccionada}_procesada.parquet")
                            os.makedirs("datos_web", exist_ok=True)
                            gdf_result.to_parquet(ruta_out)
                            
                            # --- AQUÍ OCURRE LA MAGIA AUTOMÁTICA ---
                            st.cache_data.clear() # Limpia la memoria automáticamente al guardar
                            # ---------------------------------------
                            
                            st.success(f"✅ ¡Capa {capa_seleccionada} actualizada con éxito!")
                            st.balloons()
                            
                        else:
                            st.error(f"Error en backend: {msg}")
                    except Exception as e:
                        st.error(f"Error crítico: {e}")
            else:
                st.warning("Por favor sube al menos el archivo ZIP.")
    st.stop() # DETENEMOS AQUI PARA QUE EL ADMIN NO VEA EL DASHBOARD MIENTRAS EDITA

# ==============================================================================
# 🚀 APLICACIÓN PRINCIPAL (DASHBOARD)
# ==============================================================================

# --- Funciones auxiliares ---
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

# --- 2. ESTILOS CSS (ESTILOS COMPLETOS ORIGINALES) ---
st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    
    /* PANEL IZQUIERDO (TARJETA) */
    div[data-testid="column"]:nth-of-type(1) > div {{
        background-color: white; border-radius: 12px; padding: 20px;
        border: 1px solid #e0e0e0; box-shadow: 0 4px 15px rgba(0,0,0,0.08); height: 100%;
    }}

    /* CHECKBOXES */
    div[data-testid="stCheckbox"] label p {{
        font-weight: 700 !important; font-size: 1rem !important; color: #333 !important;
    }}
    
    /* PANELES CENTRO Y DERECHA */
    div[data-testid="column"]:nth-of-type(2) > div,
    div[data-testid="column"]:nth-of-type(3) > div {{
        background-color: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    
    /* ESTILOS GENERALES */
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
        text-align: center; margin-top: 20px; margin-bottom: 5px; border-bottom: 1px solid #eee;
        padding-bottom: 3px;
    }}
    iframe {{ width: 100% !important; border-radius: 8px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. HEADER APP PRINCIPAL ---
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

# --- 4. DATOS (CACHÉ REDUCIDO 60s) ---
@st.cache_data(ttl=60) 
def cargar_datos():
    carpeta_datos = 'datos_web'
    ruta_cuenca = os.path.join(carpeta_datos, 'cuenca_web.parquet')
    
    capas_admin = ["PSA", "PFC", "MFC"]
    gdfs_lista = []
    
    # Intentamos cargar capas individuales
    for capa in capas_admin:
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
        # Fallback master
        ruta_master = os.path.join(carpeta_datos, 'db_master.parquet')
        gdf = gpd.read_parquet(ruta_master) if os.path.exists(ruta_master) else None

    if gdf is not None:
        # Limpieza de tipos de datos
        for c in ['FOL_PROG', 'MUNICIPIO', 'TIPO_CAPA', 'TIPO_PROP', 'CONCEPTO', 'ESTADO', 'SOLICITANT']:
            if c in gdf.columns: gdf[c] = gdf[c].astype(str)
        
        for col in ['MONTO_CNF', 'MONTO_PI', 'MONTO_TOT', 'SUPERFICIE']:
            if col not in gdf.columns: gdf[col] = 0.0
            else: gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0)

    cuenca = gpd.read_parquet(ruta_cuenca) if os.path.exists(ruta_cuenca) else None
    return gdf, cuenca

df_total, cuenca = cargar_datos()

# Inicializar hora de actualización (opcional, solo para control interno)
if 'ultima_actualizacion' not in st.session_state:
    st.session_state.ultima_actualizacion = datetime.now().strftime("%H:%M:%S")

if df_total is None:
    st.info("👋 Hola Admin. El sistema no tiene datos. Sube capas en el menú lateral.")
    st.stop()

# --- 5. LAYOUT ---
col_izq, col_centro, col_der = st.columns([1.1, 2.9, 1.4], gap="medium")

# =========================================================
# 1. CONTROLES (IZQUIERDA)
# =========================================================
with col_izq:
    st.markdown('<div class="section-header">🎛️ FILTROS</div>', unsafe_allow_html=True)
    ver_psa = st.checkbox("🟩 Servicios Ambientales", value=True, key="chk_psa")
    ver_pfc = st.checkbox("🟨 Plantaciones Forestales", value=True, key="chk_pfc")
    ver_mfc = st.checkbox("🟦 Manejo Forestal", value=True, key="chk_mfc")
    
    # ❌ EL BOTÓN DE ACTUALIZAR HA SIDO ELIMINADO DE AQUÍ PARA EL USUARIO COMÚN ❌

# Lógica de filtrado
capas = []
if ver_psa: capas.append("PSA")
if ver_pfc: capas.append("PFC")
if ver_mfc: capas.append("MFC")

df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas)].copy()

# ==============================================================================
# 🚨 CORRECCIÓN CRÍTICA DE CONTEO (EL FIX DE LOS 231 PROYECTOS)
# ==============================================================================
# 1. Limpieza de strings
df_filtrado['FOL_PROG'] = df_filtrado['FOL_PROG'].astype(str).str.strip()
# 2. Definir valores basura
valores_invalidos = ['nan', 'None', '', 'Sin Dato', 'NAN', 'null']
# 3. Métricas
monto_cnf = df_filtrado['MONTO_CNF'].sum()
monto_pi = df_filtrado['MONTO_PI'].sum()
monto_tot = df_filtrado['MONTO_TOT'].sum()
col_sup = next((c for c in df_filtrado.columns if c.upper() in ['SUPERFICIE', 'SUP_HA', 'HECTAREAS', 'HA']), None)
sup_tot = df_filtrado[col_sup].sum() if col_sup else 0
# 4. Conteo ÚNICO excluyendo basura
num_proy = df_filtrado[~df_filtrado['FOL_PROG'].isin(valores_invalidos)]['FOL_PROG'].nunique()
# ==============================================================================

# SECCIÓN DESCARGAS (IZQUIERDA)
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
        
        st.download_button(
            label="📊 Descargar Tabla (Excel)",
            data=buffer_excel.getvalue(),
            file_name="Base_Datos_CONAFOR.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                ruta_shp = os.path.join(tmp_dir, "Proyectos_CONAFOR.shp")
                df_filtrado.to_file(ruta_shp, driver='ESRI Shapefile')
                buffer_zip = BytesIO()
                with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for archivo in os.listdir(tmp_dir):
                        zf.write(os.path.join(tmp_dir, archivo), arcname=archivo)
                buffer_zip.seek(0)
                st.download_button(
                    label="🌍 Descargar Capa (.zip SHP)",
                    data=buffer_zip,
                    file_name="Proyectos_Shapefile.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Error generando Shapefile: {e}")

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

    config_capas = {"PSA": COLOR_PSA_MAPA, "PFC": COLOR_PFC_MAPA, "MFC": COLOR_MFC_MAPA}
    df_mapa = df_filtrado.copy()
    
    if 'MONTO_TOT' in df_mapa.columns:
        df_mapa['MONTO_FMT'] = df_mapa['MONTO_TOT'].apply(lambda x: "{:,.2f}".format(x))
    else: df_mapa['MONTO_FMT'] = "0.00"
    if col_sup: df_mapa['SUP_FMT'] = df_mapa[col_sup].apply(lambda x: "{:,.1f}".format(x))

    campos_deseados = ['SOLICITANT','FOL_PROG', 'ESTADO', 'MUNICIPIO', 'TIPO_PROP', 'MONTO_FMT', 'CONCEPTO']
    if col_sup: campos_deseados.append('SUP_FMT')
    campos_validos = [c for c in campos_deseados if c in df_mapa.columns]
    
    diccionario_alias = {
        'SOLICITANT': 'BENEFICIARIO: ', 'FOL_PROG': 'FOLIO: ', 'ESTADO': 'ESTADO: ', 
        'MUNICIPIO': 'MUNICIPIO: ', 'TIPO_PROP': 'TIPO DE PROPIEDAD: ', 
        'MONTO_FMT': 'INVERSIÓN ($): ', 'CONCEPTO': 'CONCEPTO: ', 'SUP_FMT': 'SUPERFICIE (Ha): '
    }
    lista_alias = [diccionario_alias.get(c, c) for c in campos_validos]

    for tipo in capas:
        subset = df_mapa[df_mapa['TIPO_CAPA'] == tipo]
        if not subset.empty:
            folium.GeoJson(
                subset, name=tipo, smooth_factor=2.0,
                style_function=lambda x, c=config_capas.get(tipo, "gray"): {'fillColor': c, 'color': 'black', 'weight': 0.4, 'fillOpacity': 0.7},
                tooltip=folium.GeoJsonTooltip(
                    fields=campos_validos, aliases=lista_alias,
                    style=("background-color: white; color: #333333; font-family: arial; font-size: 10px; padding: 8px;")
                )
            ).add_to(m)

    macro = MacroElement()
    macro._template = Template(f"""
    {{% macro html(this, kwargs) %}}
    <div style="position: fixed; bottom: 30px; right: 30px; background:rgba(255,255,255,0.95); padding:12px; 
        border-radius:6px; border: 1px solid #ccc; box-shadow: 0 4px 10px rgba(0,0,0,0.1); z-index:999;">
        <div style="font-size:11px; font-family:Arial; color:black; font-weight:bold;">
        <div style="margin-bottom:5px;"><i style="background:{COLOR_PSA_MAPA}; width:10px; height:10px; display:inline-block; border-radius:2px; margin-right:5px;"></i>PSA (Servicios Ambientales)</div>
        <div style="margin-bottom:5px;"><i style="background:{COLOR_PFC_MAPA}; width:10px; height:10px; display:inline-block; border-radius:2px; margin-right:5px;"></i>PFC (Plantaciones Forestales Comerciales)</div>
        <div><i style="background:{COLOR_MFC_MAPA}; width:10px; height:10px; display:inline-block; border-radius:2px; margin-right:5px;"></i>MFC (Manejo Forestal Comunitario)</div>
        </div>
    </div>
    {{% endmacro %}}
    """)
    m.get_root().add_child(macro)
    st_folium(m, width="100%", height=600, returned_objects=[])

    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns(2, gap="medium")
    
    # --- GRÁFICA MUNICIPIOS ---
    with col_chart1:
        if not df_filtrado.empty and 'MUNICIPIO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Municipios por Inversión</div>', unsafe_allow_html=True)
            df_mun = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            fig_mun = px.bar(
                df_mun, x='MUNICIPIO', y='MONTO_TOT', text_auto='.2s', 
                color_discrete_sequence=[COLOR_PRIMARIO],
                labels={'MUNICIPIO': 'MUNICIPIO', 'MONTO_TOT': 'MONTO TOTAL'}
            )
            fig_mun.update_layout(
                xaxis_title="MUNICIPIO", yaxis_title="MONTO TOTAL",
                xaxis=dict(tickfont=dict(size=10, color="black"), categoryorder='total descending'), 
                yaxis=dict(showgrid=True, gridcolor="#eee", showticklabels=False),
                margin=dict(t=10, b=10, l=0, r=0), height=300,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False, font=dict(color="black")
            )
            fig_mun.update_traces(textfont_size=11, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_mun, use_container_width=True, config={'displayModeBar': False})

    # --- GRÁFICA CONCEPTOS ---
    with col_chart2:
        if 'CONCEPTO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Conceptos de Apoyo</div>', unsafe_allow_html=True)
            df_con = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            df_con['CONCEPTO_CORTO'] = df_con['CONCEPTO'].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
            fig_con = px.bar(
                df_con, y='CONCEPTO_CORTO', x='MONTO_TOT', orientation='h', text_auto='.2s', 
                color_discrete_sequence=[COLOR_SECUNDARIO],
                labels={'CONCEPTO_CORTO': 'CONCEPTO DE APOYO', 'MONTO_TOT': 'MONTO TOTAL'}
            )
            fig_con.update_layout(
                xaxis_title="MONTO TOTAL", yaxis_title="CONCEPTO DE APOYO",
                xaxis=dict(showgrid=True, gridcolor="#eee", showticklabels=False),
                yaxis=dict(tickfont=dict(size=10, color="black"), categoryorder='total ascending'),
                margin=dict(t=10, b=0, l=0, r=0), height=300,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False, font=dict(color="black")
            )
            fig_con.update_traces(textfont_size=11, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_con, use_container_width=True, config={'displayModeBar': False})

# =========================================================
# 3. ESTADÍSTICAS (DERECHA)
# =========================================================
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
    <div style="text-align:center; margin-bottom:15px; background:#F8F9FA; padding:10px; border-radius:8px; border:1px solid #dcdcdc;">
        <div class="metric-label">PROYECTOS APOYADOS</div>
        <span style="font-size:1.6rem; font-weight:bold; color:{COLOR_PRIMARIO};">{num_proy}</span>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_filtrado.empty:
        # --- PIE CHART TENENCIA ---
        if 'TIPO_PROP' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Distribución por Tenencia</div>', unsafe_allow_html=True)
            df_pie = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
            fig_pie = px.pie(
                df_pie, values='MONTO_TOT', names='TIPO_PROP', hole=0.5, 
                color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO, "#6c757d"],
                labels={'TIPO_PROP': 'RÉGIMEN', 'MONTO_TOT': 'MONTO TOTAL'}
            )
            fig_pie.update_layout(height=200, margin=dict(t=10, b=30, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True, legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        
        # --- BAR CHART CATEGORÍA ---
        st.markdown('<div class="chart-title">Inversión por Categoría</div>', unsafe_allow_html=True)
        df_bar = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
        fig_bar = px.bar(
            df_bar, x='TIPO_CAPA', y='MONTO_TOT', 
            color='TIPO_CAPA', 
            color_discrete_map={"PSA": COLOR_PRIMARIO, "PFC": COLOR_SECUNDARIO, "MFC": COLOR_ACENTO}, 
            text_auto='.2s',
            labels={'TIPO_CAPA': 'GERENCIA', 'MONTO_TOT': 'MONTO TOTAL'}
        )
        fig_bar.update_layout(
            xaxis_title="GERENCIA", yaxis_title="MONTO TOTAL",
            xaxis=dict(tickfont=dict(size=12, color="black")),
            yaxis=dict(showgrid=True, gridcolor="#eee", showticklabels=False),
            margin=dict(t=10, b=0, l=0, r=0), height=200,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False, font=dict(color="black")
        )
        fig_bar.update_traces(textfont_size=12, textposition='outside', cliponaxis=False, textfont_color="black")
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

# --- PIE DE PÁGINA ---
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
with st.expander("📋 Ver Base de Datos Completa"):
    df_tabla = df_filtrado.drop(columns=['geometry'], errors='ignore').copy()
    nombres_columnas = {
        'FOL_PROG': 'FOLIO', 'SOLICITANT': 'BENEFICIARIO', 'ESTADO': 'ESTADO', 
        'MUNICIPIO': 'MUNICIPIO', 'TIPO_PROP': 'RÉGIMEN', 'TIPO_CAPA': 'CATEGORÍA', 
        'CONCEPTO': 'CONCEPTO', 'MONTO_TOT': 'INVERSIÓN ($)', 
        'MONTO_CNF': 'CONAFOR ($)', 'MONTO_PI': 'CONTRAPARTE ($)', col_sup: 'SUPERFICIE (Ha)'
    }
    df_tabla = df_tabla.rename(columns=nombres_columnas)
    cols_visibles = [nombre for nombre in nombres_columnas.values() if nombre in df_tabla.columns]
    
    # Formateo manual para la superficie
    nombre_sup = nombres_columnas.get(col_sup)
    if nombre_sup and nombre_sup in df_tabla.columns:
        df_tabla[nombre_sup] = df_tabla[nombre_sup].apply(lambda x: "{:,.2f}".format(x) if pd.notnull(x) else "0.00")

    config_cols = {
        "INVERSIÓN ($)": st.column_config.NumberColumn(format="$ %.2f"),
        "CONAFOR ($)": st.column_config.NumberColumn(format="$ %.2f"),
        "CONTRAPARTE ($)": st.column_config.NumberColumn(format="$ %.2f"),
    }

    st.dataframe(
        df_tabla[cols_visibles], 
        use_container_width=True, 
        hide_index=True,
        column_config=config_cols
    )