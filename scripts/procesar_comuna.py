"""
Genera, para una comuna, los mismos archivos que ya existen para Pudahuel:
  data/processed/<slug>_censo_manzanas.geojson   (Censo 2024 + temperatura LST)
  data/processed/<slug>_refugios.geojson         (OpenStreetMap)
  data/raw/<slug>_lst_verano_2024.tif            (temperatura satelital, Earth Engine)

Requiere que ya exista data/processed/<slug>.geojson (límite comunal).

Uso (desde la raíz del proyecto, con el venv activo):
    python scripts/procesar_comuna.py Renca
    python scripts/procesar_comuna.py "Cerro Navia" Cerrillos
    python scripts/procesar_comuna.py --nuevas          # Cerro Navia, Cerrillos y Renca
    python scripts/procesar_comuna.py --nuevas --forzar # vuelve a bajar la temperatura
"""
import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

RAIZ = Path(__file__).parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
RUTA_MANZANAS = (
    RAW / "Cartografía_censo2024_R13" / "Cartografía_censo2024_R13_Manzanas.parquet"
)

# nombre para mostrar -> prefijo de archivos
COMUNAS = {
    "Pudahuel": "pudahuel",
    "Cerro Navia": "cerro_navia",
    "Cerrillos": "cerrillos",
    "Renca": "renca",
}
NUEVAS = ["Cerro Navia", "Cerrillos", "Renca"]


def normalizar(texto) -> str:
    """Mayúsculas y sin tildes, para comparar nombres."""
    s = unicodedata.normalize("NFD", str(texto))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().upper()


# ------------------------------------------------------------------ 1) CENSO
COLS_EDAD = {
    "n_edad_0_5": "0 a 5 años",
    "n_edad_6_13": "6 a 13 años",
    "n_edad_14_17": "14 a 17 años",
    "n_edad_18_24": "18 a 24 años",
    "n_edad_25_44": "25 a 44 años",
    "n_edad_45_59": "45 a 59 años",
    "n_edad_60_mas": "60+ años",
}

_manzanas_region = None


def manzanas_region():
    """Lee el parquet de toda la región una sola vez."""
    global _manzanas_region
    if _manzanas_region is None:
        print("   Cargando cartografía regional del Censo 2024 (puede tardar)...")
        _manzanas_region = gpd.read_parquet(RUTA_MANZANAS)
    return _manzanas_region


def generar_etiquetas(row):
    total = row["n_per"]
    if total <= 0:
        return pd.Series(
            [
                "Sin población",
                "<div style='min-width: 180px;'><i>Manzana sin población residencial</i></div>",
            ]
        )

    valores = [(nombre, row[col]) for col, nombre in COLS_EDAD.items()]
    valores.sort(key=lambda x: x[1], reverse=True)

    textos_top = []
    for nombre, valor in valores[:3]:
        if valor > 0:
            pct = round((valor / total) * 100, 1)
            textos_top.append(f"{nombre} ({pct}%)")
    texto_hover = " | ".join(textos_top) if textos_top else "Sin datos"

    html = "<div style='min-width: 230px; font-family: sans-serif;'>"
    html += f"<b>Población Total: {int(total)} hab</b><hr style='margin: 5px 0;'>"
    html += "<b>Top 3 Edades:</b><br>"
    html += "<ul style='margin-top:5px; margin-bottom:10px; padding-left:20px;'>"
    for nombre, valor in valores[:3]:
        if valor > 0:
            pct = round((valor / total) * 100, 1)
            html += f"<li>{nombre}: <b>{pct}%</b> <span style='color:#555;'>({int(valor)} hab)</span></li>"
        else:
            html += f"<li><span style='color:#aaa;'>{nombre}: 0%</span></li>"
    html += "</ul>"
    html += "<div style='font-size: 13px; color: #333; background-color: #f0f0f0; padding: 8px; border-radius: 5px; line-height: 1.4;'>"
    html += "<b style='color:#222;'>Otros rangos:</b><br>"
    textos_otros = []
    for nombre, valor in valores[3:]:
        pct = round((valor / total) * 100, 1)
        if valor > 0:
            textos_otros.append(f"{nombre} ({pct}%)")
        else:
            textos_otros.append(f"<span style='color:#aaa;'>{nombre} (0%)</span>")
    html += " | ".join(textos_otros)
    html += "</div></div>"
    return pd.Series([texto_hover, html])


