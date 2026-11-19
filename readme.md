# Proyecto Ruta del Calor

Geovisor territorial para visualizar el cruce entre riesgo térmico (islas de calor urbano) y vulnerabilidad sociodemográfica en cuatro comunas de Santiago: **Pudahuel, Cerro Navia, Cerrillos y Renca**.

Este prototipo está construido con **Python, Streamlit, Folium y GeoPandas**, e integra datos oficiales del Censo 2024 (INE), temperatura satelital Landsat 8, puntos de refugio de OpenStreetMap y estaciones meteorológicas de RedMeteo.

## 🗺️ Qué puede hacer el visor

Al abrir el visor no hay comunas ni capas de datos activas: cada persona elige.

- **Comunas:** selector múltiple. Se pueden activar las cuatro a la vez.
- **Límite comunal:** viene encendido por defecto.
- **Islas de Calor (LST):** manzanas coloreadas por temperatura de superficie (≥ 36 °C crítico, 33–36 °C alto, < 33 °C moderado), con filtro de temperatura mínima.
- **Demografía / Población > 60 años:** degradado azul según la cantidad de personas de 60 años o más por manzana (Censo 2024).
- **Puntos de refugio:** hospitales, Cesfam, comisarías, bomberos, colegios, parques y más (OpenStreetMap), con filtro por tipo.
- **Estaciones meteorológicas (RedMeteo):** temperatura del **aire** medida en vivo por estaciones aficionadas, con filtro de antigüedad del dato.
- Si falta un archivo de una comuna, esa capa se desactiva y se avisa en el panel, sin romper la app.

### Cosas importantes sobre los datos

- La **LST** es temperatura de la **superficie** (no del aire) y corresponde a la hora de paso del satélite (media mañana), no a las 16:00. Es un promedio de verano 2024 (enero a marzo).
- Las **estaciones RedMeteo** miden la temperatura del **aire** en el momento actual. Son datos **no oficiales** y no son comparables directamente con la LST.
- Los refugios vienen de OpenStreetMap, que es colaborativo y puede estar incompleto.

## 📁 Estructura del Proyecto

```text
Ruta-De-Calor/
├── app.py                          # Interfaz Streamlit y visor territorial
├── requirements.txt                # Dependencias del entorno
├── README.md                       # Documentación del proyecto
├── scripts/
│   ├── procesar_comuna.py          # Hace todo por comuna: censo, temperatura y refugios
│   ├── extraer_comunas.py          # Límites de Cerro Navia, Cerrillos y Renca (BCN)
│   ├── extraer_pudahuel.py         # Límite de Pudahuel (BCN)
│   ├── estaciones_redmeteo.py      # Estaciones RedMeteo en vivo (lo usa app.py)
│   ├── preparar_censo.py           # (original, solo Pudahuel) manzanas del Censo
│   ├── descargar_temperatura.py    # (original, solo Pudahuel) temperatura con Earth Engine
│   ├── cruzar_temperatura.py       # (original, solo Pudahuel) cruce temperatura-manzanas
│   └── refugios.py                 # (original, solo Pudahuel) refugios de OpenStreetMap
└── data/
    ├── raw/                        # Datos crudos. Ignorado por Git (no está en GitHub).
    └── processed/                  # Datos procesados que lee app.py
        ├── <comuna>.geojson                  # Límite comunal
        ├── <comuna>_censo_manzanas.geojson   # Manzanas: Censo 2024 + temperatura
        └── <comuna>_refugios.geojson         # Puntos de refugio
```

Los nombres de comuna en los archivos (`<comuna>`) son: `pudahuel`, `cerro_navia`, `cerrillos` y `renca`.

> `procesar_comuna.py` reemplaza a los cuatro scripts originales de Pudahuel (`preparar_censo.py`, `descargar_temperatura.py`, `cruzar_temperatura.py` y `refugios.py`). Estos se dejan como referencia.

## 👨‍💻 Guía para Desarrolladores (Setup Local)

