// Edge-case guide suite: node tests_edge/guide_run.mjs <model.bin> [--section NAME] [--fails N]
// Scores each guide case under the demo's Standard policy, label-agnostic, at character level.
import { loadModel } from "../web/engine.js";
import { detect as detectNormalized } from "../web/postprocess.js";
import fs from "fs";

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const buf = fs.readFileSync(args[0]);
const m = await loadModel(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const { cases, skipped } = JSON.parse(fs.readFileSync(new URL("./guide_cases.json", import.meta.url), "utf8"));
const SOFT = new Set(["DATE", "TIME", "CITY", "STATE", "COUNTRY", "BUILDING", "STREET", "SECADDRESS", "URL", "TITLE", "SEX", "ORG"]);
const keep = s => s.label !== "CARD_SHAPE" && !SOFT.has(s.label);
const section = opt("--section", null), nFails = +opt("--fails", 3);

const occurrences = (t, s) => { const out = []; let i = t.indexOf(s); while (i >= 0) { out.push(i); i = t.indexOf(s, i + 1); } return out; };
const stat = () => ({ cases: 0, passed: 0, items: 0, itemsPassed: 0 });
const bySec = {}, bySev = {}, all = stat(), maskSt = { items: 0, ok: 0 }, keepSt = { items: 0, ok: 0 }, crit = { items: 0, ok: 0 };
const fails = {};
for (const c of cases) {
  if (section && c.section !== section) continue;
  const spans = detectNormalized(m, c.t).filter(keep);
  const cov = new Uint8Array(c.t.length);
  for (const s of spans) for (let i = s.start; i < s.end; i++) cov[i] = 1;
  const bad = [];
  for (const it of c.mask) {
    // pass if any occurrence is >=90% covered (non-space characters)
    const ok = occurrences(c.t, it).some(a => {
      let n = 0, hit = 0;
      for (let i = a; i < a + it.length; i++) if (!/\s/.test(c.t[i])) { n++; hit += cov[i]; }
      return n === 0 || hit / n >= 0.9;
    });
    maskSt.items++; if (ok) maskSt.ok++; else bad.push(`MISS ${JSON.stringify(it)}`);
    if (c.severity === "FN-critical") { crit.items++; if (ok) crit.ok++; }
  }
  for (const it of c.keep) {
    const ok = occurrences(c.t, it).every(a => { for (let i = a; i < a + it.length; i++) if (cov[i]) return false; return true; });
    keepSt.items++; if (ok) keepSt.ok++; else bad.push(`OVERMASK ${JSON.stringify(it)}`);
  }
  const items = c.mask.length + c.keep.length, itemsOk = items - bad.length;
  for (const st of [all, bySec[c.section] ||= stat(), bySev[c.severity] ||= stat()]) {
    st.cases++; st.items += items; st.itemsPassed += itemsOk; if (!bad.length) st.passed++;
  }
  if (bad.length) (fails[c.section] ||= []).push({ case: c.case, severity: c.severity, t: c.t, bad,
    got: spans.map(s => `${s.label}:${c.t.slice(s.start, s.end)}`) });
}
const pct = (a, b) => b ? (100 * a / b).toFixed(1) + "%" : "-";
console.log(`GUIDE SUITE (Standard policy): ${all.passed}/${all.cases} cases pass (${pct(all.passed, all.cases)}); items ${pct(all.itemsPassed, all.items)}`);
console.log(`mask-item recall ${pct(maskSt.ok, maskSt.items)} (${maskSt.ok}/${maskSt.items}) | FN-critical item recall ${pct(crit.ok, crit.items)} (${crit.ok}/${crit.items}) | decoy keep rate ${pct(keepSt.ok, keepSt.items)} (${keepSt.ok}/${keepSt.items})`);
console.log(`skipped guide rows: ${skipped.length}\n`);
console.log("section".padEnd(22) + "cases  pass   items");
for (const [k, v] of Object.entries(bySec)) console.log(k.padEnd(22) + String(v.cases).padStart(5) + pct(v.passed, v.cases).padStart(7) + pct(v.itemsPassed, v.items).padStart(8));
console.log("\nseverity".padEnd(23) + "cases  pass   items");
for (const [k, v] of Object.entries(bySev)) console.log(k.padEnd(22) + String(v.cases).padStart(5) + pct(v.passed, v.cases).padStart(7) + pct(v.itemsPassed, v.items).padStart(8));
if (nFails > 0) for (const [sec, fs_] of Object.entries(fails)) {
  console.log(`\n## ${sec}: ${fs_.length} failing`);
  for (const f of fs_.slice(0, nFails)) {
    console.log(`  [${f.severity}] ${f.case}: ${JSON.stringify(f.t).slice(0, 140)}`);
    console.log(`     ${f.bad.join(" | ").slice(0, 220)}`);
    console.log(`     got: ${f.got.join(" | ").slice(0, 220) || "(nothing)"}`);
  }
}
const summary = { when: new Date().toISOString(), cases: all.cases, passed: all.passed, mask: maskSt, keep: keepSt, fnCritical: crit, bySection: bySec, bySeverity: bySev, fails };
fs.writeFileSync(new URL("./guide_last.json", import.meta.url), JSON.stringify(summary, null, 1));
