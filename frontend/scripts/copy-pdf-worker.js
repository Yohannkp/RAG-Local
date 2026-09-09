// Copie le worker pdf.js correspondant exactement a la version de pdfjs-dist
// utilisee EN INTERNE par react-pdf (qui peut differer de la version
// top-level, et dont l'emplacement sur disque depend de la strategie de
// hoisting de npm) : un decalage de version fait planter le rendu PDF avec
// "API version does not match Worker version". On utilise la resolution de
// modules Node elle-meme (celle que react-pdf utilise en interne) plutot que
// de deviner un chemin statique, pour rester correct quel que soit le hoisting.
const fs = require("fs");
const path = require("path");

const reactPdfDir = path.dirname(require.resolve("react-pdf/package.json"));
const pdfjsDir = path.dirname(
  require.resolve("pdfjs-dist/package.json", { paths: [reactPdfDir] })
);
const source = path.join(pdfjsDir, "build", "pdf.worker.min.mjs");

fs.mkdirSync("public", { recursive: true });
fs.copyFileSync(source, path.join("public", "pdf.worker.min.mjs"));
console.log(`pdf.worker.min.mjs copié depuis ${source}`);