def paso_censo(nombre: str) -> gpd.GeoDataFrame:
    gdf = manzanas_region()
    objetivo = normalizar(nombre)
    sel = gdf[gdf["COMUNA"].map(normalizar) == objetivo].copy()
    if sel.empty:
        parecidas = sorted(
            {
                str(c)
                for c in gdf["COMUNA"].dropna().unique()
                if objetivo.split()[0] in normalizar(c)
            }
        )
        raise RuntimeError(
            f"No encontré '{nombre}' en el Censo. Nombres parecidos: {parecidas}"
        )

    columnas_utiles = ["MANZENT", "COMUNA", "n_per", "SHAPE"] + list(COLS_EDAD)
    sel = sel[columnas_utiles].rename(columns={"SHAPE": "geometry"})
    sel = sel.set_geometry("geometry")

    sel["n_per"] = sel["n_per"].fillna(0)
    for col in COLS_EDAD:
        sel[col] = sel[col].fillna(0)

    sel[["top_edades", "html_popup"]] = sel.apply(generar_etiquetas, axis=1)

    if sel.crs is not None and sel.crs.to_epsg() != 4326:
        sel = sel.to_crs(4326)
    sel["geometry"] = sel["geometry"].simplify(0.0001, preserve_topology=True)

    return sel[
        ["MANZENT", "n_per", "n_edad_60_mas", "top_edades", "html_popup", "geometry"]
    ].copy()


# ------------------------------------------------------------ 2) TEMPERATURA
_ee_listo = False


def iniciar_ee():
    global _ee_listo
    if _ee_listo:
        return
    import ee

    try:
        ee.Initialize(project="ruta-de-calor")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project="ruta-de-calor")
    _ee_listo = True


def paso_temperatura_descargar(slug: str, forzar: bool) -> Path:
    ruta_limite = PROCESSED / f"{slug}.geojson"
    ruta_tif = RAW / f"{slug}_lst_verano_2024.tif"
    if ruta_tif.exists() and not forzar:
        print(f"   Ya existe {ruta_tif.name}; no se vuelve a descargar (usa --forzar).")
        return ruta_tif

    import ee
    import geemap

    iniciar_ee()
    os.makedirs(RAW, exist_ok=True)

    limite = gpd.read_file(ruta_limite)
    minx, miny, maxx, maxy = limite.total_bounds
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

    dataset = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(region)
        .filterDate("2024-01-01", "2024-03-31")
        .filterMetadata("CLOUD_COVER", "less_than", 5)
    )
    imagen = dataset.median()
    temp_band = imagen.select("ST_B10")
    lst_celsius = temp_band.multiply(0.00341802).add(149.0).subtract(273.15)

    print(f"   Descargando {ruta_tif.name}...")
    geemap.ee_export_image(
        lst_celsius,
        filename=str(ruta_tif),
        scale=30,
        region=region,
        file_per_band=False,
    )
    if not ruta_tif.exists():
        raise RuntimeError("Earth Engine no generó el archivo .tif")
    return ruta_tif


def paso_cruzar(gdf: gpd.GeoDataFrame, ruta_tif: Path) -> gpd.GeoDataFrame:
    from rasterstats import zonal_stats

    stats = zonal_stats(gdf, str(ruta_tif), stats="mean", nodata=0)
    gdf["temp_promedio"] = [
        s["mean"] if s["mean"] is not None else 0.0 for s in stats
    ]
    gdf["temp_promedio"] = gdf["temp_promedio"].round(1)
    return gdf


# --------------------------------------------------------------- 3) REFUGIOS
SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

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
    partes = "".join(f'nwr["{k}"="{v}"]({s},{w},{n},{e});' for (k, v) in CATEGORIAS)
    return f"[out:json][timeout:90];({partes});out center tags;"


