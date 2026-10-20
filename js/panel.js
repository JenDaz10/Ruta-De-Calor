const capas = {}; // aquí quedan guardadas todas las capas, por nombre

function agregarCapa(nombre, capa, visibleAlInicio = false) {
  capas[nombre] = capa;

  const lista = document.getElementById("lista-capas");

  const mensajeVacio = lista.querySelector(".vacio");
  if (mensajeVacio) mensajeVacio.remove();

  const fila = document.createElement("label");
  fila.className = "item-capa";

  const casilla = document.createElement("input");
  casilla.type = "checkbox";
  casilla.checked = visibleAlInicio;

  const texto = document.createElement("span");
  texto.textContent = nombre;

  fila.append(casilla, texto);
  lista.appendChild(fila);

  // Activa o desactiva la capa en el mapa
  casilla.addEventListener("change", function () {
    if (casilla.checked) {
      capa.addTo(mapa);
    } else {
      mapa.removeLayer(capa);
    }
  });

  if (visibleAlInicio) capa.addTo(mapa);
}
