import streamlit as st
import pandas as pd
import sys
import os

# Agregamos el directorio padre para poder importar backend_admin y utils_github
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_admin import procesar_zip_upload
from utils_github import subir_archivo_a_github

st.set_page_config(page_title="Admin CONAFOR", page_icon="⚙️")

# VERIFICAR LOGIN (Usamos la misma sesión que tu app principal)
if 'acceso_concedido' not in st.session_state or not st.session_state.acceso_concedido:
    st.error("⚠️ Acceso denegado. Inicia sesión en la página principal.")
    st.stop()

st.title("⚙️ Panel de Administración")
st.markdown("Sube aquí las capas actualizadas. El sistema las procesará y actualizará el dashboard automáticamente.")

tipo_capa = st.selectbox("Selecciona el Programa:", ["PSA", "PFC", "MFC"])
archivo_zip = st.file_uploader("1. Sube el Mapa (ZIP con SHP)", type="zip")
usar_csv = st.checkbox("2. ¿Quieres subir un CSV de datos adicional?")
archivo_csv = None

if usar_csv:
    archivo_csv = st.file_uploader("Sube el Excel/CSV de datos", type=["csv", "xlsx"])

if st.button("🚀 PROCESAR Y ACTUALIZAR"):
    if archivo_zip:
        with st.status("Procesando...", expanded=True) as status:
            # Leer CSV si existe
            df_extra = None
            if archivo_csv:
                try:
                    if archivo_csv.name.endswith('.csv'):
                        df_extra = pd.read_csv(archivo_csv, encoding='latin1')
                    else:
                        df_extra = pd.read_excel(archivo_csv)
                    st.write("✅ Datos externos leídos correctamente.")
                except Exception as e:
                    st.error(f"Error en CSV: {e}")
            
            # Procesar
            st.write("🛠️ Limpiando geometrías y estandarizando columnas...")
            gdf, msg = procesar_zip_upload(archivo_zip, tipo_capa, df_extra)
            
            if gdf is not None:
                # Guardar Temporal
                nombre_archivo = f"capa_{tipo_capa}_procesada.parquet"
                gdf.to_parquet(nombre_archivo)
                
                # Subir a GitHub
                st.write("☁️ Subiendo a la nube...")
                # Asegúrate de que la ruta 'datos_web/' exista en tu repo
                ruta_repo = f"datos_web/{nombre_archivo}"
                
                exito, resp = subir_archivo_a_github(nombre_archivo, ruta_repo, f"Update {tipo_capa}")
                
                if exito:
                    status.update(label="¡Completado!", state="complete")
                    st.success(f"Capa {tipo_capa} actualizada correctamente.")
                    st.balloons()
                else:
                    st.error(f"Error subiendo a GitHub: {resp}")
            else:
                st.error(f"Error: {msg}")
    else:
        st.warning("Falta el archivo ZIP.")