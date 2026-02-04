import os
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import shutil
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURACIÓN DE COLUMNAS ---
# Estas son las columnas que TU dashboard necesita para no romperse
COLUMNAS_REQUERIDAS = {
    'FOL_PROG': 'FOLIO',   # Si no existe, buscamos FOLIO, etc.
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
    """Busca una columna parecida a lo que necesitamos."""
    cols_upper = [c.upper() for c in cols_archivo]
    
    # 1. Buscar la exacta requerida
    if objetivo in cols_upper: return cols_archivo[cols_upper.index(objetivo)]
    
    # 2. Buscar candidatos
    candidatos = [objetivo]
    if candidatos_extra: candidatos.extend(candidatos_extra)
    if objetivo in COLUMNAS_REQUERIDAS: candidatos.append(COLUMNAS_REQUERIDAS[objetivo])

    for cand in candidatos:
        for i, col_real in enumerate(cols_upper):
            if cand in col_real: # Búsqueda parcial (ej: MONTO_TOT en MONTO_TOTAL)
                return cols_archivo[i]
    return None

def procesar_zip_upload(archivo_zip, tipo_capa, df_csv_extra=None):
    with tempfile.TemporaryDirectory() as tmpdirname:
        # 1. Descomprimir
        with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
            zip_ref.extractall(tmpdirname)
        
        # 2. Buscar SHP
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

        # 3. UNIR CON CSV (OPCIONAL)
        if df_csv_extra is not None:
            # Intentar unir por folio
            col_fol_shp = buscar_columna_flexible(gdf.columns, "FOL_PROG", ["FOLIO", "CLAVE"])
            col_fol_csv = buscar_columna_flexible(df_csv_extra.columns, "FOL_PROG", ["FOLIO", "CLAVE"])
            
            if col_fol_shp and col_fol_csv:
                gdf = gdf.merge(df_csv_extra, left_on=col_fol_shp, right_on=col_fol_csv, how='left')
        
        # 4. LIMPIEZA Y GEOMETRÍA
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        gdf['geometry'] = gdf.simplify(0.0005)
        gdf['TIPO_CAPA'] = tipo_capa

        # 5. GARANTIZAR COLUMNAS PARA EL DASHBOARD
        # Tu dashboard usa MONTO_CNF, MONTO_PI, MONTO_TOT. Si no vienen, pon ceros.
        for col_std, alias in COLUMNAS_REQUERIDAS.items():
            col_real = buscar_columna_flexible(gdf.columns, col_std, [alias])
            
            if col_real:
                # Renombrar a la estándar
                gdf.rename(columns={col_real: col_std}, inplace=True)
            else:
                # Crear vacía si no existe para que no falle el dashboard
                if 'MONTO' in col_std or 'SUPERFICIE' in col_std:
                    gdf[col_std] = 0.0
                else:
                    gdf[col_std] = "Sin Dato"

        # Asegurar numéricos
        for c in ['MONTO_TOT', 'MONTO_CNF', 'MONTO_PI', 'SUPERFICIE']:
            gdf[c] = pd.to_numeric(gdf[c], errors='coerce').fillna(0)

        return gdf, "Éxito"