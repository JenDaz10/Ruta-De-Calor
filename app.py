"""
Ruta del Calor - MVP Sprint 1 (prototipo Streamlit + Folium)
Visor territorial con varias comunas a la vez y capas activables.

- Límite comunal: data/processed/<comuna>.geojson (WGS84).
- Manzanas con temperatura LST + Censo 2024: data/processed/<comuna>_censo_manzanas.geojson
- Refugios (OpenStreetMap): data/processed/<comuna>_refugios.geojson
  Si un archivo no existe para una comuna, esa capa no se muestra para ella.
- Estaciones meteorológicas (RedMeteo): se consultan en vivo por internet
  (scripts/estaciones_redmeteo.py), no hay archivo de datos.

Al abrir el visor no hay comunas ni capas activas: la persona elige.

Ejecutar:  python -m streamlit run app.py
"""
import json
import math
import unicodedata
from datetime import datetime
from pathlib import Path

import branca.colormap as cm
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from shapely.geometry import shape
from shapely.ops import unary_union
from streamlit_folium import st_folium

# Estaciones RedMeteo (módulo del compañero). Si falta el archivo o una
# librería, la app sigue funcionando y solo se desactiva esa capa.
try:
    from scripts.estaciones_redmeteo import (
        agregar_estaciones,
        cargar_estaciones,
        leyenda_estaciones_html,
    )

    ESTACIONES_DISPONIBLES = True
except Exception:
    ESTACIONES_DISPONIBLES = False

st.set_page_config(page_title="Ruta del Calor", page_icon="🔥", layout="wide")

DIR_PROCESSED = Path(__file__).parent / "data" / "processed"

# Margen (en metros) alrededor de las comunas elegidas para buscar estaciones
ESTACIONES_BUFFER_M = 0

# Comunas disponibles: nombre que se muestra -> prefijo de los archivos
COMUNAS = {
    "Pudahuel": "pudahuel",
    "Cerro Navia": "cerro_navia",
    "Cerrillos": "cerrillos",
    "Renca": "renca",
}

COLORES_REFUGIO = {
    "Hospital": "#d62728",
    "Clínica / Cesfam": "#e377c2",
    "Comisaría / Carabineros": "#1f77b4",
    "Bomberos": "#ff7f0e",
    "Colegio": "#9467bd",
    "Jardín infantil": "#bcbd22",
    "Educación superior": "#8c564b",
    "Centro comunitario": "#17becf",
    "Biblioteca": "#7f7f7f",
    "Municipalidad": "#393b79",
    "Parque / plaza": "#2ca02c",
    "Recinto deportivo": "#006d2c",
}


