// Text normalisation applied before the network sees the text (offsets are mapped back afterwards).
// It removes invisible characters, turns exotic spaces into spaces, folds full-width forms, maps non-Latin
// digits to 0-9, and replaces Latin look-alike letters inside mixed-script words. This is a fixed,
// hand-written table, like the network's own weights: nothing here is learned.
const DROP = /[​-‏‪-‮⁦-⁩﻿­͏؜]/;
const SPACE = /[   -   　]/;
const DIGIT_BASES = [0x0660, 0x06F0, 0x07C0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0DE6, 0x0E50,
                     0x0ED0, 0x0F20, 0x1040, 0x17E0, 0x1810, 0xFF10];
const HOMO = { "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ɡ": "g",
  "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "І": "I", "Ј": "J",
  "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y",
  "Χ": "X", "ο": "o", "ν": "v" };
const ASCII_WORD = /[A-Za-z0-9@._-]/;
// scanning errors inside numbers: l, I, | read as 1 and O as 0 when a digit sits on both sides ("99000 1l223")
const OCR = /\d[lI|O]\d/;
const OCR_MAP = { l: "1", I: "1", "|": "1", O: "0" };
// a scanning error closing a phone-like digit group: "70214 5539O", "98450 1234G"
const OCR_END = /\d{4,5}[ -]\d{4}[OoIlGSBZ](?![A-Za-z0-9])/;
const OCR_END_MAP = { O: "0", o: "0", I: "1", l: "1", G: "6", S: "5", B: "8", Z: "2" };
const ENTITY = /^&(#\d{1,6}|#x[0-9a-fA-F]{1,5}|amp|lt|gt|quot|apos|nbsp);/;
const NAMED = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
function digitOf(cp) {
  for (const b of DIGIT_BASES) if (cp >= b && cp < b + 10) return String.fromCharCode(48 + cp - b);
  return null;
}
export function normalize(text) {
  if (!/[^\x00-\x7f]/.test(text) && !OCR.test(text) && !OCR_END.test(text) && !/&#?\w+;/.test(text)) return { text, map: null };
  let out = "", map = [];
  const chars = Array.from(text);
  let pos = 0;                                  // UTF-16 offset of the current code point in the original
  for (let k = 0; k < chars.length; k++) {
    const ch = chars[k], cp = ch.codePointAt(0), at = pos;
    pos += ch.length;
    if (DROP.test(ch)) continue;
    // combining accents on Latin letters (NFD "Rene\u0301") are dropped; marks in other scripts (Indic vowel signs) stay
    if (/\p{M}/u.test(ch) && k > 0 && /[A-Za-z]/.test(chars[k - 1])) continue;
    let r = ch;
    if (ch === "&") {
      const e = ENTITY.exec(text.slice(at, at + 10));
      if (e) {
        const n = e[1];
        r = n[0] === "#" ? String.fromCodePoint(n[1] === "x" ? parseInt(n.slice(2), 16) : +n.slice(1)) : NAMED[n];
        for (let j = 0; j < r.length; j++) { out += r[j]; map.push(at); }
        k += e[0].length - 1; pos = at + e[0].length;
        continue;
      }
    }
    if (OCR_END_MAP[ch] && /^\d{4}$/.test(text.slice(at - 4, at)) && /\d{4,5}[ -]$/.test(text.slice(Math.max(0, at - 10), at - 4)) &&
        !/[A-Za-z0-9]/.test(text[at + 1] || "") && !/[A-Za-z]/.test(text[at - 11] || "")) r = OCR_END_MAP[ch];
    else if (OCR_MAP[ch] && k > 0 && k + 1 < chars.length && /\d/.test(chars[k - 1]) && /\d/.test(chars[k + 1])) r = OCR_MAP[ch];
    else if (SPACE.test(ch)) r = " ";
    else if (cp >= 0xFF01 && cp <= 0xFF5E) r = String.fromCharCode(cp - 0xFEE0);
    else if (digitOf(cp)) r = digitOf(cp);
    else if (HOMO[ch] && ((k > 0 && ASCII_WORD.test(chars[k - 1])) || (k + 1 < chars.length && ASCII_WORD.test(chars[k + 1])))) r = HOMO[ch];
    else if (cp >= 0x1D400 && cp <= 0x1D7FF) { const f = ch.normalize("NFKC"); if (f.length === 1) r = f; }   // math bold etc.
    for (let j = 0; j < r.length; j++) { out += r[j]; map.push(at); }
  }
  map.push(text.length);
  return { text: out, map };
}
// Run a model on normalised text and return spans in the ORIGINAL text's UTF-16 offsets.
export function detectNormalized(model, text, opts) {
  const { text: t, map } = normalize(text);
  if (map === null) return model.detect(t, opts);
  return model.detect(t, opts).map(s => {
    const start = map[s.start], last = map[s.end - 1];
    const end = last + (text.codePointAt(last) > 0xFFFF ? 2 : 1);
    return { ...s, start, end, text: text.slice(start, end) };
  });
}
