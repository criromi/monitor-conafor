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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Monitor CONAFOR", page_icon="🌲")

# 🎨 COLORES INSTITUCIONALES
COLOR_PRIMARIO = "#13322B"      # Verde Oscuro Gobierno
COLOR_SECUNDARIO = "#9D2449"    # Guinda Institucional
COLOR_ACENTO = "#DDC9A3"        # Dorado
COLOR_TEXTO = "#333333"         # Gris Oscuro
COLOR_FONDO_GRIS = "#F8F9FA"    # Gris muy claro

# Colores Mapa
COLOR_PSA_MAPA = "#28a745"
COLOR_PFC_MAPA = "#ffc107"
COLOR_MFC_MAPA = "#17a2b8"

# --- 2. ESTILOS CSS ---
st.markdown(f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}
    [data-testid="stSidebar"] {{ display: none; }}
    
    /* --- TARJETAS --- */
    div[data-testid="column"] {{
        background-color: white;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e0e0e0;
        height: 100%;
    }}
    
    /* --- CORRECCIÓN DE TEXTO CHECKBOXES --- */
    div[data-testid="stCheckbox"] label p {{
        color: #000000 !important; 
        font-weight: 700 !important;
        font-size: 1rem !important;
        white-space: nowrap !important;
    }}
    div[data-testid="stCheckbox"] label span {{
        color: #000000 !important;
    }}
    
    /* Estilo del contenedor del checkbox (FORZADO CON !IMPORTANT) */
    div[data-testid="stCheckbox"] {{
        background-color: {COLOR_FONDO_GRIS} !important; 
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 8px;
        border-left: 5px solid {COLOR_SECUNDARIO};
        border: 1px solid #ddd;
    }}

    /* --- ENCABEZADOS DE SECCIÓN --- */
    .section-header {{
        color: {COLOR_PRIMARIO};
        font-weight: 800;
        border-bottom: 2px solid {COLOR_ACENTO};
        padding-bottom: 5px;
        margin-bottom: 10px;
        font-size: 1rem;
        margin-top: 10px;
    }}

    /* --- MÉTRICAS --- */
    .metric-container {{
        background-color: {COLOR_FONDO_GRIS};
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
        text-align: center;
        border: 1px solid #eee;
    }}
    .metric-label {{
        font-size: 0.7rem; color: #555; text-transform: uppercase; font-weight: 700;
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

# --- 3. HEADER CON LOGO A LA DERECHA ---
def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception: return None

# Búsqueda de logo
nombre_logo = "logo 25 ani_conafor"
carpeta_logos = "logos"
logo_b64 = None
ext_encontrada = ""
for ext in [".png", ".jpg", ".jpeg"]:
    ruta_posible = os.path.join(carpeta_logos, nombre_logo + ext)
    if os.path.exists(ruta_posible):
        logo_b64 = get_img_as_base64(ruta_posible)
        ext_encontrada = "png" if ext == ".png" else "jpeg"
        break

# Construcción HTML
if logo_b64:
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
        <img src="data:image/{ext_encontrada};base64,{logo_b64}" style="height: 70px; width: auto;">
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

# --- 4. DATOS ---
@st.cache_data
def cargar_datos():
    ruta_master = os.path.join('datos_web', 'db_master.parquet')
    ruta_cuenca = os.path.join('datos_web', 'cuenca_web.parquet')
    if not os.path.exists(ruta_master): return None, None
    try:
        gdf = gpd.read_parquet(ruta_master).copy()
        # Asegurar tipos string
        for c in ['FOL_PROG', 'MUNICIPIO', 'TIPO_CAPA', 'TIPO_PROP', 'CONCEPTO', 'GERENCIA', 'ESTADO', 'SOLICITANT']:
            if c in gdf.columns: gdf[c] = gdf[c].astype(str)
        # Asegurar tipos numéricos
        for col_num in ['MONTO_CNF', 'MONTO_PI', 'MONTO_TOT', 'SUPERFICIE']:
            if col_num not in gdf.columns: gdf[col_num] = 0.0
        cuenca = gpd.read_parquet(ruta_cuenca).copy() if os.path.exists(ruta_cuenca) else None
        return gdf, cuenca
    except: return None, None

df_total, cuenca = cargar_datos()

if df_total is None:
    st.error("⚠️ Error de carga. Ejecuta 'optimizador_cuenca.py'.")
    st.stop()

# --- 5. LAYOUT ---
col_izq, col_centro, col_der = st.columns([1.1, 2.9, 1.4], gap="medium")

# =========================================================
# 1. CONTROLES (IZQUIERDA)
# =========================================================
with col_izq:
    st.markdown("""
        <style>
        div[data-testid="stCheckbox"] div[data-testid="stMarkdownContainer"] p {
            color: #000000 !important; font-weight: 700 !important; font-size: 16px !important; white-space: nowrap !important;
        }
        div[data-testid="stCheckbox"] span { color: #000000 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">🎛️ VISUALIZACIÓN</div>', unsafe_allow_html=True)
    
    ver_psa = st.checkbox("🟩 Servicios Ambientales", value=True, key="chk_psa")
    ver_pfc = st.checkbox("🟨 Plantaciones Forestales", value=True, key="chk_pfc")
    ver_mfc = st.checkbox("🟦 Manejo Forestal", value=True, key="chk_mfc")
    
    st.markdown("""
        <div style="margin-top:20px; font-size:0.8rem; color:#000; background:#fff; padding:10px; border-radius:6px; border:1px solid #ccc;">
        <span style="color:black;">ℹ️ <b>Nota:</b> Desactiva capas para filtrar el cálculo de inversión y actualizar las gráficas.</span>
        </div>
    """, unsafe_allow_html=True)

# Lógica de Filtros
capas = []
if ver_psa: capas.append("PSA")
if ver_pfc: capas.append("PFC")
if ver_mfc: capas.append("MFC")

df_filtrado = df_total[df_total['TIPO_CAPA'].isin(capas)]

# Cálculos Totales
monto_cnf = df_filtrado['MONTO_CNF'].sum()
monto_pi = df_filtrado['MONTO_PI'].sum()
monto_tot = df_filtrado['MONTO_TOT'].sum()
col_sup = next((c for c in df_filtrado.columns if c.upper() in ['SUPERFICIE', 'SUP_HA', 'HECTAREAS', 'HA']), None)
sup_tot = df_filtrado[col_sup].sum() if col_sup else 0
num_proy = len(df_filtrado)

# SECCIÓN DE DESCARGAS (Dentro de columna izquierda)
with col_izq:
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📥 DESCARGAR DATOS</div>', unsafe_allow_html=True)

    if not df_filtrado.empty:
        # 1. EXCEL
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

        # 2. SHAPEFILE ZIPPED
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                ruta_shp = os.path.join(tmp_dir, "Proyectos_CONAFOR.shp")
                df_filtrado.to_file(ruta_shp, driver='ESRI Shapefile')
                
                buffer_zip = BytesIO()
                with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for archivo in os.listdir(tmp_dir):
                        ruta_completa = os.path.join(tmp_dir, archivo)
                        zf.write(ruta_completa, arcname=archivo)
                
                buffer_zip.seek(0)
                
                st.download_button(
                    label="🌍 Descargar Capa (.zip SHP)",
                    data=buffer_zip,
                    file_name="Proyectos_Shapefile.zip",
                    mime="application/zip",
                    use_container_width=True,
                    help="Archivo ZIP compatible con cualquier SIG (ArcGIS, QGIS)."
                )
        except Exception as e:
            st.error(f"Error generando Shapefile: {e}")

# =========================================================
# 2. MAPA (CENTRO) + GRÁFICOS INFERIORES
# =========================================================
with col_centro:
    try:
        if not df_filtrado.empty:
            b = df_filtrado.total_bounds
            clat, clon = (b[1]+b[3])/2, (b[0]+b[2])/2
            zoom = 8
        else:
            clat, clon, zoom = 20.5, -101.5, 7
    except: clat, clon, zoom = 20.5, -101.5, 7

    # OPTIMIZACIÓN 1: prefer_canvas=True (AGREGADO PARA FLUIDEZ)
    m = folium.Map([clat, clon], zoom_start=zoom, tiles=None, zoom_control=False, prefer_canvas=True)
    folium.TileLayer("CartoDB positron", control=False).add_to(m)

    if cuenca is not None:
        folium.GeoJson(cuenca, name="Cuenca", style_function=lambda x: {'fillColor':'none','color':'#555','weight':2,'dashArray':'5,5'}).add_to(m)
        # OPTIMIZACIÓN 2: FIT BOUNDS (AGREGADO PARA ENCUADRE DE CUENCA)
        bounds = cuenca.total_bounds
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    config_capas = {"PSA": COLOR_PSA_MAPA, "PFC": COLOR_PFC_MAPA, "MFC": COLOR_MFC_MAPA}

    # --- DATOS PARA MAPA ---
    df_mapa = df_filtrado.copy()
    df_mapa['MONTO_FMT'] = df_mapa['MONTO_TOT'].apply(lambda x: "{:,.2f}".format(x))
    if col_sup:
        df_mapa['SUP_FMT'] = df_mapa[col_sup].apply(lambda x: "{:,.1f}".format(x))

    # --- ALIAS TOOLTIP ---
    campos_deseados = ['SOLICITANT','FOL_PROG', 'ESTADO', 'MUNICIPIO', 'TIPO_PROP', 'MONTO_FMT', 'CONCEPTO']
    if col_sup: campos_deseados.append('SUP_FMT')
    
    campos_validos = [c for c in campos_deseados if c in df_mapa.columns]

    diccionario_alias = {
        'SOLICITANT': 'BENEFICIARIO: ', 'FOL_PROG': 'FOLIO: ', 'ESTADO': 'ESTADO: ', 'MUNICIPIO': 'MUNICIPIO: ',
        'TIPO_PROP': 'TIPO DE PROPIEDAD: ', 'MONTO_FMT': 'INVERSIÓN ($): ', 'CONCEPTO': 'CONCEPTO: ', 'SUP_FMT': 'SUPERFICIE (Ha): '
    }
    lista_alias = [diccionario_alias.get(c, c) for c in campos_validos]

    for tipo in capas:
        subset = df_mapa[df_mapa['TIPO_CAPA'] == tipo]
        if not subset.empty:
            # OPTIMIZACIÓN 3: smooth_factor (AGREGADO PARA FLUIDEZ)
            folium.GeoJson(
                subset, name=tipo,
                smooth_factor=2.0,  
                style_function=lambda x, c=config_capas[tipo]: {'fillColor': c, 'color': 'black', 'weight': 0.4, 'fillOpacity': 0.7},
                tooltip=folium.GeoJsonTooltip(
                    fields=campos_validos, 
                    aliases=lista_alias,
                    style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
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
    
    # OPTIMIZACIÓN 4: returned_objects=[] (AGREGADO PARA EVITAR RECARGAS)
    st_folium(m, width="100%", height=600, returned_objects=[])

    # --- GRÁFICAS INFERIORES (MUNICIPIOS Y CONCEPTOS) ---
    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
    
    col_chart1, col_chart2 = st.columns(2, gap="medium")
    
    # 1. TOP 10 MUNICIPIOS
    with col_chart1:
        if not df_filtrado.empty and 'MUNICIPIO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Municipios por Inversión</div>', unsafe_allow_html=True)
            df_mun = df_filtrado.groupby('MUNICIPIO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            
            fig_mun = px.bar(
                df_mun, x='MUNICIPIO', y='MONTO_TOT',
                text_auto='.2s', color_discrete_sequence=[COLOR_PRIMARIO]
            )
            fig_mun.update_layout(
                xaxis_title=None, yaxis_title=None,
                xaxis=dict(tickfont=dict(size=10, color="black"), categoryorder='total descending'), 
                yaxis=dict(showgrid=True, gridcolor="#eee", showticklabels=False),
                margin=dict(t=10, b=10, l=0, r=0), height=300,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False, font=dict(color="black")
            )
            fig_mun.update_traces(textfont_size=11, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_mun, use_container_width=True, config={'displayModeBar': False})

    # 2. TOP 10 CONCEPTOS
    with col_chart2:
        if 'CONCEPTO' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Top 10 Conceptos de Apoyo</div>', unsafe_allow_html=True)
            df_con = df_filtrado.groupby('CONCEPTO')['MONTO_TOT'].sum().reset_index().nlargest(10, 'MONTO_TOT')
            df_con['CONCEPTO_CORTO'] = df_con['CONCEPTO'].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
            
            fig_con = px.bar(
                df_con, y='CONCEPTO_CORTO', x='MONTO_TOT', orientation='h',
                text_auto='.2s', color_discrete_sequence=[COLOR_SECUNDARIO]
            )
            fig_con.update_layout(
                xaxis_title=None, yaxis_title=None,
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
    # --- FINANCIERA ---
    st.markdown('<div class="section-header">💰 INVERSIÓN (MXN)</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">CONAFOR vs PARTE INTERESADA (CONTRAPARTE)</div>
        <div class="metric-value">${monto_cnf:,.0f}</div>
        <div style="font-size: 0.8rem; color: #666; font-weight:bold;">+ ${monto_pi:,.0f} (Part.)</div>
    </div>
    
    <div class="metric-container" style="border-left: 5px solid {COLOR_SECUNDARIO}; background:white;">
        <div class="metric-label">TOTAL EJERCIDO</div>
        <div class="metric-value-total">${monto_tot:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    # --- FÍSICA ---
    st.markdown('<div class="section-header" style="margin-top: 25px;">🌲 AVANCE FÍSICO</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">Superficie Total</div>
        <div class="metric-value" style="color:{COLOR_PRIMARIO}; font-size:1.4rem;">{sup_tot:,.1f} ha</div>
    </div>
    
    <div style="text-align:center; margin-bottom:15px; background:{COLOR_FONDO_GRIS}; padding:10px; border-radius:8px; border:1px solid #eee;">
        <div class="metric-label">PROYECTOS APOYADOS</div>
        <span style="font-size:1.6rem; font-weight:bold; color:{COLOR_PRIMARIO};">{num_proy}</span>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_filtrado.empty:
        # Donut Chart
        if 'TIPO_PROP' in df_filtrado.columns:
            st.markdown('<div class="chart-title">Distribución por Tenencia</div>', unsafe_allow_html=True)
            df_pie = df_filtrado.groupby('TIPO_PROP')['MONTO_TOT'].sum().reset_index()
            fig_pie = px.pie(
                df_pie, values='MONTO_TOT', names='TIPO_PROP', hole=0.5,
                color_discrete_sequence=[COLOR_SECUNDARIO, COLOR_ACENTO, COLOR_PRIMARIO, "#6c757d"]
            )
            fig_pie.update_layout(
                showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=10, b=30, l=10, r=10), height=200,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black")
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent')
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        # Bar Chart (Categoría)
        st.markdown('<div class="chart-title">Inversión por Categoría</div>', unsafe_allow_html=True)
        df_bar = df_filtrado.groupby('TIPO_CAPA')['MONTO_TOT'].sum().reset_index().sort_values('MONTO_TOT', ascending=False)
        color_map_inst = {"PSA": COLOR_PRIMARIO, "PFC": COLOR_SECUNDARIO, "MFC": COLOR_ACENTO}
        fig_bar = px.bar(
            df_bar, x='TIPO_CAPA', y='MONTO_TOT', color='TIPO_CAPA',
            color_discrete_map=color_map_inst, text_auto='.2s'
        )
        fig_bar.update_layout(
            xaxis_title=None, yaxis_title=None,
            xaxis=dict(tickfont=dict(size=12, color="black")),
            yaxis=dict(showgrid=True, gridcolor="#eee", showticklabels=False),
            margin=dict(t=10, b=0, l=0, r=0), height=200,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False, font=dict(color="black")
        )
        fig_bar.update_traces(textfont_size=12, textposition='outside', cliponaxis=False, textfont_color="black")
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

# --- PIE DE PÁGINA (TABLA LIMPIA) ---
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
with st.expander("📋 Ver Base de Datos Completa"):
    df_tabla = df_filtrado.drop(columns=['geometry'], errors='ignore').copy()
    nombres_columnas = {
        'FOL_PROG': 'FOLIO', 'SOLICITANT': 'BENEFICIARIO', 'ESTADO': 'ESTADO', 'MUNICIPIO': 'MUNICIPIO',
        'TIPO_PROP': 'RÉGIMEN DE PROPIEDAD', 'TIPO_CAPA': 'CATEGORÍA', 'CONCEPTO': 'CONCEPTO DE APOYO',
        'MONTO_TOT': 'INVERSIÓN TOTAL ($)', 'MONTO_CNF': 'CONAFOR ($)', 'MONTO_PI': 'CONTRAPARTE ($)', col_sup: 'SUPERFICIE (Ha)'
    }
    df_tabla = df_tabla.rename(columns=nombres_columnas)
    cols_visibles = [nombre for nombre in nombres_columnas.values() if nombre in df_tabla.columns]

    st.dataframe(df_tabla[cols_visibles], use_container_width=True, hide_index=True)