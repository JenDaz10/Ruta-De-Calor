# Proyecto Ruta del Calor
Geovisor territorial centrado en la comuna de Pudahuel para visualizar el cruce entre riesgo térmico (islas de calor) y vulnerabilidad sociodemográfica. 

Este prototipo está construido con **Python, Streamlit y Folium**.

## 🛠️ Instalación y Ejecución

Para levantar el entorno local, es necesario instalar las dependencias y procesar los límites espaciales:

1. **Instalar dependencias del proyecto:**
   ```bash
   pip install -r requirements.txt
```
## 📁 Estructura del Proyecto
```
Ruta_Calor/
├── app.py                 ← Aplicación principal (interfaz Streamlit y mapa Folium)
├── extraer_pudahuel.py    ← Script para aislar el polígono de Pudahuel
├── requirements.txt       ← Dependencias del entorno (streamlit, folium, shapely)
└── data/
    └── pudahuel.geojson
```