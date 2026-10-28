"""
Ruta del Calor - MVP Sprint 1 (prototipo Streamlit + Folium)
Visor centrado en la comuna de Pudahuel con capas activables.

- Límite comunal: archivo OFICIAL en  data/pudahuel.geojson  (ver instrucciones).
- Temperatura y población > 65 años: datos SIMULADOS (demo), generados
  siempre DENTRO del límite de la comuna.

Ejecutar:  python -m streamlit run app.py
"""
import json
import random
from pathlib import Path

import folium
import streamlit as st
from folium.plugins import HeatMap
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union
from streamlit_folium import st_folium

import geopandas as gpd

st.set_page_config(page_title="Ruta del Calor", page_icon="🔥", layout="wide")

RUTA_LIMITE = Path(__file__).parent / "data" / "processed" / "pudahuel.geojson"
NOMBRE_COMUNA = "pudahuel"
# Solo se usa si falta el archivo oficial (caja aproximada, NO es el límite real)
CAJA_FALLBACK = (-70.88, -33.50, -70.68, -33.36)  # minx, miny, maxx, maxy


# ---------------------------------------------------------------- Límite comunal
@st.cache_data
def cargar_limite(ruta: str):
    """Lee el GeoJSON y se queda con Pudahuel (acepta archivo de todo Chile)."""
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    feats = data["features"] if data.get("type") == "FeatureCollection" else [data]
    elegidas = []
    for ft in feats:
        props = ft.get("properties") or {}
        texto = " ".join(str(v) for v in props.values()).lower()
        if NOMBRE_COMUNA in texto:
            elegidas.append(ft)
    if not elegidas and len(feats) == 1:
        elegidas = feats  # archivo ya filtrado y sin atributos
    if not elegidas:
        return None
    return {"type": "FeatureCollection", "features": elegidas}


def obtener_geometria():
    """Devuelve (geometria, geojson_dict | None, es_oficial)."""
    if RUTA_LIMITE.exists():
        fc = cargar_limite(str(RUTA_LIMITE))
        if fc is None:
            st.error(
                "El archivo data/pudahuel.geojson no contiene la comuna de Pudahuel."
            )
            st.stop()
        geom = unary_union([shape(f["geometry"]) for f in fc["features"]])
        minx, miny, maxx, maxy = geom.bounds
        if max(abs(minx), abs(maxx)) > 180 or max(abs(miny), abs(maxy)) > 90:
            st.error(
                "El GeoJSON está en coordenadas proyectadas (UTM). "
                "Expórtalo de nuevo en WGS84 (lat/lon). Ver instrucciones."
            )
            st.stop()
        return geom, fc, True
    return box(*CAJA_FALLBACK), None, False

@st.cache_data
def cargar_censo_real():
    ruta = Path(__file__).parent / "data" / "processed" / "pudahuel_censo_manzanas.geojson"
    if ruta.exists():
        return gpd.read_file(ruta)
    return None

# Y llámala en la sección de "Datos base" (cerca de la línea 85):
gdf_censo = cargar_censo_real()

# ---------------------------------------------------------------- Datos simulados
def punto_dentro(rng, geom):
    minx, miny, maxx, maxy = geom.bounds
    while True:
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if geom.contains(p):
            return p


@st.cache_data
def generar_focos(_geom, n_focos: int = 5, seed: int = 3):
    rng = random.Random(seed)
    focos = []
    for _ in range(n_focos):
        p = punto_dentro(rng, _geom)
        focos.append((p.y, p.x))
    return focos


@st.cache_data
def generar_puntos_calor(_geom, focos, n_por_foco: int = 40, seed: int = 42):
    """Temperatura simulada (°C) a las 16:00 hrs, solo dentro de la comuna."""
    rng = random.Random(seed)
    minx, miny, maxx, maxy = _geom.bounds
    sigma = 0.05 * max(maxx - minx, maxy - miny)
    puntos = []
    for lat0, lon0 in focos:
        creados, intentos = 0, 0
        while creados < n_por_foco and intentos < n_por_foco * 30:
            intentos += 1
            lat, lon = rng.gauss(lat0, sigma), rng.gauss(lon0, sigma)
            if not _geom.contains(Point(lon, lat)):
                continue
            dist = ((lat - lat0) ** 2 + (lon - lon0) ** 2) ** 0.5
            temp = round(41 - (dist / (2 * sigma)) * 6 + rng.uniform(-1, 1), 1)
            puntos.append({"lat": lat, "lon": lon, "temp": temp})
            creados += 1
    return puntos

def color_por_temperatura(t: float) -> str:
    if t >= 36:
        return "#d7191c"  # Crítico / Rojo
    if t >= 33:
        return "#f46d43"  # Alto / Naranja
    return "#fdae61"      # Moderado / Amarillo


# ---------------------------------------------------------------- Datos base
geom, geojson_limite, es_oficial = obtener_geometria()
focos = generar_focos(geom)

# ---------------------------------------------------------------- Panel lateral
st.sidebar.title("🔥 Ruta del Calor")
st.sidebar.caption("MVP Sprint 1 · Comuna de Pudahuel")
st.sidebar.markdown("### Capas")

ver_limite = st.sidebar.checkbox("Límite comunal", value=True)
ver_termico = st.sidebar.checkbox("Islas de Calor (Temperatura LST)", value=True)
ver_mayores = st.sidebar.checkbox("Demografía / Población > 60 años", value=False)

estilo_base = st.sidebar.selectbox(
    "Mapa base", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"]
)

