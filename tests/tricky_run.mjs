// node tests_edge/tricky_run.mjs <model.bin> <dev|heldout> [--fails N]
// Scores the independently written tricky paragraphs: a mask item passes when >=90% of its non-space characters are
// masked; a keep item passes when none of its characters are masked (Standard policy, as in the demo).
import { loadModel } from "../web/engine.js";
import { detect as detectNormalized } from "../web/postprocess.js";
import { maskStandalone } from "../web/standalone.js";
import fs from "fs";
const [, , modelPath, which = "dev"] = process.argv;
const nf = process.argv.includes("--fails") ? +process.argv[process.argv.indexOf("--fails") + 1] : 0;
const buf = fs.readFileSync(modelPath);
const m = await loadModel(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const paras = JSON.parse(fs.readFileSync(new URL(`./tricky/${which}.json`, import.meta.url)));
const SOFT = new Set(["DATE", "TIME", "CITY", "STATE", "COUNTRY", "BUILDING", "STREET", "SECADDRESS", "URL", "TITLE", "SEX", "ORG", "CARD_SHAPE"]);
const at = (t, s, occ) => { let i = -1; for (let k = 0; k <= occ; k++) { i = t.indexOf(s, i + 1); if (i < 0) return -1; } return i; };
let mOk = 0, mN = 0, kOk = 0, kN = 0, paraOk = 0; const byType = {}, fails = [];
for (const p of paras) {
  // STANDALONE=1: the model on its own (network + minimal decoder, every date masked), no pipeline rules
  const t = p.text, spans = process.env.STANDALONE ? maskStandalone(m, t).spans
    : detectNormalized(m, t).filter(s => !SOFT.has(s.label) && !(process.env.PRODUCT && s.label === "HEALTH"));
  const cov = new Array(t.length).fill(null);
  for (const s of spans) for (let i = s.start; i < s.end; i++) cov[i] = s.label;
  let good = true; const pf = [];
  for (const [s, occ, type] of p.mask) {
    const i = at(t, s, occ); if (i < 0) continue;
    let need = 0, got = 0;
    for (let k = i; k < i + s.length; k++) if (!/\s/.test(t[k])) { need++; if (cov[k]) got++; }
    const ok = got >= 0.9 * need; mN++; if (ok) mOk++;
    const bt = byType[type] = byType[type] || [0, 0]; bt[1]++; if (ok) bt[0]++;
    if (!ok) { good = false; pf.push(`MISS[${type}] ${JSON.stringify(s)}${got ? ` (${got}/${need})` : ""}`); }
  }
  for (const [s, occ] of p.keep) {
    const i = at(t, s, occ); if (i < 0) continue;
    const hit = cov.slice(i, i + s.length).filter(Boolean); kN++;
    if (!hit.length) kOk++; else { good = false; pf.push(`OVER ${JSON.stringify(s)} [${[...new Set(hit)].join("/")}]`); }
  }
  if (good) paraOk++; else fails.push({ id: p.id, domain: p.domain, pf, got: spans.map(s => `${s.label}:${t.slice(s.start, s.end)}`).join(" | ") });
}
console.log(`TRICKY ${which}: ${paras.length} paragraphs, ${paraOk} perfect | mask recall ${(100 * mOk / mN).toFixed(1)}% (${mOk}/${mN}) | keep (no false positive) ${(100 * kOk / kN).toFixed(1)}% (${kOk}/${kN})`);
console.log("by type: " + Object.entries(byType).sort((a, b) => b[1][1] - a[1][1]).map(([k, [a, b]]) => `${k} ${a}/${b}`).join(" · "));
for (const f of fails.slice(0, nf)) { console.log(`\n## ${f.id} (${f.domain})`); for (const x of f.pf) console.log("   " + x.slice(0, 160)); }
