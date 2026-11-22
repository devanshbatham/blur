// node tests_edge/fpfn/run.mjs <model.bin> [--show N]
// False positives: everything masked in negatives.json (text with no personal data) is wrong. Reported per 1,000 words.
// False negatives: a value in positives.json counts as found when at least 90% of its characters are masked.
import { loadModel } from "../../web/engine.js";
import { maskText as maskPipeline, label10 } from "../../web/postprocess.js";
import { maskStandalone } from "../../web/standalone.js";
// STANDALONE=1: the model alone (web/standalone.js), no pipeline
// (PII_DATES=0 leaves dates out, as the pipeline does under that policy)
const maskText = (m, t) => process.env.STANDALONE ? { spans: maskStandalone(m, t).spans.filter(s => process.env.PII_DATES !== "0" || s.label !== "private_date").map(s => ({ ...s, tag10: "[" + s.label + "]" })) } : maskPipeline(m, t);
import fs from "fs";
const b = fs.readFileSync(process.argv[2]);
const m = await loadModel(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
const show = process.argv.includes("--show") ? +process.argv[process.argv.indexOf("--show") + 1] : 0;
const rd = f => JSON.parse(fs.readFileSync(new URL("./" + f, import.meta.url)));
const neg = rd("negatives.json"), pos = rd("positives.json");
let words = 0, fp = 0, dirty = 0; const byLab = {}, byDom = {}, ex = {};
for (const d of neg) {
  words += d.text.split(/\s+/).length;
  const sp = maskText(m, d.text).spans;
  if (sp.length) dirty++;
  for (const s of sp) {
    fp++; const lab = label10(s.labelOut), v = d.text.slice(s.start, s.end);
    byLab[lab] = (byLab[lab] || 0) + 1; byDom[d.domain] = (byDom[d.domain] || 0) + 1;
    (ex[lab] = ex[lab] || []).push(`${JSON.stringify(v.slice(0, 40))} ← ${JSON.stringify(d.text.slice(Math.max(0, s.start - 30), s.start))}`);
  }
}
console.log(`FALSE POSITIVES: ${fp} spans in ${neg.length} clean documents (${words} words) = ${(1000 * fp / words).toFixed(2)} per 1,000 words; ${dirty} documents (${(100 * dirty / neg.length).toFixed(1)}%) touched`);
console.log("  by label: " + Object.entries(byLab).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(" · "));
console.log("  by domain: " + Object.entries(byDom).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => `${k} ${v}`).join(" · "));
let ok = 0; const byType = {}, byCtx = {}, miss = {};
for (const p of pos) {
  const cov = new Uint8Array(p.text.length);
  for (const s of maskText(m, p.text).spans) for (let i = s.start; i < s.end; i++) cov[i] = 1;
  let need = 0, got = 0;
  for (let i = p.start; i < p.start + p.value.length; i++) if (!/\s/.test(p.text[i])) { need++; got += cov[i]; }
  const hit = got >= 0.9 * need;
  const t = byType[p.type] = byType[p.type] || [0, 0]; t[1]++; const c = byCtx[p.context] = byCtx[p.context] || [0, 0]; c[1]++;
  if (hit) { ok++; t[0]++; c[0]++; } else (miss[p.type] = miss[p.type] || []).push(JSON.stringify(p.text.slice(Math.max(0, p.start - 35), p.start) + "[[" + p.value + "]]" + p.text.slice(p.start + p.value.length, p.start + p.value.length + 15)));
}
console.log(`\nFALSE NEGATIVES: ${pos.length - ok} of ${pos.length} values missed; recall ${(100 * ok / pos.length).toFixed(1)}%`);
console.log("  by type: " + Object.entries(byType).sort((a, b) => a[1][0] / a[1][1] - b[1][0] / b[1][1]).map(([k, [a, n]]) => `${k} ${(100 * a / n).toFixed(0)}%`).join(" · "));
console.log("  by context: " + Object.entries(byCtx).sort((a, b) => a[1][0] / a[1][1] - b[1][0] / b[1][1]).map(([k, [a, n]]) => `${k} ${(100 * a / n).toFixed(0)}%`).join(" · "));
if (show) {
  for (const [lab, xs] of Object.entries(ex)) { console.log(`\nFP ${lab}:`); for (const x of xs.slice(0, show)) console.log("   " + x); }
  for (const [t, xs] of Object.entries(miss)) { console.log(`\nFN ${t}:`); for (const x of xs.slice(0, show)) console.log("   " + x.slice(0, 150)); }
}
