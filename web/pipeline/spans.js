// Span clean-up: label priority, whole-token extension, overlaps, and resolving competing spans.
import { DELIM, KEEP_LABELS, NAME_LABELS } from "./common.js";
import { pieces } from "./mask.js";
import { specificKind } from "./validators.js";


// --- 2. span clean-up: trim delimiters, never split a word for word-like labels, drop overlaps by priority
export const PRIORITY = ["SECRET", "PASS", "COOKIE", "CARD", "SOCIALNUMBER", "IDCARD", "PASSPORT", "DRIVERLICENSE", "HEALTH", "EMAIL", "TEL",
  "IP", "MAC", "BOD", "GIVENNAME", "LASTNAME", "USERNAME", "ID", "ADDRESS", "STREET", "SECADDRESS", "BUILDING", "POSTCODE", "CITY",
  "STATE", "COUNTRY", "GEOCOORD", "DATE", "TIME", "URL"];

export const rank = l => { const i = PRIORITY.indexOf(l); return i < 0 ? PRIORITY.length : i; };

export const TOKEN_LABELS = new Set(["ID", "PASSPORT", "IDCARD", "DRIVERLICENSE", "SOCIALNUMBER", "TEL", "CARD", "SECRET", "USERNAME",
  "COOKIE", "IP", "MAC", "EMAIL"]);

export const NOT_TOKEN = new Set(["URL", "COOKIE", "ADDRESS"]);

