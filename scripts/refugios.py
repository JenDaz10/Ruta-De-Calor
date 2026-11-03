"""
Descarga puntos que pueden servir de refugio desde OpenStreetMap (Overpass)
y los guarda en data/processed/pudahuel_refugios.geojson

Ejecutar desde la raíz del proyecto:
    python scripts/descargar_refugios.py
"""
import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import Point

RAIZ = Path(__file__).parent.parent
LIMITE = RAIZ / "data" / "processed" / "pudahuel.geojson"
SALIDA = RAIZ / "data" / "processed" / "pudahuel_refugios.geojson"

SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# (clave OSM, valor OSM) -> categoría que verá el usuario
CATEGORIAS = {
    ("amenity", "police"): "Comisaría / Carabineros",
    ("amenity", "fire_station"): "Bomberos",
    ("amenity", "hospital"): "Hospital",
    ("amenity", "clinic"): "Clínica / Cesfam",
    ("amenity", "school"): "Colegio",
    ("amenity", "kindergarten"): "Jardín infantil",
    ("amenity", "college"): "Educación superior",
    ("amenity", "university"): "Educación superior",
    ("amenity", "community_centre"): "Centro comunitario",
    ("amenity", "library"): "Biblioteca",
    ("amenity", "townhall"): "Municipalidad",
    ("leisure", "park"): "Parque / plaza",
    ("leisure", "sports_centre"): "Recinto deportivo",
    ("leisure", "stadium"): "Recinto deportivo",
}


def construir_consulta(bbox):
    s, w, n, e = bbox
    partes = "".join(
        f'nwr["{k}"="{v}"]({s},{w},{n},{e});' for (k, v) in CATEGORIAS
    )
    return f"[out:json][timeout:90];({partes});out center tags;"


def descargar(consulta):
    for url in SERVIDORES:
        try:
            r = requests.post(
                url,
                data={"data": consulta},
                headers={"User-Agent": "RutaCalor-proyecto-UDP"},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["elements"]
        except Exception as err:
            print(f"Falló {url}: {err}")
            time.sleep(3)
    raise SystemExit("No se pudo descargar. Intenta de nuevo en unos minutos.")


def categoria_de(tags):
    for (k, v), nombre in CATEGORIAS.items():
        if tags.get(k) == v:
            return nombre
    return None


def main():
    comuna = gpd.read_file(LIMITE)
    if comuna.crs is None:
        comuna = comuna.set_crs(4326)
    comuna = comuna.to_crs(4326)

    minx, miny, maxx, maxy = comuna.total_bounds
    print("Descargando desde OpenStreetMap...")
    elementos = descargar(construir_consulta((miny, minx, maxy, maxx)))
    print(f"Elementos recibidos: {len(elementos)}")

    filas = []
    for el in elementos:
        tags = el.get("tags", {})
        cat = categoria_de(tags)
        if cat is None:
            continue
        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        else:
            centro = el.get("center")
            if not centro:
                continue
            lat, lon = centro["lat"], centro["lon"]
        filas.append({
            "nombre": tags.get("name", "(sin nombre)"),
            "categoria": cat,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "geometry": Point(lon, lat),
        })

    gdf = gpd.GeoDataFrame(filas, geometry="geometry", crs=4326)
    gdf = gdf.drop_duplicates(subset=["nombre", "categoria", "lat", "lon"])

    # Quedarse solo con lo que cae dentro de la comuna
    poligono = comuna.union_all() if hasattr(comuna, "union_all") else comuna.unary_union
    gdf = gdf[gdf.within(poligono)]

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(SALIDA, driver="GeoJSON")

    print(f"\nGuardado en {SALIDA}")
    print(gdf["categoria"].value_counts().to_string())


if __name__ == "__main__":
    main()