// HTTP request/response regression suite: node tests_edge/http/run.mjs <model.bin> [--fails]
// Every occurrence of each 'mask' value must be fully masked with the expected output label; no character of any
// occurrence of a 'keep' value may be masked.
import { loadModel } from "../../web/engine.js";
import * as P from "../../web/postprocess.js";
import fs from "fs";
const [modelPath, ...flags] = process.argv.slice(2);
const b = fs.readFileSync(modelPath);
const m = await loadModel(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
const exp = JSON.parse(fs.readFileSync(new URL("./expect.json", import.meta.url)));
const text = fs.readFileSync(new URL("./" + exp.file, import.meta.url), "utf8");
import { maskStandalone } from "../../web/standalone.js";
const spans = process.env.STANDALONE ? maskStandalone(m, text).spans.map(s => ({ ...s, tag10: "[" + s.label + "]" })) : P.maskText(m, text).spans;
const lab = new Array(text.length).fill(null);
for (const s of spans) for (let i = s.start; i < s.end; i++) lab[i] = (s.tag10 || "[personal_id]").slice(1, -1);
const occ = v => { const out = []; let i = -1; while ((i = text.indexOf(v, i + 1)) >= 0) out.push(i); return out; };
let mOk = 0, mN = 0, lOk = 0, kOk = 0, kN = 0; const fails = [];
for (const [v, want] of exp.mask) {
  const at = occ(v);
  if (!at.length) { fails.push(`NOT IN FILE  ${v}`); continue; }
  for (const a of at) {
    mN++;
    const ls = lab.slice(a, a + v.length), masked = ls.every((x, i) => x || /\s/.test(v[i]));
    if (masked) { mOk++; if (ls.filter(Boolean).every(x => x === want)) lOk++; else fails.push(`LABEL  ${v.slice(0, 50)}  want ${want} got ${[...new Set(ls.filter(Boolean))].join("/")}`); }
    else fails.push(`MISS   ${v.slice(0, 60)}  (${want})  ${ls.some(Boolean) ? "partly masked" : ""}`);
  }
}
for (const v of exp.keep) for (const a of occ(v)) {
  kN++;
  const hit = lab.slice(a, a + v.length).some(Boolean);
  if (!hit) kOk++; else fails.push(`OVER   ${v.slice(0, 60)}  got ${[...new Set(lab.slice(a, a + v.length).filter(Boolean))].join("/")}`);
}
console.log(`HTTP SUITE: masked ${mOk}/${mN} (${(100 * mOk / mN).toFixed(1)}%), right label ${lOk}/${mOk} | kept ${kOk}/${kN} (${(100 * kOk / kN).toFixed(1)}%)`);
if (flags.includes("--fails")) for (const f of [...new Set(fails)]) console.log("  " + f);