def ruta_datos(slug: str, sufijo: str = "") -> Path:
    """data/processed/<slug>.geojson  o  data/processed/<slug>_<sufijo>.geojson"""
    nombre = f"{slug}_{sufijo}.geojson" if sufijo else f"{slug}.geojson"
    return DIR_PROCESSED / nombre


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres de comuna."""
    sin_tildes = unicodedata.normalize("NFD", str(texto))
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return sin_tildes.lower()


# ---------------------------------------------------------------- Carga de datos
@st.cache_data
def cargar_limite(ruta: str, nombre_comuna: str):
    """Lee el GeoJSON y se queda con la comuna pedida (acepta archivo con varias comunas)."""
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    feats = data["features"] if data.get("type") == "FeatureCollection" else [data]
    buscado = normalizar(nombre_comuna)
    elegidas = []
    for ft in feats:
        props = ft.get("properties") or {}
        texto = normalizar(" ".join(str(v) for v in props.values()))
        if buscado in texto:
            elegidas.append(ft)
    if not elegidas and len(feats) == 1:
        elegidas = feats  # archivo ya filtrado y sin atributos
    if not elegidas:
        return None
    return {"type": "FeatureCollection", "features": elegidas}


def geometria_limite(nombre: str):
    """Devuelve (geometria, geojson_dict) del límite de una comuna, o None si no se puede."""
    ruta = ruta_datos(COMUNAS[nombre])
    if not ruta.exists():
        return None
    fc = cargar_limite(str(ruta), nombre)
    if fc is None:
        return None
    geom = unary_union([shape(f["geometry"]) for f in fc["features"]])
    minx, miny, maxx, maxy = geom.bounds
    if max(abs(minx), abs(maxx)) > 180 or max(abs(miny), abs(maxy)) > 90:
        return None  # coordenadas proyectadas (UTM), no sirven
    return geom, fc


@st.cache_data
def cargar_censo_real(ruta: str):
    gdf = gpd.read_file(ruta)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


@st.cache_data
def cargar_refugios(ruta: str):
    """Lista de puntos de refugio."""
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["features"]


def datos_comuna(nombre: str):
    """Todos los datos disponibles de una comuna (None en lo que falte)."""
    limite = geometria_limite(nombre)
    if limite is None:
        return None
    geom, fc = limite
    slug = COMUNAS[nombre]
    ruta_censo = ruta_datos(slug, "censo_manzanas")
    ruta_ref = ruta_datos(slug, "refugios")
    return {
        "nombre": nombre,
        "geom": geom,
        "fc": fc,
        "censo": cargar_censo_real(str(ruta_censo)) if ruta_censo.exists() else None,
        "refugios": cargar_refugios(str(ruta_ref)) if ruta_ref.exists() else None,
    }


def agregar_refugios(mapa, features, categorias_visibles):
    """Dibuja un círculo de color por cada refugio de las categorías elegidas."""
    for ft in features:
        p = ft["properties"]
        if p["categoria"] not in categorias_visibles:
            continue
        lon, lat = ft["geometry"]["coordinates"]
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="white",
            weight=1,
            fill=True,
            fill_color=COLORES_REFUGIO.get(p["categoria"], "#555555"),
            fill_opacity=0.95,
            tooltip=p["nombre"],
            popup=folium.Popup(
                f"<b>{p['nombre']}</b><br>{p['categoria']}", max_width=250
            ),
        ).add_to(mapa)


def color_por_temperatura(t: float) -> str:
    if t >= 36:
        return "#d7191c"  # Crítico / Rojo
    if t >= 33:
        return "#f46d43"  # Alto / Naranja
    return "#fdae61"      # Moderado / Amarillo


# ---------------------------------------------------------------- Panel lateral (parte 1)
st.sidebar.title("🔥 Ruta del Calor")
st.sidebar.caption("MVP Sprint 1 · Pudahuel, Cerro Navia, Cerrillos y Renca")

elegidas = st.sidebar.multiselect(
    "Comunas",
    list(COMUNAS.keys()),
    default=[],
    help="Puedes elegir una o varias comunas a la vez.",
)

# ---------------------------------------------------------------- Datos de las comunas elegidas
datos = {}
for nombre in elegidas:
    d = datos_comuna(nombre)
    if d is None:
        st.sidebar.error(f"No pude cargar el límite comunal de {nombre}.")
    else:
        datos[nombre] = d

# Se juntan los datos de todas las comunas elegidas en una sola tabla / lista
censos = []
refugios = []
for d in datos.values():
    if d["censo"] is not None:
        g = d["censo"].copy()
        g["comuna"] = d["nombre"]
        censos.append(g)
    if d["refugios"]:
        refugios.extend(d["refugios"])

gdf_censo = (
    gpd.GeoDataFrame(
        pd.concat(censos, ignore_index=True), geometry="geometry", crs="EPSG:4326"
    )
    if censos
    else None
)
tiene_censo = gdf_censo is not None
tiene_refugios = len(refugios) > 0
hay_comunas = len(datos) > 0

# ---------------------------------------------------------------- Panel lateral (parte 2)
st.sidebar.markdown("### Capas")

# Las capas de datos arrancan apagadas; solo se bloquean si hay comunas elegidas sin esos datos
ver_limite = st.sidebar.checkbox("Límite comunal", value=True)
ver_termico = st.sidebar.checkbox(
    "Islas de Calor (Temperatura LST)",
    value=False,
    disabled=hay_comunas and not tiene_censo,
)
ver_mayores = st.sidebar.checkbox(
    "Demografía / Población > 60 años",
    value=False,
    disabled=hay_comunas and not tiene_censo,
)
ver_refugios = st.sidebar.checkbox(
    "Puntos de refugio",
    value=False,
    disabled=hay_comunas and not tiene_refugios,
)

# Por seguridad: ninguna capa de datos se activa si no hay archivos para lo elegido
ver_termico = ver_termico and tiene_censo
ver_mayores = ver_mayores and tiene_censo
ver_refugios = ver_refugios and tiene_refugios

# Tipos de refugio: al activar la capa salen todos (sin filtro); la persona puede quitar
categorias_elegidas = []
if ver_refugios:
    todas_las_categorias = sorted({ft["properties"]["categoria"] for ft in refugios})
    categorias_elegidas = st.sidebar.multiselect(
        "Tipos de refugio",
        todas_las_categorias,
        default=todas_las_categorias,
        key="cat_" + "_".join(COMUNAS[n] for n in datos),
    )

# Estaciones meteorológicas (RedMeteo): apagada al abrir; necesita comunas elegidas
ver_estaciones = st.sidebar.checkbox(
    "Estaciones meteorológicas (RedMeteo)",
    value=False,
    disabled=not (hay_comunas and ESTACIONES_DISPONIBLES),
    help="Temperatura del aire medida por estaciones aficionadas (datos no oficiales). "
    "Elige primero una o más comunas.",
)
ver_estaciones = ver_estaciones and hay_comunas and ESTACIONES_DISPONIBLES
if not ESTACIONES_DISPONIBLES:
    st.sidebar.caption(
        "Estaciones no disponibles: falta scripts/estaciones_redmeteo.py o una librería."
    )

max_horas_est = 3
estaciones = None
if ver_estaciones:
    max_horas_est = st.sidebar.slider("Antigüedad máxima del dato (horas)", 1, 24, 3)
    geom_estaciones = unary_union([d["geom"] for d in datos.values()])
    try:
        estaciones = cargar_estaciones(
            geom_estaciones, buffer_m=ESTACIONES_BUFFER_M, max_horas=max_horas_est
        )
    except Exception:
        estaciones = None
    if estaciones is None:
        st.sidebar.warning("No se pudo conectar con RedMeteo. Intenta más tarde.")
    elif not estaciones:
        st.sidebar.info(
            "Sin estaciones con datos recientes en las comunas elegidas "
            f"(+{ESTACIONES_BUFFER_M // 1000} km)."
        )

# Avisos de datos faltantes
for nombre, d in datos.items():
    faltan = []
    if d["censo"] is None:
        faltan.append("temperatura y demografía")
    if d["refugios"] is None:
        faltan.append("refugios")
    if faltan:
        st.sidebar.warning(f"{nombre}: todavía no hay datos de {' ni de '.join(faltan)}.")

estilo_base = st.sidebar.selectbox(
    "Mapa base", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"]
)

# Filtro de calor: arranca en el mínimo de los datos, o sea, sin filtrar nada
st.sidebar.markdown("### Filtro de Calor")
if tiene_censo:
    t_validas = gdf_censo.loc[gdf_censo["temp_promedio"] > 0, "temp_promedio"]
    t_lo = float(math.floor(t_validas.min())) if not t_validas.empty else 25.0
    t_hi = float(math.ceil(t_validas.max())) if not t_validas.empty else 42.0
    if t_hi <= t_lo:
        t_hi = t_lo + 1.0
else:
    t_lo, t_hi = 25.0, 42.0
temp_min = st.sidebar.slider(
    "Temperatura mínima (°C)",
    min_value=t_lo,
    max_value=t_hi,
    value=t_lo,
    step=0.5,
    disabled=not ver_termico,
)

if tiene_censo:
    st.sidebar.markdown("---")
    st.sidebar.info(
        "⚠️ Datos actualizados con temperatura satelital real LST (Landsat 8) "
        "y demografía del Censo 2024 (INE)."
    )

# ---------------------------------------------------------------- Mapa
# Encuadre: las comunas elegidas o, si no hay ninguna, las cuatro juntas
if hay_comunas:
    geom_vista = unary_union([d["geom"] for d in datos.values()])
else:
    geoms = []
    for nombre in COMUNAS:
        limite = geometria_limite(nombre)
        if limite is not None:
            geoms.append(limite[0])
    if not geoms:
        st.error("No encontré ningún límite comunal en data/processed.")
        st.stop()
    geom_vista = unary_union(geoms)

centro = geom_vista.centroid
mapa = folium.Map(
    location=[centro.y, centro.x],
    zoom_start=12,
    tiles=estilo_base,
    control_scale=True,
)
minx, miny, maxx, maxy = geom_vista.bounds
mapa.fit_bounds([[miny, minx], [maxy, maxx]])

if ver_limite:
    for d in datos.values():
        folium.GeoJson(
            d["fc"],
            name=f"Límite {d['nombre']}",
            style_function=lambda _: {
                "color": "#222222",
                "weight": 3,
                "fillOpacity": 0.03,
            },
            tooltip=f"Comuna de {d['nombre']}",
        ).add_to(mapa)

# --- CAPA 1: Islas de Calor (Temperatura Satelital LST) ---
gdf_filtrado = None
if ver_termico:
    gdf_filtrado = gdf_censo[gdf_censo["temp_promedio"] >= temp_min]
    if not gdf_filtrado.empty:
        capa_termica = folium.FeatureGroup(name="Islas de Calor (LST)")
        folium.GeoJson(
            gdf_filtrado[["comuna", "MANZENT", "temp_promedio", "geometry"]],
            name="Manzanas Térmicas",
            style_function=lambda feature: {
                "fillColor": color_por_temperatura(feature["properties"]["temp_promedio"]),
                "color": "#333333",
                "weight": 0.3,
                "fillOpacity": 0.75,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["comuna", "MANZENT", "temp_promedio"],
                aliases=["Comuna:", "Manzana:", "Temp. Promedio (°C):"],
                localize=True,
            ),
        ).add_to(capa_termica)
        capa_termica.add_to(mapa)

# --- CAPA 2: Demografía / Adultos Mayores (Censo 2024), color según cantidad ---
if ver_mayores:
    valores = gdf_censo["n_edad_60_mas"].fillna(0)
    positivos = valores[valores > 0]
    # Tope en el percentil 95 para que unas pocas manzanas extremas no aplasten la escala
    tope = max(float(positivos.quantile(0.95)), 2.0) if not positivos.empty else 2.0
    escala = cm.LinearColormap(["#deebf7", "#6baed6", "#08306b"], vmin=1, vmax=tope)

    def estilo_censo(feature):
        n = feature["properties"].get("n_edad_60_mas") or 0
        if n <= 0:
            return {"fillColor": "transparent", "color": "#2b5c8f",
                    "weight": 0.4, "fillOpacity": 0}
        return {"fillColor": escala(min(n, tope)), "color": "#2b5c8f",
                "weight": 0.4, "fillOpacity": 0.75}

    capa_censo = folium.FeatureGroup(name="Adultos Mayores (Censo)")
    folium.GeoJson(
        gdf_censo[["comuna", "MANZENT", "n_per", "n_edad_60_mas",
                   "top_edades", "html_popup", "geometry"]],
        name="Manzanas Censo",
        style_function=estilo_censo,
        tooltip=folium.GeoJsonTooltip(
            fields=["comuna", "MANZENT", "n_per", "n_edad_60_mas", "top_edades"],
            aliases=["Comuna:", "Manzana:", "Población total:",
                     "Personas 60+:", "Mayoría de edad:"],
            localize=True,
        ),
        popup=folium.GeoJsonPopup(fields=["html_popup"], labels=False, max_width=300),
    ).add_to(capa_censo)
    capa_censo.add_to(mapa)

# --- CAPA 3: Puntos de refugio (encima de las capas de polígonos) ---
if ver_refugios and categorias_elegidas:
    agregar_refugios(mapa, refugios, categorias_elegidas)

# --- CAPA 4: Estaciones meteorológicas RedMeteo (al final, quedan encima de todo) ---
if ver_estaciones and estaciones is not None:
    if estaciones:
        agregar_estaciones(mapa, estaciones)
    mapa.get_root().html.add_child(folium.Element(leyenda_estaciones_html()))

# --- Leyenda de temperatura / población (solo de las capas activas) ---
partes_leyenda = []
if ver_termico:
    partes_leyenda.append(
        "<b>Temperatura Satelital LST</b><br>"
        '<span style="color:#d7191c">■</span> ≥ 36 °C (Crítico)<br>'
        '<span style="color:#f46d43">■</span> 33 – 36 °C (Alto)<br>'
        '<span style="color:#fdae61">■</span> &lt; 33 °C (Moderado)'
    )
if ver_mayores:
    partes_leyenda.append(
        "<b>Población &gt; 60 años</b> (por manzana)<br>"
        '<div style="width:140px;height:10px;background:linear-gradient(to right,#deebf7,#6baed6,#08306b);"></div>'
        '<div style="display:flex;justify-content:space-between;width:140px;font-size:11px;"><span>pocas</span><span>muchas</span></div>'
    )
if partes_leyenda:
    leyenda = (
        '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999; '
        "background: white; padding: 10px 12px; border: 1px solid #999; "
        'border-radius: 6px; font-size: 13px; color: #222;">'
        + '<hr style="margin: 4px 0;">'.join(partes_leyenda)
        + "</div>"
    )
    mapa.get_root().html.add_child(folium.Element(leyenda))

# --- Leyenda de refugios (esquina inferior derecha, solo categorías visibles) ---
if ver_refugios and categorias_elegidas:
    filas_leyenda = "".join(
        f'<span style="color:{COLORES_REFUGIO.get(c, "#555555")}">●</span> {c}<br>'
        for c in categorias_elegidas
    )
    leyenda_refugios = f"""
