import geopandas as gpd
from pathlib import Path

# 1. Definir rutas
RAIZ = Path(__file__).parent.parent
RUTA_RAW = RAIZ / "data" / "raw" / "Cartografía_censo2024_R13" / "Cartografía_censo2024_R13_Manzanas.parquet"
RUTA_PROCESSED = RAIZ / "data" / "processed" / "pudahuel_censo_manzanas.geojson"

print("1. Cargando cartografía regional del Censo 2024 (Manzanas)...")
gdf = gpd.read_parquet(RUTA_RAW)

print("2. Filtrando la comuna de Pudahuel...")
# Filtramos usando la columna COMUNA
gdf_pudahuel = gdf[gdf['COMUNA'] == 'PUDAHUEL'].copy()
print(f"   -> Encontradas {len(gdf_pudahuel)} manzanas en Pudahuel.")

print("3. Seleccionando columnas útiles y limpiando datos...")
# Usamos 'SHAPE' porque así viene del INE
columnas_utiles = ['MANZENT', 'COMUNA', 'n_per', 'n_edad_60_mas', 'SHAPE']
gdf_pudahuel = gdf_pudahuel[columnas_utiles]

# Renombramos 'SHAPE' a 'geometry' para estandarizar el GeoJSON
gdf_pudahuel = gdf_pudahuel.rename(columns={'SHAPE': 'geometry'})
gdf_pudahuel = gdf_pudahuel.set_geometry('geometry')

# Llenar posibles valores nulos con 0
gdf_pudahuel['n_edad_60_mas'] = gdf_pudahuel['n_edad_60_mas'].fillna(0)

# Simplificar la geometría un poco para que cargue rapidísimo en Streamlit
# Mantenemos topología para no deformar las manzanas
gdf_pudahuel['geometry'] = gdf_pudahuel['geometry'].simplify(0.0001, preserve_topology=True)

print(f"4. Guardando archivo final en: {RUTA_PROCESSED.relative_to(RAIZ)}")
# Exportar a GeoJSON
gdf_pudahuel.to_file(RUTA_PROCESSED, driver="GeoJSON")

print("¡Proceso terminado con éxito!")