def descargar_overpass(consulta, rondas=3):
    for ronda in range(1, rondas + 1):
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
                print(f"   Falló {url}: {err}")
                time.sleep(3)
        if ronda < rondas:
            espera = 30 * ronda
            print(f"   Todos fallaron. Reintentando en {espera} s (ronda {ronda}/{rondas})...")
            time.sleep(espera)
    raise RuntimeError("No se pudo descargar de Overpass. Intenta de nuevo en unos minutos.")


def categoria_de(tags):
    for (k, v), nombre in CATEGORIAS.items():
        if tags.get(k) == v:
            return nombre
    return None


def paso_refugios(slug: str) -> None:
    limite = PROCESSED / f"{slug}.geojson"
    salida = PROCESSED / f"{slug}_refugios.geojson"

    comuna = gpd.read_file(limite)
    if comuna.crs is None:
        comuna = comuna.set_crs(4326)
    comuna = comuna.to_crs(4326)

    minx, miny, maxx, maxy = comuna.total_bounds
    print("   Descargando desde OpenStreetMap...")
    elementos = descargar_overpass(construir_consulta((miny, minx, maxy, maxx)))
    print(f"   Elementos recibidos: {len(elementos)}")

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
        filas.append(
            {
                "nombre": tags.get("name", "(sin nombre)"),
                "categoria": cat,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "geometry": Point(lon, lat),
            }
        )

    gdf = gpd.GeoDataFrame(filas, geometry="geometry", crs=4326)
    gdf = gdf.drop_duplicates(subset=["nombre", "categoria", "lat", "lon"])

    poligono = comuna.union_all() if hasattr(comuna, "union_all") else comuna.unary_union
    gdf = gdf[gdf.within(poligono)]

    gdf.to_file(salida, driver="GeoJSON")
    print(f"   Guardado {salida.name}: {len(gdf)} refugios")
    if len(gdf):
        print("   " + gdf["categoria"].value_counts().to_string().replace("\n", "\n   "))


# ---------------------------------------------------------------------- MAIN
def procesar(nombre: str, forzar: bool) -> None:
    slug = COMUNAS[nombre]
    if not (PROCESSED / f"{slug}.geojson").exists():
        raise RuntimeError(f"Falta el límite comunal data/processed/{slug}.geojson")

    print(f"\n=== {nombre} ===")
    print("1/4 Manzanas del Censo 2024...")
    gdf = paso_censo(nombre)
    print(f"   {len(gdf)} manzanas")

    print("2/4 Temperatura satelital (Earth Engine)...")
    ruta_tif = paso_temperatura_descargar(slug, forzar)

    print("3/4 Cruzando temperatura con manzanas...")
    gdf = paso_cruzar(gdf, ruta_tif)
    salida = PROCESSED / f"{slug}_censo_manzanas.geojson"
    gdf.to_file(salida, driver="GeoJSON")
    print(f"   Guardado {salida.name}")

    print("4/4 Refugios (OpenStreetMap)...")
    paso_refugios(slug)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("comunas", nargs="*", help="Nombres de comuna")
    parser.add_argument("--nuevas", action="store_true", help="Cerro Navia, Cerrillos y Renca")
    parser.add_argument("--forzar", action="store_true", help="Volver a bajar la temperatura")
    args = parser.parse_args()

    por_norm = {normalizar(k): k for k in COMUNAS}
    pedidas = list(NUEVAS) if args.nuevas else []
    for c in args.comunas:
        nombre = por_norm.get(normalizar(c))
        if nombre is None:
            sys.exit(f"Comuna desconocida: '{c}'. Opciones: {list(COMUNAS)}")
        if nombre not in pedidas:
            pedidas.append(nombre)
    if not pedidas:
        sys.exit("Indica una comuna, por ejemplo:  python scripts/procesar_comuna.py Renca")

    resultados = {}
    for nombre in pedidas:
        try:
            procesar(nombre, args.forzar)
            resultados[nombre] = "OK"
        except Exception as err:  # seguimos con la siguiente comuna
            resultados[nombre] = f"ERROR: {err}"
            print(f"\n[ERROR en {nombre}] {err}")
        time.sleep(2)

    print("\n=== Resumen ===")
    for nombre, estado in resultados.items():
        print(f"{nombre}: {estado}")


if __name__ == "__main__":
    main()