<div style="position: fixed; bottom: 30px; right: 30px; z-index: 9999;
 background: white; padding: 10px 12px; border: 1px solid #999;
 border-radius: 6px; font-size: 13px; color: #222;
 max-height: 300px; overflow-y: auto;">
<b>Puntos de refugio</b><br>{filas_leyenda}
</div>
"""
    mapa.get_root().html.add_child(folium.Element(leyenda_refugios))

# Quitar el borde negro de foco al hacer clic en polígonos
estilo_sin_borde = """
<style>
.leaflet-interactive:focus,
.leaflet-container path:focus,
.leaflet-container svg:focus {
    outline: none !important;
}
</style>
"""
mapa.get_root().header.add_child(folium.Element(estilo_sin_borde))

# ---------------------------------------------------------------- Página principal
st.title("Ruta del Calor – Visor territorial")
st.caption(
    "Islas de calor urbano y vulnerabilidad social · "
    + (", ".join(datos) if hay_comunas else "Pudahuel, Cerro Navia, Cerrillos y Renca")
    + " (MVP)"
)

if not hay_comunas:
    st.info(
        "👈 Elige una o más comunas en el panel izquierdo y luego activa "
        "las capas que quieras ver."
    )

c1, c2, c3, c4 = st.columns(4)

if ver_termico and gdf_filtrado is not None and not gdf_filtrado.empty:
    n_manzanas_visibles = len(gdf_filtrado)
    temp_max_val = f"{gdf_filtrado['temp_promedio'].max():.1f} °C"
    temp_prom_val = f"{gdf_filtrado['temp_promedio'].mean():.1f} °C"
elif ver_termico:
    n_manzanas_visibles, temp_max_val, temp_prom_val = 0, "—", "—"
else:
    n_manzanas_visibles, temp_max_val, temp_prom_val = "—", "—", "—"

if ver_refugios:
    n_refugios_visibles = sum(
        1 for ft in refugios if ft["properties"]["categoria"] in categorias_elegidas
    )
else:
    n_refugios_visibles = "—"

c1.metric("Manzanas visibles", n_manzanas_visibles)
c2.metric("Temp. máxima", temp_max_val)
c3.metric("Temp. promedio", temp_prom_val)
c4.metric("Refugios visibles", n_refugios_visibles)

clave_mapa = "mapa_" + ("_".join(COMUNAS[n] for n in datos) if hay_comunas else "todas")
st_folium(mapa, width=None, height=600, returned_objects=[], key=clave_mapa)

with st.expander("Fuente y fecha de los datos"):
    st.write("**Límite comunal:** archivo oficial (División Político Administrativa, BCN).")
    st.write(
        "**Población:** datos demográficos reales extraídos de la cartografía de manzanas "
        "del Censo 2024 (INE).\n\n"
        "**Temperatura:** Superficie Terrestre (LST) extraída de imágenes satelitales "
        "Landsat 8 de verano a través de Google Earth Engine. Es temperatura de la "
        "superficie (no del aire) a la hora de paso del satélite (media mañana)."
    )
    st.write("**Refugios:** OpenStreetMap (colaborativo, puede estar incompleto).")
    st.write(
        "**Estaciones meteorológicas:** Red Meteorológica Aficionada de Chile. (2019). "
        "Sitio web RedMeteo. Red Ciudadana De Estaciones Meteorológicas. "
        f"Consultado {datetime.now():%d-%m-%Y}, desde https://www.redmeteo.cl/. "
        "Datos no oficiales. Es temperatura del aire, medida en vivo."
    )