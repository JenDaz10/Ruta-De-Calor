"""
Extrae las comunas de Cerro Navia, Cerrillos y Renca desde comunas_final.zip
(o desde data/raw/comunas.json si existe) y guarda en data/processed/:
  - cerro_navia.geojson
  - cerrillos.geojson
  - renca.geojson

Uso (desde la raíz del proyecto, con venv activo):
    python scripts/extraer_comunas.py
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping
from shapely.ops import unary_union

RAIZ = Path(__file__).parent.parent
RAW_DIR = RAIZ / "data" / "raw"
PROCESSED_DIR = RAIZ / "data" / "processed"
ZIP_ORIGINAL = RAW_DIR / "comunas_final.zip"
JSON_ALTERNATIVO = RAW_DIR / "comunas.json"

COMUNAS_OBJETIVO = {
    "cerro navia": "cerro_navia.geojson",
    "cerrillos": "cerrillos.geojson",
    "renca": "renca.geojson",
}

CANDIDATOS = [
    "EPSG:32719",
    "EPSG:32718",
    "EPSG:31979",
    "EPSG:31978",
    "EPSG:24879",
    "EPSG:24878",
    "EPSG:5361",
    "EPSG:5362",
    "EPSG:3857",
]


def cargar_gdf() -> gpd.GeoDataFrame:
    if ZIP_ORIGINAL.exists():
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(ZIP_ORIGINAL) as zf:
                zf.extractall(tmpdir)
            shp_files = list(Path(tmpdir).rglob("*.shp"))
            if not shp_files:
                sys.exit("No se encontró ningún archivo .shp dentro de comunas_final.zip")
            gdf = gpd.read_file(shp_files[0])
            if gdf.crs is None:
                for codigo in CANDIDATOS:
                    try:
                        prueba = gdf.set_crs(codigo, allow_override=True).to_crs("EPSG:4326")
                        minx, miny, maxx, maxy = prueba.total_bounds
                        if -72 <= minx and maxx <= -69 and -35 <= miny and maxy <= -32:
                            gdf = prueba
                            break
                    except Exception:
                        continue
            else:
                gdf = gdf.to_crs("EPSG:4326")
            return gdf

    if JSON_ALTERNATIVO.exists():
        gdf = gpd.read_file(JSON_ALTERNATIVO)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")
        return gdf

    sys.exit(
        f"No encontré {ZIP_ORIGINAL} ni {JSON_ALTERNATIVO}. "
        "Deja comunas_final.zip en data/raw/comunas_final.zip."
    )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    gdf = cargar_gdf()

    # Buscar columna de nombre de comuna
    col_comuna = None
    for col in gdf.columns:
        if col.lower() in {"comuna", "nom_comuna", "cut_com", "nombre"}:
            col_comuna = col
            break

    if col_comuna is None:
        # Fallback: buscar columna de texto que contenga alguna comuna objetivo
        for col in gdf.select_dtypes(include="object").columns:
            valores = gdf[col].dropna().astype(str).str.strip().str.lower()
            if any(c in valores.values for c in COMUNAS_OBJETIVO):
                col_comuna = col
                break

    if col_comuna is None:
        sys.exit(f"No pude identificar la columna de comuna. Columnas: {list(gdf.columns)}")

    gdf["_comuna_norm"] = gdf[col_comuna].astype(str).str.strip().str.lower()

    for nombre_norm, archivo_salida in COMUNAS_OBJETIVO.items():
        sub = gdf[gdf["_comuna_norm"] == nombre_norm]
        if sub.empty:
            sub = gdf[gdf["_comuna_norm"].str.contains(nombre_norm, na=False)]
        if sub.empty:
            print(f"[AVISO] No se encontró la comuna '{nombre_norm}'.")
            continue

        geom = unary_union(sub.geometry).simplify(0.0001, preserve_topology=True)
        nombre_display = sub[col_comuna].iloc[0]
        salida_path = PROCESSED_DIR / archivo_salida

        geojson_obj = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"comuna": nombre_display, "fuente": "BCN"},
                    "geometry": mapping(geom),
                }
            ],
        }
        with open(salida_path, "w", encoding="utf-8") as f:
            json.dump(geojson_obj, f)

        c = geom.centroid
        print(f"Generado {salida_path} | centro (lon, lat): ({c.x:.4f}, {c.y:.4f})")


if __name__ == "__main__":
    main()