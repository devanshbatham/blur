// Policy-aligned masking evaluation on REDACT's locked sample1000 release.
// This is a binary character/complete-entity audit, NOT REDACT's 51-label leaderboard metric.
// Dataset and terms: https://github.com/guneeshvats/REDACT-PII-Benchmark
// Run: node eval/redact.mjs DATA.json MODEL.bin OUTPUT.json [--pipeline]
// Prints no examples or errors from the locked evaluation corpus.
import fs from "node:fs";
import crypto from "node:crypto";
import { loadModel } from "../web/engine.js";
import { maskStandalone } from "../web/standalone.js";
import { maskText } from "../web/postprocess.js";

const [dataPath, modelPath, outputPath, mode] = process.argv.slice(2);
if (!outputPath) throw new Error("usage: redact.mjs DATA.json MODEL.bin OUTPUT.json [--pipeline]");
const supported = new Set([
  "Address_Personal", "Address_Work", "Building_Badge_Card_Number", "Credit_Card_Numbers", "Customer_Reference_Number",
  "Date_of_Birth", "Driving_License_Number", "Employee_ID_Number", "First_Given_Name", "Full_Name", "Last_Family_Name",
  "National_Identification_Number", "Passport_Number", "Password", "Personal_Email_Address", "Preferred_Name",
  "Social_Media_Identifiers", "Static_IP_Address", "Tax_Reference_Number", "Telephone_Numbers_Personal",
  "Telephone_Numbers_Work", "Work_Email_Address",
]);
const bytes = fs.readFileSync(dataPath), modelBytes = fs.readFileSync(modelPath);
const rows = JSON.parse(bytes), model = await loadModel(modelBytes);
const run = mode === "--pipeline" ? maskText : maskStandalone;
const fresh = () => ({ documents: 0, tp: 0, fp: 0, fn: 0, entities: 0, complete: 0 });
const total = fresh(), languages = {};
let invalidDocuments = 0, invalidEntities = 0;
for (const row of rows) {
  const text = row.text, chars = [...text], offsets = [0];
  for (const char of chars) offsets.push(offsets.at(-1) + char.length);
  // Reject invalid annotations before inference, identically for every model.
  const invalid = row.entities.filter(e => !Number.isInteger(e.start) || !Number.isInteger(e.end)
    || e.start < 0 || e.end > chars.length || e.end <= e.start
    || text.slice(offsets[e.start], offsets[e.end]) !== e.entity_string);
  if (invalid.length) { invalidDocuments++; invalidEntities += invalid.length; continue; }
  const gold = new Uint8Array(text.length), ignore = new Uint8Array(text.length), pred = new Uint8Array(text.length);
  const entities = [];
  for (const entity of row.entities) {
    const start = offsets[entity.start], end = offsets[entity.end];
    if (supported.has(entity.entity_type) && entity.disclosed === true) {
      gold.fill(1, start, end); entities.push([start, end]);
    } else ignore.fill(1, start, end);
  }
  for (const span of run(model, text).spans) pred.fill(1, span.start, span.end);
  const counts = fresh(); counts.documents = 1; counts.entities = entities.length;
  for (const [start, end] of entities) {
    let covered = true;
    for (let i = start; i < end; i++) if (!/\s/.test(text[i]) && !pred[i]) { covered = false; break; }
    counts.complete += +covered;
  }
  // Count Unicode code points, not UTF-16 code units. Supported gold wins on overlaps.
  for (const i of offsets.slice(0, -1)) {
    if (gold[i]) counts[pred[i] ? "tp" : "fn"]++;
    else if (pred[i] && !ignore[i]) counts.fp++;
  }
  const lang = row.axes?.language || "unknown", bucket = languages[lang] ??= fresh();
  for (const key of Object.keys(total)) { total[key] += counts[key]; bucket[key] += counts[key]; }
}
function metrics(counts) {
  const precision = counts.tp / (counts.tp + counts.fp || 1), recall = counts.tp / (counts.tp + counts.fn || 1);
  return { ...counts, precision, recall, f1: 2 * precision * recall / (precision + recall || 1),
    completeEntityRecall: counts.complete / (counts.entities || 1) };
}
const hash = b => crypto.createHash("sha256").update(b).digest("hex");
fs.writeFileSync(outputPath, JSON.stringify({
  protocol: "REDACT shared-policy disclosed-only binary masking; unsupported and non-disclosed annotations ignored; all other predicted characters counted",
  mode: mode === "--pipeline" ? "pipeline" : "model", datasetSha256: hash(bytes), modelSha256: hash(modelBytes),
  inputDocuments: rows.length, invalidDocuments, invalidEntities, supportedTypes: [...supported].sort(),
  total: metrics(total), languages: Object.fromEntries(Object.entries(languages).map(([key, value]) => [key, metrics(value)])),
}, null, 2) + "\n");
console.log(`REDACT: wrote aggregate metrics for ${total.documents} documents; ${invalidDocuments} invalid documents excluded`);
