# MVP Ruta del Calor - Sprint 1

Geovisor base centrado en la comuna de Cerro Navia para visualizar el cruce entre riesgo térmico y vulnerabilidad sociodemográfica.

## 🛠️ Estructura y Reglas de Desarrollo

El mapa base y la interfaz gráfica ya están configurados (`mapa.js`, `panel.js`, `estilos.css`). **Por favor, no editen estos archivos base para evitar conflictos al hacer merge.**

Cada uno debe trabajar su requerimiento en un archivo JavaScript independiente (por ejemplo, `temperatura.js` o `censo.js`) y luego enlazar ese script en el `index.html` (justo antes de cerrar la etiqueta `</body>`).

### ¿Cómo agregar tu capa al menú?
Para inyectar tu capa en el panel lateral flotante, solo debes llamar a la función `agregarCapa()` (la cual ya está disponible globalmente a través de `panel.js`).

**Ejemplo de uso en tu archivo JS:**
```javascript
// 1. Construyes tu capa de datos con Leaflet
const capaTemperatura = L.geoJSON(misDatos);

// 2. La envías al panel de control pasándole un nombre y la variable
agregarCapa("Temperatura 16:00", capaTemperatura);