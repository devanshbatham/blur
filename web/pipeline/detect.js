// Detection: the network's spans, its exported not-a-name/secret/id regions, and the order of every stage.
import { detectNormalized } from "../normalize.js";
import { keyValueSpans, spokenSpans, structuredSpans } from "../structure.js";
import { KEEP_LABELS, NAME_LABELS, OPTIONS, dbg } from "./common.js";
import { consistency } from "./consistency.js";
import { DEPT_WORD, ORG_END, ORG_NEXT, ORG_PREV, PUBLIC_LINE, REF_CUE, ROLE_BOX, TITLE_HEAD, cuedNames } from "./cued_names.js";
import { decodeSpans } from "./decode.js";
import { editDistance, evidenceGate, monthMatch, nm0 } from "./evidence.js";
import { finishing } from "./finishing.js";
import { keyAware, keyOf } from "./keys.js";
import { role } from "./labels.js";
import { completeNames, fixNames, namesInTokens, propagate } from "./names.js";
import { clean, overlay, resolve } from "./spans.js";
import { VP } from "./validators.js";

// the network's own "not a name / secret / id / ip / handle here" regions (auxiliary outputs _NOT_*)
export const NOT_GROUP = { GIVENNAME: "_NOT_NAME", LASTNAME: "_NOT_NAME", PERSON: "_NOT_NAME", _NAME: "_NOT_NAME", SECRET: "_NOT_SECRET", PASS: "_NOT_SECRET",
  ID: "_NOT_ID", _ID: "_NOT_ID", IDCARD: "_NOT_ID", IP: "_NOT_IP", USERNAME: "_NOT_USERNAME" };

export let notAt = {};

export const notCovered = s => {
  const g = NOT_GROUP[s.label], rs = g && notAt[g];
  if (!rs) return false;
  let k = 0; for (const [a, b] of rs) k += Math.max(0, Math.min(b, s.end) - Math.max(a, s.start));
  return 2 * k > s.end - s.start;
};

export function detect(model, text, depth = 2) {
  const saved = notAt;
  const out = detectAll(model, text, depth);
  const res = depth > 0 ? out.filter(s => !notCovered(s)) : out;
  notAt = saved;
  return res;
}

