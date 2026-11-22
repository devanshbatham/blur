// Contrastive precision pairs: node tests_edge/precision/run.mjs <model.bin> [--fails]   (STANDALONE=1: the model alone)
// A 'mask' value must be fully masked; no character of a 'keep' value may be masked.
import fs from "fs";
import { loadModel } from "../../web/engine.js";
import { maskText } from "../../web/postprocess.js";
import { maskStandalone } from "../../web/standalone.js";
const [modelPath, ...flags] = process.argv.slice(2);
const b = fs.readFileSync(modelPath);
const m = await loadModel(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
const { cases } = JSON.parse(fs.readFileSync(new URL(process.env.CASES ? "./" + process.env.CASES : "./pairs.json", import.meta.url)));
let mOk = 0, mN = 0, kOk = 0, kN = 0, perfect = 0; const fails = [];
for (const c of cases) {
  const spans = process.env.STANDALONE ? maskStandalone(m, c.text).spans : maskText(m, c.text).spans;
  const on = new Array(c.text.length).fill(false);
  for (const s of spans) for (let i = s.start; i < s.end; i++) on[i] = true;
  let ok = true;
  for (const v of c.mask) { const a = c.text.indexOf(v); mN++; const good = [...v].every((ch, i) => on[a + i] || /\s/.test(ch)); if (good) mOk++; else { ok = false; fails.push(`MISS  ${v}   in: ${c.text.slice(0, 70)}`); } }
  for (const v of c.keep) { const a = c.text.indexOf(v); kN++; const good = [...v].every((_, i) => !on[a + i]); if (good) kOk++; else { ok = false; fails.push(`OVER  ${v}   in: ${c.text.slice(0, 70)}`); } }
  if (ok) perfect++;
}
console.log(`PRECISION PAIRS: ${perfect}/${cases.length} cases right | masked ${mOk}/${mN} | kept ${kOk}/${kN}`);
if (flags.includes("--fails")) for (const f of fails) console.log("  " + f);
