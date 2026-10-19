// ===== MAPA BASE: Cerro Navia =====

const CENTRO_CERRO_NAVIA = [-33.4219, -70.7436];
const ZOOM_INICIAL = 13;

const mapa = L.map("mapa", {
  center: CENTRO_CERRO_NAVIA,
  zoom: ZOOM_INICIAL,
  minZoom: 11,
  maxZoom: 19
});

const imagenSatelital = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { attribution: "Imágenes &copy; Esri, Maxar, Earthstar Geographics" }
);
const etiquetas = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
);
const satelite = L.layerGroup([imagenSatelital, etiquetas]);

const calles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; Colaboradores de OpenStreetMap"
});

satelite.addTo(mapa);

L.control.layers({ "Satélite": satelite, "Calles": calles }, null, { position: "topright" }).addTo(mapa);

const BotonInicio = L.Control.extend({
  options: { position: "topleft" },
  onAdd: function () {
    const contenedor = L.DomUtil.create("div", "leaflet-bar boton-inicio");
    const boton = L.DomUtil.create("a", "", contenedor);
    boton.innerHTML = "&#8962;"; // símbolo de casa
    boton.title = "Volver a Cerro Navia";
    L.DomEvent.on(boton, "click", function (e) {
      L.DomEvent.stop(e);
      mapa.setView(CENTRO_CERRO_NAVIA, ZOOM_INICIAL);
    });
    return contenedor;
  }
});
mapa.addControl(new BotonInicio());

L.control.scale({ imperial: false, position: "bottomleft" }).addTo(mapa);

const Coordenadas = L.Control.extend({
  options: { position: "bottomleft" },
  onAdd: function () {
    this._div = L.DomUtil.create("div", "coordenadas");
    this._div.textContent = "Mueve el cursor sobre el mapa";
    return this._div;
  }
});
const controlCoordenadas = new Coordenadas();
mapa.addControl(controlCoordenadas);

mapa.on("mousemove", function (e) {
  controlCoordenadas._div.textContent =
    e.latlng.lat.toFixed(4) + ", " + e.latlng.lng.toFixed(4);
});
