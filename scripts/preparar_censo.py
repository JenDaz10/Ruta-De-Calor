import pandas as pd
import geopandas as gpd
from pathlib import Path

# 1. Definir rutas
RAIZ = Path(__file__).parent.parent
RUTA_RAW = RAIZ / "data" / "raw" / "Cartografía_censo2024_R13" / "Cartografía_censo2024_R13_Manzanas.parquet"
RUTA_PROCESSED = RAIZ / "data" / "processed" / "pudahuel_censo_manzanas.geojson"

print("1. Cargando cartografía regional del Censo 2024 (Manzanas)...")
gdf = gpd.read_parquet(RUTA_RAW)

print("2. Filtrando la comuna de Pudahuel...")
gdf_pudahuel = gdf[gdf['COMUNA'] == 'PUDAHUEL'].copy()

print("3. Calculando desgloses y generando HTML interactivo...")
cols_edad = {
    'n_edad_0_5': '0 a 5 años',
    'n_edad_6_13': '6 a 13 años',
    'n_edad_14_17': '14 a 17 años',
    'n_edad_18_24': '18 a 24 años',
    'n_edad_25_44': '25 a 44 años',
    'n_edad_45_59': '45 a 59 años',
    'n_edad_60_mas': '60+ años'
}

columnas_utiles = ['MANZENT', 'COMUNA', 'n_per', 'SHAPE'] + list(cols_edad.keys())
gdf_pudahuel = gdf_pudahuel[columnas_utiles]
gdf_pudahuel = gdf_pudahuel.rename(columns={'SHAPE': 'geometry'})
gdf_pudahuel = gdf_pudahuel.set_geometry('geometry')

# Llenar nulos
gdf_pudahuel['n_per'] = gdf_pudahuel['n_per'].fillna(0)
for col in cols_edad.keys():
    gdf_pudahuel[col] = gdf_pudahuel[col].fillna(0)

# Función para armar los textos
def generar_etiquetas(row):
    total = row['n_per']
    if total <= 0:
        return pd.Series(["Sin población", "<div style='min-width: 180px;'><i>Manzana sin población residencial</i></div>"])
    
    # Extraer y ordenar valores de mayor a menor
    valores = [(nombre, row[col]) for col, nombre in cols_edad.items()]
    valores.sort(key=lambda x: x[1], reverse=True)
    
    # --- A) Texto para pasar el mouse (Tooltip - Solo Top 3) ---
    textos_top = []
    for nombre, valor in valores[:3]:
        if valor > 0:
            pct = round((valor / total) * 100, 1)
            textos_top.append(f"{nombre} ({pct}%)")
    texto_hover = " | ".join(textos_top) if textos_top else "Sin datos"
    
    # --- B) Cuadro HTML para el clic (Diseño fijo a dos niveles) ---
    html = "<div style='min-width: 230px; font-family: sans-serif;'>"
    html += f"<b>Población Total: {int(total)} hab</b><hr style='margin: 5px 0;'>"
    
    # 1. Top 3 destacado en lista
    html += "<b>Top 3 Edades:</b><br>"
    html += "<ul style='margin-top:5px; margin-bottom:10px; padding-left:20px;'>"
    for nombre, valor in valores[:3]:
        if valor > 0:
            pct = round((valor / total) * 100, 1)
            html += f"<li>{nombre}: <b>{pct}%</b> <span style='color:#555;'>({int(valor)} hab)</span></li>"
        else:
            html += f"<li><span style='color:#aaa;'>{nombre}: 0%</span></li>"
    html += "</ul>"
    
    # 2. Bloque compacto para los 4 restantes (siempre visible, pero secundario)
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

# Aplicar la función y crear dos columnas nuevas
gdf_pudahuel[['top_edades', 'html_popup']] = gdf_pudahuel.apply(generar_etiquetas, axis=1)

print("4. Simplificando geometrías y guardando...")
gdf_pudahuel['geometry'] = gdf_pudahuel['geometry'].simplify(0.0001, preserve_topology=True)

# Guardamos solo lo necesario
gdf_final = gdf_pudahuel[['MANZENT', 'n_per', 'n_edad_60_mas', 'top_edades', 'html_popup', 'geometry']]
gdf_final.to_file(RUTA_PROCESSED, driver="GeoJSON")

print("¡Proceso terminado con éxito!")