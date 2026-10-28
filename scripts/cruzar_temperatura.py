import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from pathlib import Path

# Rutas de los archivos
RAIZ = Path(__file__).parent.parent
RUTA_CENSO = RAIZ / "data" / "processed" / "pudahuel_censo_manzanas.geojson"
RUTA_TIF = RAIZ / "data" / "raw" / "pudahuel_lst_verano_2024.tif"
RUTA_SALIDA = RAIZ / "data" / "processed" / "pudahuel_censo_manzanas.geojson" # Sobrescribimos con los datos térmicos

print("1. Cargando manzanas del Censo...")
gdf = gpd.read_file(RUTA_CENSO)

print("2. Extrayendo la temperatura satelital para cada manzana (zonal_stats)...")
# zonal_stats calcula el promedio ('mean') de los píxeles térmicos que caen dentro de cada polígono de manzana
stats = zonal_stats(
    gdf,
    str(RUTA_TIF),
    stats="mean",
    nodata=0
)

# Añadir la temperatura promedio como una nueva columna al GeoDataFrame
gdf["temp_promedio"] = [s["mean"] if s["mean"] is not None else 0.0 for s in stats]

# Redondear a un decimal para que se vea ordenado
gdf["temp_promedio"] = gdf["temp_promedio"].round(1)

print(f"3. Guardando el GeoJSON enriquecido en {RUTA_SALIDA.name}...")
gdf.to_file(RUTA_SALIDA, driver="GeoJSON")

print("¡Cruce completado con éxito! Las manzanas ya tienen su temperatura real.")