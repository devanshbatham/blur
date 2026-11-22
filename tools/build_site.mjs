// node tools/build_site.mjs [outDir]      (run from the repository root; outDir defaults to site/)
//
// Writes the demo as plain static files: the page and worker from demo/, the engine from web/, the prebuilt model as
// model.bin, the example documents, and a static "info" file standing in for the /info endpoint of demo/server.py.
// The result can be opened with any static file server; nothing in it needs Python.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { loadModel } from "../web/engine.js";

const out = process.argv[2] || "site";
const models = fs.readdirSync("web").filter(f => /^model.*\.bin$/.test(f)).sort();
const modelName = models.includes("model-general.bin") ? "model-general.bin" : models[0];
if (!modelName) { console.error("build_site: no web/model*.bin; build one first (make model)"); process.exit(1); }
const modelPath = path.join("web", modelName);

let previous = {};      // the build date of an unchanged model is kept, so that regenerating changes nothing
try { previous = JSON.parse(fs.readFileSync(path.join(out, "info.json"), "utf8")); } catch {}
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });
const copied = [];
const copy = (from, to = path.basename(from)) => { fs.copyFileSync(from, path.join(out, to)); copied.push(to); };
for (const f of fs.readdirSync("demo").sort()) if (/\.(html|js|json|css|svg|png|ico)$/.test(f)) copy(path.join("demo", f));
for (const f of fs.readdirSync("web").sort()) if (f.endsWith(".js")) copy(path.join("web", f));
fs.mkdirSync(path.join(out, "pipeline"), { recursive: true });
for (const f of fs.readdirSync("web/pipeline").sort()) if (f.endsWith(".js")) copy(path.join("web/pipeline", f), path.join("pipeline", f));
copy(modelPath, "model.bin");

const bytes = fs.readFileSync(modelPath);
const info = (await loadModel(bytes)).info;
const stamp = crypto.createHash("sha256").update(bytes).digest("hex").slice(0, 16);
const built = process.env.SITE_BUILT || (previous.stamp === stamp && previous.built) ||
  fs.statSync(modelPath).mtime.toISOString().replace("T", " ").replace(/\..*/, " UTC");
fs.writeFileSync(path.join(out, "info.json"), JSON.stringify({
  built, neurons: info.neurons, weights: info.connections, labels: info.labels, bytes: bytes.length,
  stamp, profile: modelName.replace(/^model-?|\.bin$/g, "") || "general",
  building: false, error: null, static: true,
}) + "\n");
console.log(`site: ${copied.length + 1} files in ${out}/ (model ${modelName}, ${bytes.length} bytes, ${info.neurons} neurons)`);
