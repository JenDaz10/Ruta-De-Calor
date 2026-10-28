import ee
import geemap
import geopandas as gpd
from pathlib import Path
import os

# 1. Rutas
RAIZ = Path(__file__).parent.parent
RUTA_GEOJSON = RAIZ / "data" / "processed" / "pudahuel.geojson"
RUTA_SALIDA_TIF = RAIZ / "data" / "raw" / "pudahuel_lst_verano_2024.tif"

# Crear carpeta raw si no existe
os.makedirs(RUTA_SALIDA_TIF.parent, exist_ok=True)

# 2. Inicializar Google Earth Engine
try:
    ee.Initialize(project='ruta-de-calor')
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project='ruta-de-calor')

print("1. Cargando polígono de Pudahuel...")
gdf = gpd.read_file(RUTA_GEOJSON)
# Obtener las coordenadas del bounding box para GEE
minx, miny, maxx, maxy = gdf.total_bounds
region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

print("2. Buscando imágenes Landsat 8 (Verano 2024, sin nubes)...")
# Colección Landsat 8 Level 2 (Surface Temperature)
dataset = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
           .filterBounds(region)
           .filterDate('2024-01-01', '2024-03-31') # Fechas de verano
           .filterMetadata('CLOUD_COVER', 'less_than', 5)) # Cielos despejados

imagen = dataset.median()

print("3. Calculando Temperatura de Superficie (Celsius)...")
# La banda ST_B10 es la temperatura. Hay que aplicar el factor de escala de la NASA.
# Formula: (Valor * 0.00341802 + 149.0) - 273.15
temp_band = imagen.select('ST_B10')
lst_celsius = temp_band.multiply(0.00341802).add(149.0).subtract(273.15)

print(f"4. Descargando el mapa de calor a {RUTA_SALIDA_TIF.name}...")
# Descargar el TIF recortado al bounding box de Pudahuel
geemap.ee_export_image(
    lst_celsius, 
    filename=str(RUTA_SALIDA_TIF), 
    scale=30, # Resolución de 30 metros por píxel
    region=region, 
    file_per_band=False
)

print("¡Descarga térmica completada con éxito!")