Sigue estos pasos para levantar el entorno en tu máquina. Se explica el proceso para Ubuntu/Linux y para Windows.

### 1. Clonar el repositorio
```bash
git clone https://github.com/JenDaz10/Ruta-De-Calor.git
cd Ruta-De-Calor
```

### 2. Crear y activar el entorno virtual
Usa siempre un entorno virtual (`venv`) para mantener aisladas las dependencias (como las librerías espaciales) y no causar conflictos con el sistema.

**🐧 Ubuntu / Linux:**
```bash
# 1. Instalar el paquete de entornos virtuales (si el sistema lo pide)
sudo apt update
sudo apt install python3-venv

# 2. Crear el entorno virtual
python3 -m venv venv

# 3. Activarlo (verás un "(venv)" al inicio de la línea de comandos)
source venv/bin/activate
```

**🪟 Windows:**
```bash
# 1. Crear el entorno virtual
python -m venv venv

# 2. Activarlo (verás un "(venv)" al inicio de la línea de comandos)
venv\Scripts\activate
```

### 3. Instalar dependencias
Con el entorno virtual activado:
```bash
pip install -r requirements.txt
```
*(Nota para Ubuntu: si no encuentra pip, usa `python3 -m pip install -r requirements.txt`)*

> En Windows, `tzdata` (incluida en `requirements.txt`) es necesaria para mostrar la hora de Chile en las estaciones meteorológicas.

### 4. Levantar el visor
```bash
python -m streamlit run app.py
```
El visor se abre automáticamente en `http://localhost:8501`.

### 5. Gestión de datos (¡Importante!)
Para no saturar el repositorio, la carpeta `data/raw/` está en el `.gitignore` y **no** está en GitHub.

* **Modo visualización:** si los archivos `.geojson` ya existen en `data/processed/`, el visor funciona directamente tras instalar las dependencias. Las estaciones RedMeteo no necesitan ningún archivo: se consultan por internet cada vez que se activa la capa.
* **Modo procesamiento (ETL):** si necesitas generar o rehacer los datos de una comuna, necesitas los datos crudos en `data/raw/` (parquet del Censo 2024 de la Región Metropolitana y `comunas_final.zip`), las librerías de procesamiento (ver comentarios en `requirements.txt`) y una cuenta de Google Earth Engine (proyecto `ruta-de-calor`).

  1. Genera el límite de las comunas (una sola vez):
     ```bash
     python scripts/extraer_pudahuel.py
     python scripts/extraer_comunas.py
     ```
  2. Procesa una o más comunas (censo + temperatura + refugios):
     ```bash
     python scripts/procesar_comuna.py Renca
     python scripts/procesar_comuna.py "Cerro Navia" Cerrillos
     python scripts/procesar_comuna.py --nuevas           # Cerro Navia, Cerrillos y Renca
     python scripts/procesar_comuna.py --nuevas --forzar  # vuelve a bajar la temperatura
     ```
  *(En Windows usa `python`; en Ubuntu, si `python` no existe, usa `python3`.)*

## 🤝 Trabajo en equipo con Git

Antes de empezar a trabajar:
```bash
git pull origin main
```
Para subir tus cambios:
```bash
git add <archivos>
git commit -m "Descripción corta del cambio"
git pull --no-rebase origin main
git push origin main
```
No subas `data/raw/` ni carpetas `__pycache__/`.

## 📚 Fuentes de datos

- **Límites comunales:** Biblioteca del Congreso Nacional (BCN).
- **Población:** Censo 2024, Instituto Nacional de Estadísticas (INE).
- **Temperatura de superficie (LST):** Landsat 8 (banda ST_B10), vía Google Earth Engine.
- **Refugios:** OpenStreetMap (API Overpass).
- **Estaciones meteorológicas:** Red Meteorológica Aficionada de Chile (RedMeteo), https://www.redmeteo.cl/. Datos no oficiales.
