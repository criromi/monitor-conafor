import os
import geopandas as gpd
import pandas as pd
import warnings

# Ignorar advertencias de proyecciones
warnings.filterwarnings('ignore')

# --- CONFIGURACIÓN ---
CARPETA_ENTRADA = 'datos_crudos'  
CARPETA_SALIDA = 'datos_web'      
ARCHIVO_CSV = 'BD_CLS.csv'
ARCHIVO_CUENCA = 'RH_Lerma_Santiago.shp'

# Configuración de las 3 capas
CAPAS_PROYECTOS = [
    {"archivo": "PSA_CLS_VIG.shp", "tipo": "PSA"}, 
    {"archivo": "PFC_CLS_VIG.shp", "tipo": "PFC"}, 
    {"archivo": "MFC_CLS_VIG.shp", "tipo": "MFC"} 
]

def buscar_columna_folio(cols):
    opciones = ['FOL_PROG', 'FOLIO', 'PROYECTO', 'CLAVE', 'EXPEDIENTE']
    c_up = [c.upper() for c in cols]
    for o in opciones:
        if o in c_up: return cols[c_up.index(o)]
    return None

def limpiar_dinero(valor):
    try:
        if pd.isna(valor): return 0.0
        if isinstance(valor, (int, float)): return float(valor)
        s = str(valor).replace('$', '').replace(',', '').strip()
        return float(s) if s else 0.0
    except: return 0.0

def optimizar_sistema():
    print("--- 🚀 INICIANDO OPTIMIZACIÓN DEL SISTEMA ---")
    if not os.path.exists(CARPETA_SALIDA): os.makedirs(CARPETA_SALIDA)

    # 1. CARGAR CSV
    ruta_csv = os.path.join(CARPETA_ENTRADA, ARCHIVO_CSV)
    df_csv = pd.DataFrame()
    
    if os.path.exists(ruta_csv):
        try:
            df_csv = pd.read_csv(ruta_csv, encoding='latin1')
            col_fol = buscar_columna_folio(df_csv.columns)
            if col_fol:
                df_csv.rename(columns={col_fol: 'FOL_PROG'}, inplace=True)
                df_csv['FOL_PROG'] = df_csv['FOL_PROG'].astype(str).str.strip()
                # Limpiar dinero
                for c in ['MONTO_TOT', 'MONTO_CNF', 'MONTO_PI', 'SUP_HA']: 
                    if c in df_csv.columns: df_csv[c] = df_csv[c].apply(limpiar_dinero)
                print(f"✅ CSV cargado: {len(df_csv)} registros.")
        except Exception as e:
            print(f"❌ Error CSV: {e}")

    # 2. PROCESAR SHAPEFILES
    gdf_lista = []
    for capa in CAPAS_PROYECTOS:
        ruta_shp = os.path.join(CARPETA_ENTRADA, capa["archivo"])
        if os.path.exists(ruta_shp):
            try:
                gdf = gpd.read_file(ruta_shp)
                col_fol = buscar_columna_folio(gdf.columns)
                if col_fol:
                    gdf.rename(columns={col_fol: 'FOL_PROG'}, inplace=True)
                    gdf['FOL_PROG'] = gdf['FOL_PROG'].astype(str).str.strip()
                    gdf['TIPO_CAPA'] = capa["tipo"]
                    
                    if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")
                    
                    # Simplificación agresiva para velocidad web (aprox 50m precisión)
                    gdf['geometry'] = gdf.simplify(0.0005)
                    
                    # Solo guardar columnas clave
                    cols_keep = ['FOL_PROG', 'TIPO_CAPA', 'geometry']
                    gdf_lista.append(gdf[cols_keep])
                    print(f"  -> {capa['tipo']} procesada.")
            except Exception as e: print(f"Error en {capa['tipo']}: {e}")

    # 3. GUARDAR MASTER
    if gdf_lista:
        gdf_todos = pd.concat(gdf_lista, ignore_index=True)
        if not df_csv.empty:
            gdf_final = gdf_todos.merge(df_csv, on='FOL_PROG', how='left')
        else:
            gdf_final = gdf_todos
            
        gdf_final.to_parquet(os.path.join(CARPETA_SALIDA, "db_master.parquet"))
        print(f"✅ BASE MAESTRA LISTA: {len(gdf_final)} proyectos.")

    # 4. PROCESAR CUENCA
    ruta_cuenca = os.path.join(CARPETA_ENTRADA, ARCHIVO_CUENCA)
    if os.path.exists(ruta_cuenca):
        gdf_c = gpd.read_file(ruta_cuenca)
        if gdf_c.crs and gdf_c.crs.to_string() != "EPSG:4326": gdf_c = gdf_c.to_crs("EPSG:4326")
        gdf_c['geometry'] = gdf_c.simplify(0.001)
        gdf_c.to_parquet(os.path.join(CARPETA_SALIDA, "cuenca_web.parquet"))
        print("✅ Cuenca procesada.")

if __name__ == "__main__":
    optimizar_sistema()