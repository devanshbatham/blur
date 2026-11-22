// node tests_edge/spec3/run.mjs <model.bin> [--fails N] [--only ID,ID]
// Exact-output check against the owner's spec: same characters masked, everything else byte-identical, and the same
// entity linking (tags are compared by identity, not by name). Label-name agreement is reported separately.
import { loadModel } from "../../web/engine.js";
import { maskText, OPTIONS } from "../../web/postprocess.js";
OPTIONS.health = true;        // the answer keys of this spec include health labels
import fs from "fs";
const [, , modelPath] = process.argv;
const nf = process.argv.includes("--fails") ? +process.argv[process.argv.indexOf("--fails") + 1] : 0;
const only = process.argv.includes("--only") ? new Set(process.argv[process.argv.indexOf("--only") + 1].split(",")) : null;
const buf = fs.readFileSync(modelPath);
const m = await loadModel(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const cases = JSON.parse(fs.readFileSync(new URL("./cases.json", import.meta.url)));
const TAG = /\[([A-Z][A-Z0-9_]*?)_(\d+)\]/g;
const shape = s => { const ids = new Map(); return s.replace(TAG, t => { if (!ids.has(t)) ids.set(t, ids.size + 1); return `«${ids.get(t)}»`; }); };
let pass = 0; const fails = []; const groups = {}; let labN = 0, labOk = 0; const labBad = [];
for (const k of cases) {
  if (only && !only.has(k.id)) continue;
  const out = maskText(m, k.input, { numbered: true }).text;
  const ok = shape(out) === shape(k.expected);
  if (ok) {           // same structure: compare the label names placeholder by placeholder
    const le = [...k.expected.matchAll(TAG)].map(x => x[1]), lg = [...out.matchAll(TAG)].map(x => x[1]);
    le.forEach((l, i) => { labN++; if (l === lg[i]) labOk++; else labBad.push(`${k.id}: expected ${l}, got ${lg[i]}`); });
  }
  const g = k.id.replace(/\d+[a-z]?$/, "").replace(/^G$/, "G") ; const grp = k.id.startsWith("G") ? "G" + String(Math.floor((+k.id.slice(1) - 1) / 8)) : k.id.replace(/[a-z]$/, "");
  (groups[grp] = groups[grp] || [0, 0])[1]++; if (ok) { pass++; groups[grp][0]++; } else fails.push({ k, out });
}
const total = only ? only.size : cases.length;
console.log(`SPEC3: ${pass}/${total} exact (${(100 * pass / total).toFixed(1)}%)  ` + Object.entries(groups).map(([g, [a, b]]) => `${g} ${a}/${b}`).join(" · "));
console.log(`LABELS: ${labOk}/${labN} placeholders carry the expected label (${(100 * labOk / Math.max(1, labN)).toFixed(1)}%)`);
if (process.argv.includes("--labels")) for (const x of labBad) console.log("  " + x);
for (const { k, out } of fails.slice(0, nf)) console.log(`\n${k.id}\n  in : ${JSON.stringify(k.input)}\n  exp: ${JSON.stringify(k.expected)}\n  got: ${JSON.stringify(out)}`);
