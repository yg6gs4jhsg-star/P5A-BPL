// Éditeur : barre d'outils et brouillon gardé dans le navigateur. Seul JavaScript du site.

// --- Constantes ---
const TOOLS = {titre: ["## ", "", true], gras: ["**", "**", false], liste: ["- ", "", true]};  // avant, après, début de ligne

const form = document.querySelector("form[data-brouillon]");
const areas = [...form.querySelectorAll("textarea")];

function changed(area) {
  area.dispatchEvent(new Event("input", {bubbles: true}));  // relance l'aperçu et la copie locale
}

function insert(area, before, after, atLineStart) {
  const {selectionStart, selectionEnd, value} = area;
  const start = atLineStart ? value.lastIndexOf("\n", selectionStart - 1) + 1 : selectionStart;
  area.value = value.slice(0, start) + before + value.slice(start, selectionEnd) + after + value.slice(selectionEnd);
  area.focus();
  area.selectionStart = area.selectionEnd = selectionEnd + before.length;
  changed(area);
}

document.querySelectorAll(".outils").forEach(bar => bar.addEventListener("click", event => {
  const tool = event.target.dataset.outil;
  const area = form.elements[bar.dataset.for];
  const image = bar.querySelector("select").selectedOptions[0];
  if (tool === "image" && image) insert(area, `![${image.text}](/fichiers/${image.value})`, "", false);
  else if (TOOLS[tool]) insert(area, ...TOOLS[tool]);
}));

// Copie locale : sans stockage disponible (navigation privée, réglage, copie illisible), on ne fait rien.
const key = "brouillon-" + form.dataset.brouillon;
let store = null, copy = {};
try {
  store = window.localStorage;
  copy = JSON.parse(store.getItem(key) || "{}");
} catch (error) { store = null; }
if (store) {
  const differs = areas.some(area => area.name in copy && copy[area.name] !== area.value);
  if (differs && confirm("Une copie non enregistrée de ce brouillon existe dans ce navigateur. La récupérer ?")) {
    areas.forEach(area => { if (area.name in copy) { area.value = copy[area.name]; changed(area); } });
  } else {
    store.removeItem(key);  // identique au serveur (donc enregistrée) ou refusée
  }
  form.addEventListener("input", () => {
    try { store.setItem(key, JSON.stringify(Object.fromEntries(areas.map(area => [area.name, area.value])))); }
    catch (error) {}  // stockage plein : la copie locale n'est qu'un filet de secours
  });
}
