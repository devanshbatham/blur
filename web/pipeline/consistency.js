// One value, one decision: dates of birth repeated as dates, identifiers repeated as plain numbers.
import { KEEP_LABELS } from "./common.js";
import { extColumn } from "./names.js";


// one value, one decision: a date equal to a known date of birth is that date of birth; an identifier repeated as a
// standalone number elsewhere is masked there too (but a phone extension is business contact data)
export const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

export const NUMW = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
  fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50,
  sixty: 60, seventy: 70, eighty: 80, ninety: 90 };

export const ORDW = { first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7, eighth: 8, ninth: 9, tenth: 10, eleventh: 11,
  twelfth: 12, thirteenth: 13, fourteenth: 14, fifteenth: 15, sixteenth: 16, seventeenth: 17, eighteenth: 18, nineteenth: 19, twentieth: 20, thirtieth: 30 };

export function yearOf(w) {
  if (/^\d{4}$/.test(w)) return +w;
  const t = w.toLowerCase().replace(/-/g, " ").split(/\s+/).filter(x => x !== "and");
  if (t[0] === "two" && t[1] === "thousand") return 2000 + t.slice(2).reduce((a, x) => a + (NUMW[x] || 0), 0);
  if (NUMW[t[0]] >= 19 || t[0] === "nineteen" || t[0] === "twenty") { const c = NUMW[t[0]]; let r = 0; for (const x of t.slice(1)) if (x !== "hundred") r += NUMW[x] || 0; return c * 100 + r; }
  return null;
}

export function dateKeys(v) {
  const t = v.trim().toLowerCase(), out = new Set();
  let m;
  if ((m = /^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})/.exec(t))) out.add(`${+m[1]}-${+m[2]}-${+m[3]}`);
  else if ((m = /^(\d{1,2})[-\/.](\d{1,2})[-\/.](\d{4})$/.exec(t))) { out.add(`${+m[3]}-${+m[2]}-${+m[1]}`); out.add(`${+m[3]}-${+m[1]}-${+m[2]}`); }
  else if ((m = /^(\d{1,2})(?:st|nd|rd|th)?(?: of)? ([a-z]{3})[a-z]*,? (.+)$/.exec(t)) || (m = /^([a-z]+)(?: of)? ([a-z]{3})[a-z]*,? (.+)$/.exec(t))) {
    const d = /^\d+$/.test(m[1]) ? +m[1] : (ORDW[m[1]] || (m[1].startsWith("twenty") ? 20 + (ORDW[m[1].replace(/^twenty[- ]?/, "")] || 0) : null));
    const y = yearOf(m[3]); if (d && MONTHS[m[2]] && y) out.add(`${y}-${MONTHS[m[2]]}-${d}`);
  }
  return out;
}

export function consistency(text, spans) {
  const add = [];
  const covered = new Uint8Array(text.length + 1);
  for (const s of spans) if (!KEEP_LABELS.has(s.label)) for (let i = s.start; i < s.end; i++) covered[i] = 1;
  const free = (a, b) => { for (let i = a; i < b; i++) if (covered[i]) return false; return true; };
  // dates of birth
  const dob = new Set();
  for (const s of spans) if (s.label === "BOD") for (const k of dateKeys(text.slice(s.start, s.end))) dob.add(k);
  if (dob.size) {
    const D = /\b(\d{4}[-\/.]\d{1,2}[-\/.]\d{1,2}|\d{1,2}[-\/.]\d{1,2}[-\/.]\d{4})\b/g;
    let m;
    while ((m = D.exec(text))) {
      const a = m.index, b = a + m[0].length;
      if ([...dateKeys(m[0])].some(k => dob.has(k))) {
        const over = spans.find(s => s.start <= a && b <= s.end && !KEEP_LABELS.has(s.label));
        if (!over) add.push({ start: a, end: b, label: "BOD" });
      }
    }
    for (const s of spans) if (s.label === "DATE" && [...dateKeys(text.slice(s.start, s.end))].some(k => dob.has(k))) s.label = "BOD";
  }
  const ocr = v => v.toUpperCase().replace(/[IL|]/g, "1").replace(/O/g, "0").replace(/S/g, "5").replace(/B/g, "8").replace(/Z/g, "2").replace(/G/g, "6");
  const idv = spans.filter(s => /^(ID|IDCARD|PASSPORT)$/.test(s.label)).map(s => text.slice(s.start, s.end)).filter(v => /^[A-Z0-9]{8,16}$/.test(v) && /\d/.test(v) && /[A-Z]/.test(v));
  if (idv.length) {
    const keys = new Map(idv.map(v => [ocr(v), v]));
    for (const m of text.matchAll(/(?<![A-Za-z0-9])[A-Z0-9]{8,16}(?![A-Za-z0-9])/g)) {
      const src = keys.get(ocr(m[0]));
      if (src && src !== m[0] && free(m.index, m.index + m[0].length)) add.push({ start: m.index, end: m.index + m[0].length, label: "ID", value: src });
    }
  }
  // identifiers repeated as standalone numbers
  const ids = new Set(spans.filter(s => /^(ID|IDCARD)$/.test(s.label) && /^\d{4,}$/.test(text.slice(s.start, s.end)) && !/^(19|20)\d\d$/.test(text.slice(s.start, s.end))).map(s => text.slice(s.start, s.end)));
  for (const v of ids) {
    const re = new RegExp("(?<![\\w.-])" + v + "(?![\\w.-])", "g");
    let m;
    while ((m = re.exec(text))) {
      const a = m.index, b = a + v.length;
      if (!free(a, b)) continue;
      const line = text.slice(text.lastIndexOf("\n", a) + 1, a);
      if (/\bext(n|ension)?\.?\s*:?\s*$/i.test(line) || /\|/.test(line) && extColumn(text, a)) continue;
      add.push({ start: a, end: b, label: "ID", value: v });
    }
  }
  return add.length ? spans.concat(add).sort((x, y) => x.start - y.start) : spans;
}