export function clean(text, spans) {
  const out = [];
  for (let s of spans) {
    let a = s.start, b = s.end;
    if (!NOT_TOKEN.has(s.label) && !s.fromDecode) {
      // a value never carries its key ("q=13.08,80.27" -> "13.08,80.27") nor the next URL parameter ("...&issuer=Acme")
      const kv = /^[A-Za-z_][\w.\-]{0,30}=(?!=)/.exec(text.slice(a, b));
      if (kv && kv[0].length < b - a) a += kv[0].length;
      const amp = text.slice(a, b).search(/&[A-Za-z_][\w.\-]{0,30}=/);
      if (amp > 0) {
        // the rest is another parameter: it becomes its own span (its key kept visible)
        const rest = text.slice(a + amp + 1, b), eq = rest.indexOf("=");
        const val = rest.slice(eq + 1).replace(/[.,;)]+$/, "");
        // only when the other value looks like a credential itself (long, or mixed letters and digits)
        if (eq >= 0 && (val.length >= 16 || (val.length >= 8 && /\d/.test(val) && /[A-Za-z]/.test(val))))
          spans.push({ ...s, start: a + amp + 2 + eq, end: a + amp + 2 + eq + val.length, text: val });
        b = a + amp;
      }
    }
    if (!s.fromDecode && !(s.label === "IP" && text.startsWith("::", s.start))) {
      const bal = (o, c) => (text.slice(a, b).split(o).length) === (text.slice(a, b).split(c).length);
      while (a < b && DELIM.test(text[a]) && !(text[a] === "&" && text[a + 1] === "#") && !(text[a] === "(" && !bal("(", ")") === false && text.slice(a, b).includes(")"))) a++;
      while (b > a && DELIM.test(text[b - 1]) && !(text[b - 1] === "=" && /[A-Za-z0-9+\/]=*$/.test(text.slice(a, b - 1) + "=")) &&
             !(text[b - 1] === ")" && text.slice(a, b).includes("("))) b--;
    }
    if (TOKEN_LABELS.has(s.label) && !s.fromDecode) {                  // never start or end inside a letter/digit run
      while (a > 0 && /[A-Za-z0-9]/.test(text[a - 1]) && /[A-Za-z0-9]/.test(text[a])) a--;
      while (b < text.length && /[A-Za-z0-9]/.test(text[b]) && /[A-Za-z0-9]/.test(text[b - 1])) b++;
    }
    if (NAME_LABELS.has(s.label)) {
      const lead = /^[^\p{L}\p{M}\p{N}]+/u.exec(text.slice(a, b)), trail = /[^\p{L}\p{M}\p{N}.'’]+$/u.exec(text.slice(a, b));
      if (lead) a += lead[0].length;
      if (trail && b - trail[0].length > a) b -= trail[0].length;
    }
    if (NAME_LABELS.has(s.label) || s.label === "USERNAME") {          // whole words only
      // (scripts written without spaces between words - Han, kana, Hangul runs, Thai - have no token boundaries to grow to)
      const NOSPACE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}々ー]/u;
      while (a > 0 && (/[\p{L}\p{M}]/u.test(text[a - 1]) || (/['’-]/.test(text[a - 1]) && a > 1 && /\p{L}/u.test(text[a - 2]))) && /[\p{L}]/u.test(text[a]) && !NOSPACE.test(text[a - 1]) && !NOSPACE.test(text[a])) a--;
      while (b < text.length && /[\p{L}\p{M}]/u.test(text[b]) && /[\p{L}\p{M}]/u.test(text[b - 1]) && !NOSPACE.test(text[b]) && !NOSPACE.test(text[b - 1])) b++;
    }
    let label = s.label;
    if (label === "TEL" && /[A-Za-z].*[A-Za-z]|^[A-Za-z]/.test(text.slice(a, b).replace(/\b(ext|extn|extension|x|tel|ph)\b\.?/gi, ""))) label = "ID";
    let kind = s.kind;
    if (/^\d{4}[ -]?\d{4}[ -]?\d{4}$/.test(text.slice(a, b)) && /(aadhaa?r|uidai|आधार)[^\n]{0,20}$/i.test(text.slice(Math.max(0, a - 30), a))) kind = "AADHAAR";
    if (b > a) out.push({ ...s, label, kind, start: a, end: b, text: text.slice(a, b) });
  }
  // a decoded payload's label wins (it says what the value really is); then label priority; then the longer span
  out.sort((x, y) => x.start - y.start || (y.fromDecode ? 1 : 0) - (x.fromDecode ? 1 : 0) || rank(x.label) - rank(y.label) ||
                      (y.end - y.start) - (x.end - x.start));
  // a decoded span replaces whatever the network found inside the same characters
  const dec = out.filter(s => s.fromDecode);
  let res = out.filter(s => s.fromDecode || !dec.some(d => d.start < s.end && s.start < d.end));
  // merge neighbouring number pieces when the joined text passes a format validator (IBAN, card)
  const merged = [];
  for (const s of res) {
    const p = merged[merged.length - 1];
    if (p && /^[ -]$/.test(text.slice(p.end, s.start)) && /[0-9A-Z]/.test(s.text)) {
      const joined = text.slice(p.start, s.end);
      const kind = specificKind(joined);
      if (kind === "IBAN" || kind === "CARD") { p.end = s.end; p.text = joined; p.label = kind === "IBAN" ? "ID" : "CARD"; continue; }
    }
    merged.push({ ...s });
  }
  for (const s of merged) s.kind = s.kind || specificKind(s.text);
  return merged;
}

// added spans replace whatever overlaps them
export function overlay(base, add) {
  // a "weak" addition yields to what is already there (a cue-based guess never replaces a validated finding)
  add = add.filter(a => !(a.weak && base.some(b => !KEEP_LABELS.has(b.label) && b.start <= a.start && b.end >= a.end)));
  if (!add.length) return base;
  const keep = base.filter(b => KEEP_LABELS.has(b.label) || !add.some(a => !KEEP_LABELS.has(a.label) && a.start < b.end && b.start < a.end));
  return keep.concat(add.map(a => ({ ...a }))).sort((x, y) => x.start - y.start);
}

// overlapping masked spans: the earlier, then the longer one wins; labels that are only kept (URL, city, date ...) never
// compete with masked ones
export function resolve(spans) {
  const kept = spans.filter(s => KEEP_LABELS.has(s.label) || s.label === "ADDRESS");   // an address overlays its parts
  const out = [];
  const sorted = spans.filter(s => s.end > s.start && !KEEP_LABELS.has(s.label) && s.label !== "ADDRESS").sort((x, y) => x.start - y.start || (y.end - y.start) - (x.end - x.start));
  let end = -1;
  for (const s of sorted) if (s.start >= end) { out.push(s); end = s.end; }
  return out.concat(kept).sort((x, y) => x.start - y.start);
}