export function detectAll(model, text, depth) {
  const raw = detectNormalized(model, text, { includeAux: true });
  const literals = raw.filter(s => s.label === "_SECRET_LITERAL").map(s => ({ ...s, label: "SECRET", net: true }));
  notAt = {};
  for (const s of raw) if (s.label.startsWith("_NOT_")) (notAt[s.label] = notAt[s.label] || []).push([s.start, s.end]);
  let spans = raw.filter(s => !s.label.startsWith("_") && !s.label.startsWith("kind:")).map(s => ({ ...s, net: true }));
  if (depth > 0) spans = spans.concat(decodeSpans(model, text, depth));
  spans = clean(text, spans);
  if (depth <= 0) return spans;
  const ruled = xs => xs.map(x => ({ ...x, byRule: true }));          // these rules checked their own cue or structure
  spans = overlay(spans, ruled(spokenSpans(text)));                // number words, NATO e-mails, dates in words
  const st = structuredSpans(text, spans);                          // SQL columns, cookies, share links, partial masks
  spans = overlay(spans.filter(x => !x.drop), ruled(st));
  // values under explicit keys: added where the network found nothing, or only part of the value
  { const kv = keyValueSpans(text).filter(k => !spans.some(o => !KEEP_LABELS.has(o.label) && o.start <= k.start && k.end <= o.end));
    spans = overlay(spans, kv); }
  spans = fixNames(text, spans);
  spans = completeNames(text, spans);
  spans = dbg("propagate", text, propagate(text, spans));
  spans = fixNames(text, spans);                                    // again, for propagated names ("Ananya I.")
  spans = dbg("finishing", text, finishing(text, spans));
  spans = dbg("tokens", text, namesInTokens(text, spans));
  spans = dbg("fixNames", text, fixNames(text, spans));
  spans = dbg("consist", text, consistency(text, spans));
  // (a decoded payload is judged by the context of its encoded token in the outer text, not here)
  spans = spans.filter(s => {
    const v = text.slice(s.start, s.end), before = text.slice(Math.max(0, s.start - 28), s.start), nm = NAME_LABELS.has(s.label);
    // a bank branch code is public (four letters, a zero, six characters); a compact timestamp is not a phone or an ID
    if (/^(ID|_ID|ACCOUNT)$/.test(s.label) && /^[A-Z]{4}0[A-Z0-9]{6}$/.test(v)) return false;
    if (/^(TEL|ID|_ID)$/.test(s.label) && /^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])[0-5]\d([0-5]\d)?$/.test(v)) return false;
    // a phone number that is all zeros after its prefix is a blank
    if (s.label === "TEL" && /0{7,}$/.test(v.replace(/\D/g, ""))) return false;
    // a version after a version key is not an address on a network: fw=8.1.0.4, version: 10.2.0.1
    if (s.label === "IP" && /\b(fw|firmware|version|ver|build|release|sw|os|v)["']?\s*[=: ]\s*["']?v?$/i.test(before)) return false;
    // a product code after its cue: SKU A1289, model no. X200
    if (/^(ID|_ID|ADDRESS|USERNAME|BUILDING|POSTCODE)$/.test(s.label) && /\b(sku|model( no\.?| number)?|part( no\.?| number)|item( no\.?| code)|asin|isbn|hsn( code)?)[:#]?\s+$/i.test(before) && !/\s/.test(v)) return false;
    // a number is an identifier as a whole token, not as digits inside a longer code: "1:26-cv-04417-ABC"
    if (/^(ID|_ID)$/.test(s.label) && /^\d{1,6}$/.test(v) && (/[A-Za-z0-9]$/.test(before) || /^[A-Za-z0-9]/.test(text.slice(s.end, s.end + 1)) || /[A-Za-z]-0*$/.test(before) && /^-[A-Za-z]/.test(text.slice(s.end, s.end + 2)))) return false;
    // a name that is the head of a business or street name: "Sharma Kirana Store", "Iyer Street", "Clínica São Lucas"
    if (nm && (ORG_NEXT.test(text.slice(s.end, s.end + 40)) || ORG_END.test(v) || ORG_PREV.test(text.slice(Math.max(0, s.start - 24), s.start))) && !/\b(Mr|Mrs|Ms|Dr|Prof)\.? $/.test(before)) return false;
    // a reference to a thing, not to a person: order, tracking, invoice, flight, project, claim and company numbers, and
    // the last digits of a card or account ("ending 8812")
    if (/^(ID|_ID|CARD|ADDRESS|TEL|IDCARD|ACCOUNT|BUILDING)$/.test(s.label) && !s.cued && REF_CUE.test(before) && !/\b(account|customer|member|client|policyholder|patient|employee)\s+(reference|ref)\.?\s*[:#]?\s*$/i.test(before) && !/\s{2,}|\n/.test(v) && !/\b(ssn|social security|aadhaa?r|pan|passport|national id|nino|licen[cs]e)\b[^.\n]{0,16}$/i.test(before)) return false;
    // a public line of an organisation: switchboard, front desk, helpline, toll-free
    if (s.label === "TEL" && (PUBLIC_LINE.test(text.slice(Math.max(0, s.start - 60), s.start)) || /^[ ,]*\(?(?:their|the|our)? ?(?:main )?(?:switchboard|front desk|reception|helpline|hotline|practice line|office line|main line)/i.test(text.slice(s.end, s.end + 34)))) return false;
    // placeholders for a missing name; a name inside a host name
    if (nm && /^(TBD|TBA|TBC|N\/A|NA|NIL|NONE|XXX+|UNKNOWN|PENDING)$/.test(v)) return false;
    if (nm && /:\/\/[\w.-]*$/.test(before) && /^[\w-]*\.[a-z]/i.test(text.slice(s.end, s.end + 12))) return false;
    return true;
  });
  // "Baby of <mother>" names the mother; the words before her are not part of a name
  for (const s of spans) if (nm0(s)) { const m = /^(Baby|Son|Daughter|Wife|Husband|Child|Ward) of\s+/.exec(text.slice(s.start, s.end)); if (m) s.start += m[0].length; }
  spans = spans.filter(s => !(nm0(s) && /^(Baby|Son|Daughter|Wife|Husband|Child|Ward)$/.test(text.slice(s.start, s.end)) && /^ of /.test(text.slice(s.end, s.end + 4)) || nm0(s) && text.slice(s.start, s.end) === "of" ));
  // a name key decides the whole value: "Father's Name: SRINIVASA REDDY", "Child's name: Ishaan Malhotra   Gender: M".
  // When part of the value is already masked as a name, the rest of the capitalised run after the key belongs to it.
  for (const m of text.matchAll(/(?:^|[\n;|,(]|\s{2})[ \t]{0,8}[\p{L}' ]{0,24}\bname[ \t]{0,8}[:=][ \t]{0,8}((?:\p{Lu}[\p{L}'.-]*)(?: \p{Lu}[\p{L}'.-]*){0,4})(?=\s{2,}|\s*[\n,;|)]|\s*$)/giu)) {
    const a = m.index + m[0].length - m[1].length, b = a + m[1].length;
    if (/\b(user|file|host|domain|company|product|brand|table|column|field|class|function|project|event|bank|branch|school|hospital|org\w*|business|display|device|street|city|place)[ _]*name[ \t]*[:=]/i.test(m[0])) continue;
    const inside = spans.filter(o => o.start >= a && o.end <= b);
    if (!inside.some(nm0) || inside.some(o => !nm0(o) && !KEEP_LABELS.has(o.label))) continue;
    if (inside.length === 1 && inside[0].start === a && inside[0].end === b) continue;
    { const cov = new Uint8Array(b - a); for (const o of inside) cov.fill(1, o.start - a, o.end - a); if ([...text.slice(a, b)].every((ch, i) => cov[i] || !/\p{L}/u.test(ch))) continue; }
    for (const o of inside) o.drop = true;
    spans.push({ start: a, end: b, label: "GIVENNAME", byRule: true });
  }
  spans = spans.filter(o => !o.drop).sort((x, y) => x.start - y.start);
  spans = spans.filter(s => {
    const v = text.slice(s.start, s.end);
    if (NAME_LABELS.has(s.label) || s.label === "_NAME") {
      const ws = v.split(/[ \u00a0]+/);
      if (ws.length >= 2 && TITLE_HEAD.test(ws[ws.length - 1])) return false;                       // "Talent Acquisition Partner"
      if (ws.length === 1 && /^(MD|DO|RN|NP|PA|PhD|DDS|CPA|CFA|OCN|BSN|MBA|JD|Esq|MS|MA|BA|BS|PR|HR|IT|QA|VP|SVP|EVP|CEO|CFO|COO|CTO|CIO|GM)$/.test(v)) return false;
      if (ws.every(w => DEPT_WORD.test(w))) return false;                                                // "Revenue Strategy", "Footwear"
    }
    // a sheet, tab or column name ("Owner_Rollup", "Work_Email") or an ordinary hyphenated word after an article or
    // preposition ("the district-level rollouts", "sensitivity sign-off") is not a person's handle
    if (s.label === "USERNAME" && (/^[A-Z][a-z]+(?:_[A-Z][a-z0-9]*)+_?$/.test(v) || /^[a-z]+-[a-z]+$/.test(v) && /\b(the|a|an|his|her|our|their|its|of|for|in|on|and|sensitivity|final|formal)\s$/i.test(text.slice(Math.max(0, s.start - 14), s.start)))) return false;
    if (/^(ID|_ID|ACCOUNT|IDCARD)$/.test(s.label) && (/^\d{6,}$/.test(v) && /000$/.test(v) || /^(19|20)\d{2}$/.test(v))) return false;
    return true;
  });
  // a name is a whole word, never a piece of a code ("Zx" in "Zx81kLmQ92"); protocol and format names are not identifiers
  spans = spans.filter(s => !(NAME_LABELS.has(s.label) && (/[A-Za-z0-9]/.test(text[s.end] || "") && /\d/.test(text.slice(s.end, s.end + 3)) || /\d/.test(text[s.start - 1] || ""))));
  spans = spans.filter(s => !(/^(ID|USERNAME|_ID)$/.test(s.label) && /^(ipv[46]|oauth2?|sha-?\d+|md5|utf-?\d+|base(32|58|64)|http\/?[123](\.\d)?|tls ?1?\.?\d?|h26[45]|mp[34]|x86(_64)?|x64|i18n|l10n|k8s|s3|ec2|wpa[23]|aes-?\d+|rsa-?\d+|ed25519|web3|[2345]g|es\d+|python[23]|win(10|11|32|64)|cve|iso-?\d+)$/i.test(text.slice(s.start, s.end))));
  // symbols, not names: a Greek letter in a short or mixed-script token ("πr", "ΔH")
  spans = spans.filter(s => !(NAME_LABELS.has(s.label) && /\p{Script=Greek}/u.test(text.slice(s.start, s.end)) && (s.end - s.start <= 3 || /[A-Za-z]/.test(text.slice(s.start, s.end)))));
  if (depth >= 2) spans = dbg("evidence", text, evidenceGate(text, spans));
  // an address that begins with a person's name ("Neha Kulkarni, B-702, ... Pune 411045") starts after the name
  for (const s of spans) if (s.label === "ADDRESS") {
    const lead = spans.filter(o => nm0(o) && o.start >= s.start && o.start < s.start + 60 && o.end < s.end);
    if (!lead.length || Math.min(...lead.map(o => o.start)) !== s.start) continue;
    let e = s.start; for (const o of lead.sort((x, y) => x.start - y.start)) if (o.start <= e + 1) e = Math.max(e, o.end);
    const m = /^[,;:]?\s*/.exec(text.slice(e, s.end));
    if (e + m[0].length < s.end - 4) s.start = e + m[0].length;
  }
  spans = resolve(spans);
  if (depth >= 2) spans = keyAware(text, spans);
  // every date is masked (OPTIONS.dates): a plain date that no other finding covers becomes a masked date
  if (depth >= 2 && OPTIONS.dates)
    for (const s of spans) if (s.label === "DATE" && /\d/.test(text.slice(s.start, s.end)) && !(/(^|_)(version|build|release)$/.test(keyOf(text, s.start) || "")) && !spans.some(o => o !== s && !KEEP_LABELS.has(o.label) && o.start < s.end && s.start < o.end)) s.label = "DATE_PLAIN";
  if (depth >= 2) {
    spans = cuedNames(text, spans);
    // a misspelling of a name already found in this text is the same person: "Priya ... Pryia", "Fernandes ... Fernandez".
    // (5+ letters, same first letter, one edit - two for 8+ letters; a capitalised word, or any word when letters are swapped)
    const known = new Map();
    for (const o of spans) if (NAME_LABELS.has(o.label)) for (const w of text.slice(o.start, o.end).split(/[^\p{L}]+/u)) if (w.length >= 5) known.set(w.toLowerCase(), o.label);
    if (known.size && known.size <= 40) {
      const taken = new Uint8Array(text.length + 1);
      for (const o of spans) if (!KEEP_LABELS.has(o.label) || o.label === "CITY" || o.label === "COUNTRY" || o.label === "STATE") taken.fill(1, o.start, o.end);
      for (const m of text.matchAll(/(?<![\p{L}\p{N}_@.\/-])\p{L}{5,}(?![\p{L}\p{N}_@])/gu)) {
        const w = m[0], lw = w.toLowerCase();
        if (taken[m.index] || known.has(lw)) continue;
        for (const [k, lab] of known) {
          if (k[0] !== lw[0] || Math.abs(k.length - lw.length) > 1 || lw === k + "s" || k === lw + "s") continue;
          const d = editDistance(lw, k), swapped = d === 1 && lw.length === k.length && [...lw].sort().join("") === [...k].sort().join("");
          const cap = /^\p{Lu}/u.test(w) && !/(^|[.!?]\s+|\n)$/.test(text.slice(Math.max(0, m.index - 3), m.index));
          if (swapped || cap && d <= (k.length >= 8 ? 2 : 1) && d > 0 && !/\b(the|a|an|this|that|our|your)\s$/i.test(text.slice(Math.max(0, m.index - 6), m.index))) {
            spans.push({ start: m.index, end: m.index + w.length, label: lab, byRule: true }); break;
          }
        }
      }
      spans.sort((x, y) => x.start - y.start);
    }
    // dates written with a month name that the network left alone, typos included: "5 Jan", "16-Nov-2026", "March 3rd, 2025",
    // "31stt sept, 2023", "2nd Febuary 2024", "Decmber 4, 2023", "12//03//2024"
    const cands = [];
    const MONX = "(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre|januar|februar|märz|maerz|juni|juli|oktober|dezember|janeiro|fevereiro|março|marco|maio|junho|julho|setembro|outubro|novembro|dezembro|gennaio|febbraio|aprile|maggio|giugno|luglio|settembre|ottobre|dicembre|जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर)";
    const MONE = "(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)";
    for (const re of [
      new RegExp("(?<![\\w.\\/-])(?:\\d{1,2}(?:er|º|\\.)?|1er)[ \\u00a0](?:de[ \\u00a0])?" + MONX + "(?:[ \\u00a0](?:de[ \\u00a0])?(?:19|20)\\d{2})?(?![\\p{L}])", "giu"),      // 3 de diciembre, 21 février 2027, 14. Januar
      new RegExp("(?<![\\w.\\/-])\\d{1,2}(?:st|nd|rd|th)?[ ]?[–—-][ ]?\\d{1,2}(?:st|nd|rd|th)?[ ]" + MONE + "\\.?(?:,? (?:19|20)\\d{2})?(?![\\w])", "gi"),   // 14–20 December, 9–12 June 2027
      new RegExp("(?<![\\w.\\/-])" + MONE + "\\.? \\d{1,2}(?:st|nd|rd|th)?[ ]?[–—-][ ]?(?:" + MONE + "\\.? )?\\d{1,2}(?:st|nd|rd|th)?(?:,? (?:19|20)\\d{2})?(?![\\w])", "gi"),  // Dec 3 – Dec 9, 2026
      new RegExp("(?<![\\w.\\/-])\\d{1,2}(?:st|nd|rd|th) (?:day )?of " + MONE + "(?:,? (?:19|20)\\d{2})?(?![\\w])", "gi"),                               // 3rd day of February 2026
      /(?<![\w.\/-])(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?=T\d|[^\w-]|$)/g,                                                    // 2026-09-14T03:22:07Z
      new RegExp("(?<![\\p{L}])(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|twenty-(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|thirtieth|thirty-first) of " + MONE + "(?:,? (?:nineteen|twenty)[ -][a-z]+(?:[ -][a-z]+)?)?(?![\\p{L}])", "gi"),   // the twenty-second of October
    ]) for (const m of text.matchAll(re)) { if (/^may\b/i.test(m[0]) && !/^May/.test(m[0])) continue; cands.push({ a: m.index, b: m.index + m[0].length, raw: true }); }
    // a numeric date with a four-digit year that the network left alone: "geboren am 5.10.1988", "3/7/2024"
    for (const m of text.matchAll(/(?<![\w.\/-])(?:0?[1-9]|[12]\d|3[01])([.\/-])(?:0?[1-9]|1[0-2]|[12]\d|3[01])\1(?:19|20)\d{2}(?![\w\/-]|\.\d)/g)) cands.push({ a: m.index, b: m.index + m[0].length, raw: true });
    const D1 = /(?<![\w.\/-])(\d{1,2})([a-z]{0,3})[ \-\/.,]{1,2}(?:of )?(\p{L}{3,10})\.?(?:[ \-\/,]{1,3}'?(\d{4}|\d{2}))?(?![\w])/giu;
    const D2 = /(?<![\w.\/-])(\p{L}{3,10})\.? (\d{1,2})([a-z]{0,3})(?:,? (\d{4}))?(?![\w])/giu;
    for (const m of text.matchAll(D1)) cands.push({ a: m.index, b: m.index + m[0].length, day: +m[1], suf: m[2], mon: m[3], year: m[4] });
    for (const m of text.matchAll(D2)) cands.push({ a: m.index, b: m.index + m[0].length, day: +m[2], suf: m[3], mon: m[1], year: m[4] });
    for (const m of text.matchAll(/(?<![\w.\/-])\d{1,2}([\/.-])\1?\d{1,2}\1{1,2}\d{2,4}(?![\w\/-])/g)) if (/([\/.-])\1/.test(m[0])) cands.push({ a: m.index, b: m.index + m[0].length, raw: true });
    for (const c of cands) {
      if (!c.raw) {
        const mq = monthMatch(c.mon);
        if (!mq || c.day < 1 || c.day > 31) continue;
        if (c.suf && !/^(st|nd|rd|th)$/i.test(c.suf) && !(c.year && /^[stndrh]+$/i.test(c.suf))) continue;      // "31stt" needs a year beside it
        if (mq === "fuzzy" && !(c.year && c.year.length === 4)) continue;                                         // a misspelt month needs a year
        // "may" is a month only when capitalised and not used as the verb ("1 may be enough", "he may 12 times")
        if (/^may$/i.test(c.mon) && (c.mon !== "May" || /^ (be|not|have|also|need|want|well)\b/.test(text.slice(c.b, c.b + 6)))) continue;
        if (/^(mar|sep|dec|jun|jul|oct|nov|jan|feb|apr|aug)$/.test(c.mon) && !c.year && c.suf === "" && /^ \p{Ll}/u.test(text.slice(c.b, c.b + 2)) && c.a > 0 && /\p{L}{3}/u.test(text.slice(c.b + 1, c.b + 4)) && false) continue;
      }
      const hit = spans.filter(o => o.start < c.b && c.a < o.end);
      if (hit.some(o => !KEEP_LABELS.has(o.label) && o.label !== "DATE_PLAIN" && !(/^(USERNAME|ID|_ID)$/.test(o.label) && o.start >= c.a && o.end <= c.b))) continue;
      for (const o of hit) o.drop = true;
      { const k = keyOf(text, c.a); if (k && /(^|_)(version|build|release|api_version)$/.test(k)) continue; }
      const dh = hit.filter(o => o.label === "DATE" || o.made);          // (a weekday the network attached to a date is not carried over)
      spans.push({ start: Math.min(c.a, ...dh.map(o => o.start)), end: Math.max(c.b, ...dh.map(o => o.end)), label: OPTIONS.dates ? "DATE_PLAIN" : "DATE", made: true });
    }
    spans = spans.filter(o => !o.drop).sort((x, y) => x.start - y.start);
  }
  // A later prose heuristic can truncate a network-validated quoted password
  // at an escaped quote. Restore only final accepted literal spans from the
  // model, after all heuristic stages have finished.
  return overlay(spans, literals);
}
