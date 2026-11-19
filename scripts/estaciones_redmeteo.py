"""
Estaciones meteorológicas de RedMeteo (API pública) para el visor Ruta del Calor.

Módulo independiente: app.py solo necesita llamar a 3 funciones. Funciona con
cualquier comuna porque recibe su geometría (la variable `geom` de app.py).

Fuente: Red Meteorológica Aficionada de Chile (https://www.redmeteo.cl/).
La API se actualiza cada 10 minutos y trabaja en horario UTC.
Los datos NO son oficiales (ver https://redmeteo.cl/calidad.html).
"""
from datetime import datetime, timedelta, timezone
from html import escape

import folium
import geopandas as gpd
import requests
import streamlit as st
from shapely.geometry import Point

URL_ULTIMOS_DATOS = "https://redmeteo.cl/publicapi/last-data.json"
CRS_METROS = 32719  # UTM zona 19S (Chile central), sirve para buffers en metros

# Hora local de Chile. En Windows requiere:  python -m pip install tzdata
try:
    from zoneinfo import ZoneInfo

    TZ_CHILE = ZoneInfo("America/Santiago")
except Exception:  # sin tzdata: aproximación (UTC-3, horario de verano)
    TZ_CHILE = timezone(timedelta(hours=-3))

# Bits del índice QC de RedMeteo (0 = correcto). Para temperatura descartamos:
FLAG_TEMP = 0x01   # temperatura fuera de rango (< -25 °C o > 45 °C)
FLAG_NULL = 0x80   # sensores exteriores sin datos


# ---------------------------------------------------------------- Descarga
@st.cache_data(ttl=600, show_spinner=False)  # la API se actualiza cada 10 min
def _descargar():
    r = requests.get(
        URL_ULTIMOS_DATOS,
        timeout=20,
        headers={"User-Agent": "RutaCalor-proyecto-UDP"},
    )
    r.raise_for_status()
    return r.json()


def descargar_observaciones():
    """Lista de observaciones, o None si la API no responde (la app no se cae)."""
    try:
        return _descargar()
    except Exception:
        return None


# ---------------------------------------------------------------- Filtrado
def cargar_estaciones(geom, buffer_m=3000, max_horas=3):
    """
    Estaciones con dato de temperatura válido y reciente, dentro de la comuna
    (`geom`, en lat/lon) más un margen de `buffer_m` metros alrededor.

    Devuelve una lista de diccionarios, o None si falló la descarga.
    """
    obs = descargar_observaciones()
    if obs is None:
        return None

    zona = (
        gpd.GeoSeries([geom], crs=4326)
        .to_crs(CRS_METROS)
        .buffer(buffer_m)
        .to_crs(4326)
        .iloc[0]
    )
    ahora = datetime.now(timezone.utc)
    estaciones = []

    for o in obs:
        temp, lat, lon = o.get("temperatura"), o.get("latitud"), o.get("longitud")
        if temp is None or lat is None or lon is None:
            continue
        qc = o.get("QC") or 0
        if qc & (FLAG_TEMP | FLAG_NULL):
            continue
        try:
            dt = datetime.fromisoformat(o["fecha_hora"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            continue
        if ahora - dt > timedelta(hours=max_horas):
            continue
        if not zona.covers(Point(lon, lat)):
            continue
        estaciones.append(
            {
                "id": o.get("id_estacion"),
                "nombre": o.get("nombre") or "(sin nombre)",
                "lat": lat,
                "lon": lon,
                "temp": float(temp),
                "humedad": o.get("humedad"),
                "viento": o.get("velocidad_viento"),
                "radiacion": o.get("radiacion_solar"),
                "hora_local": dt.astimezone(TZ_CHILE),
                "qc": qc,
            }
        )
    return estaciones


# ---------------------------------------------------------------- Dibujo
def color_temperatura_aire(t):
    """Temperatura del AIRE (no la de superficie del satélite)."""
    if t >= 35:
        return "#d7191c"
    if t >= 30:
        return "#f46d43"
    if t >= 25:
        return "#fdae61"
    if t >= 20:
        return "#abd9e9"
    return "#74add1"


def _fmt(valor, unidad):
    return "s/d" if valor is None else f"{valor:g} {unidad}"


def agregar_estaciones(mapa, estaciones):
    """Dibuja cada estación como un círculo de color con su temperatura."""
    for e in estaciones:
        color = color_temperatura_aire(e["temp"])
        icono = (
            f'<div style="background:{color};color:#111;border:2px solid #222;'
            "border-radius:50%;width:34px;height:34px;line-height:30px;"
            'text-align:center;font-weight:700;font-size:12px;">'
            f'{e["temp"]:.0f}°</div>'
        )
        popup = (
            f"<b>{escape(e['nombre'])}</b><br>"
            f"Temperatura del aire: <b>{e['temp']:.1f} °C</b><br>"
            f"Humedad: {_fmt(e['humedad'], '%')}<br>"
            f"Viento: {_fmt(e['viento'], 'm/s')}<br>"
            f"Radiación solar: {_fmt(e['radiacion'], 'W/m²')}<br>"
            f"<small>Medido: {e['hora_local']:%d-%m-%Y %H:%M} (hora de Chile)<br>"
            f"Fuente: RedMeteo (no oficial)</small>"
        )
        folium.Marker(
            location=[e["lat"], e["lon"]],
            icon=folium.DivIcon(html=icono, icon_size=(34, 34), icon_anchor=(17, 17)),
            tooltip=f"{e['nombre']}: {e['temp']:.1f} °C",
            popup=folium.Popup(popup, max_width=260),
        ).add_to(mapa)


def leyenda_estaciones_html():
    """Leyenda para agregar al mapa (esquina superior derecha)."""
    filas = "".join(
        f'<span style="color:{c}">●</span> {texto}<br>'
        for c, texto in [
            ("#d7191c", "≥ 35 °C"),
            ("#f46d43", "30 – 35 °C"),
            ("#fdae61", "25 – 30 °C"),
            ("#abd9e9", "20 – 25 °C"),
            ("#74add1", "&lt; 20 °C"),
        ]
    )
    return f"""
<div style="position: fixed; top: 80px; right: 12px; z-index: 9999;
 background: white; padding: 10px 12px; border: 1px solid #999;
 border-radius: 6px; font-size: 13px; color: #222;">
<b>Estaciones (aire)</b><br>{filas}
</div>
"""