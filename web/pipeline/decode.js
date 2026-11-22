// Decoding loop: base64, URL-encoded, hex and HTML-entity tokens are decoded and scanned; a hit masks the token.
import { detect } from "./detect.js";


// --- 1. decoding loop: base64 / URL-encoded / hex / HTML-entity tokens are decoded and scanned; a hit masks the token.
export function tryDecode(tok) {
  const out = [];
  if (/%[0-9A-Fa-f]{2}/.test(tok)) { try { out.push(decodeURIComponent(tok.replace(/\+/g, " "))); } catch (e) {} }
  if (/&#?\w+;/.test(tok)) out.push(tok.replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d)).replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16))).replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"'));
  const b = tok.replace(/-/g, "+").replace(/_/g, "/");
  if (/^[A-Za-z0-9+/]{12,}={0,2}$/.test(b) && b.length % 4 !== 1) {
    try {
      const s = atob(b + "===".slice((b.length + 3) % 4));
      if (/^[\x20-\x7e\t\r\n]+$/.test(s)) out.push(s);
    } catch (e) {}
  }
  const hx = tok.replace(/^0x/i, "");
  if (/^(?:[0-9a-f]{2}){5,}$/i.test(hx) && (hx !== tok || hx.length >= 16)) {
    const s = hx.match(/../g).map(h => String.fromCharCode(parseInt(h, 16))).join("");
    if (/^[\x20-\x7e]+$/.test(s)) out.push(s);
  }
  return out.filter(s => s !== tok);
}

export function decodeSpans(model, text, depth = 2) {
  const found = [];
  const re = /[A-Za-z0-9+/=%&;_.\-]{12,}/g;
  let mt;
  while ((mt = re.exec(text))) {
    let tok = mt[0].replace(/^[.\-_;&]+|[.;&]+$/g, "");
    let start = mt.index + mt[0].indexOf(tok);
    const hashAt = tok.indexOf("#");                        // nor is a URL fragment
    if (hashAt > 0) tok = tok.slice(0, hashAt);
    const amp = tok.search(/&[A-Za-z_][\w.\-]{0,30}=/);   // the next URL parameter is not part of this payload
    if (amp > 0) { re.lastIndex = mt.index + mt[0].indexOf(tok) + amp + 1; tok = tok.slice(0, amp); }
    const eq = tok.search(/=[^=]/);                        // "key=value": only the value is a payload
    if (eq > 0 && eq < tok.length - 4) { start += eq + 1; tok = tok.slice(eq + 1); }
    for (const dec of tryDecode(tok)) {
      const inner = detect(model, dec, depth - 1).filter(s => !["DATE", "TIME", "URL", "CITY", "STATE", "COUNTRY"].includes(s.label));
      if (/^[\w.@+-]{2,64}:[^\s"{}]{3,}$/.test(dec) && !/^https?:/.test(dec)) { found.push({ start, end: start + tok.length, label: "SECRET", text: tok, decoded: dec, value: dec, fromDecode: true }); break; }
      if (inner.length) { found.push({ start, end: start + tok.length, label: inner[0].label, text: tok, decoded: dec, value: inner[0].text, fromDecode: true }); break; }
    }
  }
  return found;
}
