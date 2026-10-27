Proyecto Ruta del Calor

Geovisor territorial centrado en la comuna de Pudahuel para visualizar el cruce entre riesgo térmico (islas de calor) y vulnerabilidad sociodemográfica.

Este prototipo está construido con Python, Streamlit, Folium y GeoPandas, e integra datos oficiales del Censo 2024 (INE).

📁 Estructura del Proyecto

Ruta-De-Calor/
├── app.py                      # Archivo principal (interfaz Streamlit y visor territorial)
├── requirements.txt            # Dependencias del entorno
├── README.md                   # Documentación del proyecto
├── scripts/                    # Scripts de procesamiento ETL
│   ├── extraer_pudahuel.py     # Script para extraer el polígono oficial de la comuna
│   └── preparar_censo.py       # Script para procesar cartografía y demografía del Censo 2024
└── data/
    ├── raw/                    # Datos crudos (.parquet, .csv). Ignorado por Git.
    └── processed/              # Datos procesados (.geojson) consumidos por app.py


👨‍💻 Guía para Desarrolladores (Setup Local)

Sigue estos pasos para levantar el entorno en tu máquina local de forma segura. Se explica el proceso tanto para Ubuntu/Linux como para Windows.

1. Clonar el repositorio

Abre tu terminal y clona el proyecto:

git clone <URL_DEL_REPOSITORIO>
cd Ruta-De-Calor


2. Crear y activar el entorno virtual

Es estricto el uso de un entorno virtual (venv) para mantener aisladas las dependencias (como las librerías espaciales) y no causar conflictos con el sistema base.

🐧 Para Ubuntu / Linux:

# 1. Instalar el paquete base de entornos virtuales (si el sistema lo requiere)
sudo apt update
sudo apt install python3-venv

# 2. Crear el entorno virtual
python3 -m venv venv

# 3. Activar el entorno (verás un "(venv)" al inicio de tu línea de comandos)
source venv/bin/activate


🪟 Para Windows:

# 1. Crear el entorno virtual
python -m venv venv

# 2. Activar el entorno (verás un "(venv)" al inicio de tu línea de comandos)
venv\Scripts\activate


3. Instalar dependencias

Con el entorno virtual activado, instala todas las librerías necesarias ejecutando:

pip install -r requirements.txt


(Nota para Ubuntu: Si el comando anterior no encuentra pip, utiliza python3 -m pip install -r requirements.txt)

4. Gestión de Datos (¡Importante!)

Para no saturar el repositorio en GitHub, la carpeta de datos crudos (data/raw/) está incluida en el archivo .gitignore.

Modo visualización: Si los archivos livianos .geojson ya existen dentro de la carpeta data/processed/, la aplicación funcionará directamente tras instalar los requerimientos.

Modo procesamiento (ETL): Si necesitas modificar cómo se cruzan los datos espaciales, debes descargar los archivos crudos (Censo, límites), ubicarlos en data/raw/ y ejecutar los scripts correspondientes desde la raíz del proyecto:

# En Windows usar "python" en lugar de "python3"
python3 scripts/extraer_pudahuel.py
python3 scripts/preparar_censo.py


5. Levantar la plataforma

Para ejecutar el servidor local y ver la plataforma en tu navegador web, ejecuta:

streamlit run app.py


El visor se abrirá automáticamente en la dirección local: http://localhost:8501.
