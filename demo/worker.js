// Web Worker: holds its own copy of the model and masks batches of documents off the main thread.
import { loadModel } from "./engine.js";
import { detectNormalized } from "./normalize.js";
import { detect as detectFull } from "./postprocess.js";
let model = null;
const WARM = `Hi team, please update the record for Priya Raman (born 14 March 1989), 221 Harbour View Road, Flat 4B, Bristol BS1 5TR.
Reach her on +44 7700 900123 or priya.raman@example.org. IBAN GB29 NWBK 6016 1331 9268 19, card 4111 1111 1111 1111.
Passport K8829104. key: sk_live_4eC39HqLyjWDarjtT1zdp7dcQ9aX2b
username: priya_r89
password: Tr0ub4dor&3x!
Last login from 203.0.113.42 on 2026-03-14 09:12. Dear Mr. Okafor, Jürgen Müller wrote: see https://example.org/u/priya?id=88.`;
const HIDE = new Set(["CARD_SHAPE", "HEALTH"]);   // health is not a label of this product
const SOFT = new Set(["DATE", "TIME", "CITY", "STATE", "COUNTRY", "BUILDING", "STREET", "SECADDRESS", "URL", "TITLE", "SEX", "ORG"]);
function detect(text, strict) {
  const out = []; let end = 0;
  const all = detectFull(model, text).filter(s => !HIDE.has(s.label));
  const masked = all.filter(s => strict ? s.label !== "ADDRESS" : !SOFT.has(s.label));
  const soft = strict ? [] : all.filter(s => SOFT.has(s.label));
  for (const s of masked.sort((a, b) => a.start - b.start || b.end - a.end)) {
    if (s.start < end) continue;
    out.push([s.start, s.end, s.label, false]); end = s.end;
  }
  for (const s of soft) if (!out.some(o => o[0] < s.end && s.start < o[1])) out.push([s.start, s.end, s.label, true]);
  out.sort((a, b) => a[0] - b[0]);
  return out;
}
onmessage = async e => {
  const m = e.data;
  if (m.type === "load") {
    model = await loadModel(m.buf);
    // warm the JIT so the first real keystroke runs at full speed (cold runs are ~2-3x slower)
    try { for (let i = 0; i < 4; i++) detectFull(model, WARM); } catch (e) { /* warm-up is best effort */ }
    postMessage({type: "ready"});
  }
  else if (m.type === "spans") {
    // live editor: the full finding list for one piece of text, offsets relative to that piece
    try { postMessage({type: "spans", id: m.id, run: m.run, spans: detectFull(model, m.text).map(s => ({...s}))}); }
    catch (err) { postMessage({type: "spans", id: m.id, run: m.run, error: String(err && err.message || err)}); }
  }
  else if (m.type === "run") {
    const t0 = performance.now();
    const results = m.texts.map(t => detect(t, m.strict));
    postMessage({type: "done", id: m.id, results, ms: performance.now() - t0});
  }
};
