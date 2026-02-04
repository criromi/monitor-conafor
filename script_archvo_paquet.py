import geopandas as gpd

# 1. Carga tu capa local
ruta_local = r"C:\Geoportal_CONAFOR\Monitor_Lerma_Santiago\datos_crudos\RH_Lerma_Santiago.shp"
cuenca = gpd.read_file(ruta_local)

# 2. Asegura que tenga el sistema de coordenadas correcto para la web
cuenca = cuenca.to_crs("EPSG:4326")

# 3. Guárdalo como parquet en tu carpeta del proyecto
cuenca.to_parquet("datos_web/cuenca_web.parquet")

print("¡Listo! Archivo cuenca_web.parquet generado con éxito.")