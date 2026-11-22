// Entry points: long texts in pieces, and text in, masked text out.
import { KEEP_LABELS, OPTIONS } from "./common.js";
import { detect } from "./detect.js";
import { numberedMask } from "./placeholders.js";

// A long text is cut at paragraph breaks (then line breaks) into pieces of about `size` characters and each piece is
// analysed by itself: the context rules look at most a few lines around a value, and their cost grows faster than the
// text, so this keeps long documents fast. Offsets are those of the whole text.
export function pieces(text, size = 12000) {
  if (text.length <= size * 1.5) return [[0, text.length]];
  const out = [];
  let a = 0;
  while (a < text.length) {
    let b = Math.min(text.length, a + size);
    if (b < text.length) {
      let cut = text.lastIndexOf("\n\n", b);
      if (cut <= a + size / 2) cut = text.lastIndexOf("\n", b);
      if (cut <= a + size / 2) cut = text.lastIndexOf(" ", b);
      if (cut > a) b = cut + 1;
    }
    out.push([a, b]); a = b;
  }
  return out;
}

export function detectLong(model, text) {
  const parts = pieces(text);
  if (parts.length === 1) return detect(model, text);
  const found = [];
  for (const [a, b] of parts) for (const s of detect(model, text.slice(a, b))) { s.start += a; s.end += a; found.push(s); }
  return found;
}

export function maskText(model, text, opts = {}) {
  const spans = detectLong(model, text).filter(s => !KEEP_LABELS.has(s.label) && (OPTIONS.health || s.label !== "HEALTH"));
  return numberedMask(text, spans, opts);
}