st.sidebar.markdown("### Filtro de Calor")
temp_min = st.sidebar.slider("Temperatura mínima (°C)", 25.0, 42.0, 28.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.info(
    "⚠️ Datos actualizados con temperatura satelital real LST (Landsat 8) "
    "y demografía del Censo 2024 (INE)."
)

# ---------------------------------------------------------------- Mapa
centro = geom.centroid
mapa = folium.Map(
    location=[centro.y, centro.x],
    zoom_start=12,
    tiles=estilo_base,
    control_scale=True,
)
minx, miny, maxx, maxy = geom.bounds
mapa.fit_bounds([[miny, minx], [maxy, maxx]])

if ver_limite:
    if geojson_limite is not None:
        folium.GeoJson(
            geojson_limite,
            name="Límite comunal",
            style_function=lambda _: {
                "color": "#222222",
                "weight": 3,
                "fillOpacity": 0.03,
            },
            tooltip="Comuna de Pudahuel",
        ).add_to(mapa)
    else:
        folium.Rectangle(
            bounds=[[miny, minx], [maxy, maxx]],
            color="#888888",
            weight=2,
            dash_array="6",
            tooltip="Caja aproximada (falta el límite oficial)",
        ).add_to(mapa)

# ---------------------------------------------------------------- Mapa
# Filtrar las manzanas de forma segura
if gdf_censo is not None:
    gdf_filtrado = gdf_censo[gdf_censo["temp_promedio"] >= temp_min]
else:
    gdf_filtrado = None

# --- CAPA 1: Islas de Calor (Temperatura Satelital LST) ---
if ver_termico and gdf_filtrado is not None and not gdf_filtrado.empty:
    capa_termica = folium.FeatureGroup(name="Islas de Calor (LST)")
    folium.GeoJson(
        gdf_filtrado,
        name="Manzanas Térmicas",
        style_function=lambda feature: {
            "fillColor": color_por_temperatura(feature["properties"]["temp_promedio"]),
            "color": "#333333",
            "weight": 0.3,
            "fillOpacity": 0.75 
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["MANZENT", "temp_promedio"],
            aliases=["Manzana:", "Temp. Promedio (°C):"],
            localize=True
        )
    ).add_to(capa_termica)
    capa_termica.add_to(mapa)

# --- CAPA 2: Demografía / Adultos Mayores (Censo 2024) ---
if ver_mayores and gdf_censo is not None:
    capa_censo = folium.FeatureGroup(name="Adultos Mayores (Censo)")
    folium.GeoJson(
        gdf_censo,
        name="Manzanas Censo",
        style_function=lambda feature: {
            "fillColor": "#4575b4" if feature.get("properties", {}).get("n_edad_60_mas", 0) > 0 else "transparent",
            "color": "#2b5c8f",
            "weight": 0.4,
            "fillOpacity": 0.6 
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["MANZENT", "n_per", "top_edades"],
            aliases=["Manzana:", "Población total:", "Mayoría de edad:"],
            localize=True
        ),
        popup=folium.GeoJsonPopup(
            fields=["html_popup"],
            labels=False,
            max_width=300
        )
    ).add_to(capa_censo)
    capa_censo.add_to(mapa)
leyenda = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
 background: white; padding: 10px 12px; border: 1px solid #999;
 border-radius: 6px; font-size: 13px; color: #222;">
<b>Temperatura Satelital LST</b><br>
<span style="color:#d7191c">■</span> ≥ 36 °C (Crítico)<br>
<span style="color:#f46d43">■</span> 33 – 36 °C (Alto)<br>
<span style="color:#fdae61">■</span> &lt; 33 °C (Moderado)<br>
<hr style="margin: 4px 0;">
<span style="color:#4575b4">■</span> Población &gt; 60 años
</div>
"""
mapa.get_root().html.add_child(folium.Element(leyenda))

# ---------------------------------------------------------------- Página principal
st.title("Ruta del Calor – Visor territorial")
st.caption("Islas de calor urbano y vulnerabilidad social · Pudahuel (MVP)")

st.info("💡 Capa demográfica actualizada con datos reales del Censo 2024.")

c1, c2, c3 = st.columns(3)

# Calculamos de forma segura solo si el DataFrame tiene datos
if ver_termico and gdf_filtrado is not None and not gdf_filtrado.empty:
    n_manzanas_visibles = len(gdf_filtrado)
    temp_max_val = gdf_filtrado["temp_promedio"].max()
    temp_prom_val = gdf_filtrado["temp_promedio"].mean()
else:
    n_manzanas_visibles = 0
    temp_max_val = 0.0
    temp_prom_val = 0.0

c1.metric("Manzanas visibles", n_manzanas_visibles)
c2.metric("Temp. máxima", f"{temp_max_val:.1f} °C")
c3.metric("Temp. promedio", f"{temp_prom_val:.1f} °C")

st_folium(mapa, width=None, height=600, returned_objects=[])

with st.expander("Fuente y fecha de los datos"):
    st.write(
        "**Límite comunal:** "
        + (
            "archivo oficial (División Político Administrativa)."
            if es_oficial
            else "pendiente (caja aproximada)."
        )
    )
    st.write(
        "**Población:** Datos demográficos reales extraídos de la cartografía de manzanas del Censo 2024 (INE).\n\n"
        "**Temperatura:** Datos de Superficie Terrestre (LST) extraídos de imágenes satelitales Landsat 8 de verano a través de Google Earth Engine."
    )
