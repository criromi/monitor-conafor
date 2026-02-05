import os
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import shutil
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURACIÓN DE COLUMNAS ---
COLUMNAS_REQUERIDAS = {
    'FOL_PROG': 'FOLIO',
    'MONTO_TOT': 'MONTO',
    'MONTO_CNF': 'CNF',
    'MONTO_PI': 'PI',
    'SUPERFICIE': 'SUP_HA',
    'MUNICIPIO': 'MUN',
    'ESTADO': 'EDO',
    'TIPO_PROP': 'REGIMEN',
    'CONCEPTO': 'CONCEPTO',
    'SOLICITANT': 'BENEFICIARIO'
}

def buscar_columna_flexible(cols_archivo, objetivo, candidatos_extra=None):
    cols_upper = [str(c).upper() for c in cols_archivo]
    if objetivo in cols_upper: return cols_archivo[cols_upper.index(objetivo)]
    
    candidatos = [objetivo]
    if candidatos_extra: candidatos.extend(candidatos_extra)
    if objetivo in COLUMNAS_REQUERIDAS: candidatos.append(COLUMNAS_REQUERIDAS[objetivo])

    for cand in candidatos:
        for i, col_real in enumerate(cols_upper):
            if str(cand) in str(col_real):
                return cols_archivo[i]
    return None

def procesar_zip_upload(archivo_zip, tipo_capa, df_csv_extra=None):
    with tempfile.TemporaryDirectory() as tmpdirname:
        with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
            zip_ref.extractall(tmpdirname)
        
        archivo_shp = None
        for root, dirs, files in os.walk(tmpdirname):
            for file in files:
                if file.endswith(".shp"):
                    archivo_shp = os.path.join(root, file)
                    break
        
        if not archivo_shp: return None, "No se encontró .shp en el ZIP"

        try:
            gdf = gpd.read_file(archivo_shp)
        except Exception as e: return None, f"Error leyendo SHP: {e}"

        # ==========================================================
        # 🛠️ MEJORA: UNIÓN FORZADA CON CSV (EL FIX)
        # ==========================================================
        if df_csv_extra is not None:
            col_fol_shp = buscar_columna_flexible(gdf.columns, "FOL_PROG", ["FOLIO", "CLAVE"])
            col_fol_csv = buscar_columna_flexible(df_csv_extra.columns, "FOL_PROG", ["FOLIO", "CLAVE"])
            
            if col_fol_shp and col_fol_csv:
                # 1. Normalizar folios (quitar espacios y asegurar que sean texto)
                gdf[col_fol_shp] = gdf[col_fol_shp].astype(str).str.strip()
                df_csv_extra[col_fol_csv] = df_csv_extra[col_fol_csv].astype(str).str.strip()

                # 2. BORRAR COLUMNAS DUPLICADAS EN EL MAPA
                # Si la columna existe en el CSV, la borramos del mapa para que el CSV mande
                for col_req in COLUMNAS_REQUERIDAS.keys():
                    col_en_csv = buscar_columna_flexible(df_csv_extra.columns, col_req)
                    col_en_shp = buscar_columna_flexible(gdf.columns, col_req)
                    
                    # Si el dato viene en el CSV, eliminamos la versión del SHP
                    if col_en_csv and col_en_shp and col_en_shp != col_fol_shp:
                        gdf.drop(columns=[col_en_shp], inplace=True)

                # 3. Hacer la unión
                gdf = gdf.merge(df_csv_extra, left_on=col_fol_shp, right_on=col_fol_csv, how='left')
        # ==========================================================

        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        gdf['geometry'] = gdf.simplify(0.0005)
        gdf['TIPO_CAPA'] = tipo_capa

        for col_std, alias in COLUMNAS_REQUERIDAS.items():
            col_real = buscar_columna_flexible(gdf.columns, col_std, [alias])
            if col_real:
                gdf.rename(columns={col_real: col_std}, inplace=True)
            else:
                if 'MONTO' in col_std or 'SUPERFICIE' in col_std:
                    gdf[col_std] = 0.0
                else:
                    gdf[col_std] = "Sin Dato"

        for c in ['MONTO_TOT', 'MONTO_CNF', 'MONTO_PI', 'SUPERFICIE']:
            gdf[c] = pd.to_numeric(gdf[c], errors='coerce').fillna(0)

        # Eliminar columnas repetidas del merge si quedaron (ej: FOLIO_y)
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]

        return gdf, "Éxito"