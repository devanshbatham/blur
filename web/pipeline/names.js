// Names: completing a person's name, propagating it through a document, and names inside tokens.
import { rot13, skeleton, unleet } from "../structure.js";
import { KEEP_LABELS, NAME_LABELS } from "./common.js";
import { consistency } from "./consistency.js";
import { FIRM_NEXT, FIRM_PREV, GREETING } from "./evidence.js";
import { PRODUCTS } from "./finishing.js";
import { role } from "./labels.js";
import { pieces } from "./mask.js";

// is the markdown-table cell at position a under an "Ext"-type header?
export function extColumn(text, a) {
  const ls = text.lastIndexOf("\n", a) + 1, line = text.slice(ls, text.indexOf("\n", a) < 0 ? text.length : text.indexOf("\n", a));
  const col = text.slice(ls, a).split("|").length - 1;
  let p = ls - 1;
  while (p > 0) {
    const ps = text.lastIndexOf("\n", p - 1) + 1, l = text.slice(ps, p);
    if (!/^\s*\|/.test(l)) break;
    if (!/^[\s|:-]+$/.test(l)) { const h = l.split("|")[col]; if (h && /^\s*(ext|extn|extension|phone ext\.?)\s*$/i.test(h)) return true; }
    p = ps - 1;
  }
  return false;
}


// name completion: 'Kavitha "Kavi" Raghunathan'; a tagged part pulls in its capitalised neighbour ("Summer Joy", "Chase Lincoln");
// in a list made mostly of people, items of the same shape are people too; "KR (as everyone calls her)" is an alias
export const NOT_NAME_NEIGHBOUR = /^(The|A|An|In|On|At|Of|For|To|From|By|With|And|Or|But|If|When|While|Mr|Mrs|Ms|Dr|Prof|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|June|July|August|September|October|November|December|Street|Road|Lane|Avenue|Hospital|University|College|School|Bank|Ltd|Inc|LLC|LLP|Pvt|Trust|Memorial|Foundation|Group|Team|Finance|Engineering|Sales|Marketing|Legal|Support|Security|Platform|Ops|SRE|HR|IT|CI|CD|API|PIR|IST|UTC|GMT)$/;

export function completeNames(text, spans) {
  const add = [];
  const covered = new Uint8Array(text.length + 1);
  for (const s of spans) if (!KEEP_LABELS.has(s.label)) for (let i = s.start; i < s.end; i++) covered[i] = 1;
  const claim = (a, b, label) => { for (let i = a; i < b; i++) if (covered[i]) return false; add.push({ start: a, end: b, label }); for (let i = a; i < b; i++) covered[i] = 1; return true; };
  const names = () => spans.concat(add).filter(s => NAME_LABELS.has(s.label)).sort((x, y) => x.start - y.start);
  for (const s of names()) {
    const after = text.slice(s.end, s.end + 40);
    let m = /^ ["“'‘][\p{Lu}][\p{L}]+["”'’] (\p{Lu}[\p{L}'’-]+)/u.exec(after);            // first "Nick" Surname
    if (m) { const a = s.end + m[0].length - m[1].length; claim(a, a + m[1].length, "LASTNAME"); continue; }
    m = /^ (\p{Lu}[\p{Ll}'’-]+)\b/u.exec(after);
    if (m && !NOT_NAME_NEIGHBOUR.test(m[1]) && !PRODUCTS.test(m[1]) && !FIRM_NEXT.test(text.slice(s.end + m[0].length, s.end + m[0].length + 24)) &&
        !/^[.:!?]/.test(text.slice(s.end + m[0].length, s.end + m[0].length + 1)) && /^\p{Lu}\p{Ll}/u.test(text.slice(s.start, s.end)))
      claim(s.end + 1, s.end + 1 + m[1].length, "LASTNAME");
    const before = text.slice(Math.max(0, s.start - 30), s.start);
    m = /(?:^|[\s,(])(\p{Lu}[\p{Ll}'’-]+) $/u.exec(before);
    if (m && !NOT_NAME_NEIGHBOUR.test(m[1]) && !PRODUCTS.test(m[1]) && s.label === "LASTNAME" && /^\p{Lu}\p{Ll}/u.test(text.slice(s.start, s.end)))
      claim(s.start - 1 - m[1].length, s.start - 1, "GIVENNAME");
  }
  // lists: "A B, C D and E F" where most items are already people
  const LIST = /((?:\p{Lu}[\p{Ll}'’-]+ \p{Lu}[\p{Ll}'’-]+)(?:(?:, | and | & )(?:\p{Lu}[\p{Ll}'’-]+ \p{Lu}[\p{Ll}'’-]+)){2,})/gu;
  let m;
  while ((m = LIST.exec(text))) {
    const items = [...m[1].matchAll(/\p{Lu}[\p{Ll}'’-]+ \p{Lu}[\p{Ll}'’-]+/gu)].map(x => ({ a: m.index + x.index, b: m.index + x.index + x[0].length }));
    const isP = it => names().some(s => s.start >= it.a && s.end <= it.b);
    if (items.filter(isP).length * 2 > items.length)
      for (const it of items) if (!isP(it)) { const sp = text.indexOf(" ", it.a); claim(it.a, sp, "GIVENNAME"); claim(sp + 1, it.b, "LASTNAME"); }
  }
  // a capitalised word that precedes a known name every time it appears (2+ times) is part of that name: "Sterling Banks"
  for (const s of names()) {
    const m2 = /(?:^|[\s,(\]])(\p{Lu}\p{Ll}{2,}) $/u.exec(text.slice(Math.max(0, s.start - 24), s.start));
    if (!m2 || NOT_NAME_NEIGHBOUR.test(m2[1])) continue;
    const pair = m2[1] + " " + text.slice(s.start, s.end);
    if (text.split(pair).length - 1 >= 2) claim(s.start - 1 - m2[1].length, s.start - 1, "GIVENNAME");
  }
  // 'Rohit "Ro" Deshpande': the word before a quoted nickname that is followed by a name; the nickname is an alias
  const NICK = /(\p{Lu}\p{Ll}+) ["“'‘](\p{Lu}\p{L}{1,12})["”'’] (\p{Lu}[\p{L}'’-]+)/gu;
  while ((m = NICK.exec(text))) {
    const sa = m.index + m[0].length - m[3].length;
    if (!names().some(s => s.start <= sa && sa < s.end) && !names().some(s => s.start === m.index)) continue;
    claim(m.index, m.index + m[1].length, "GIVENNAME"); claim(sa, sa + m[3].length, "LASTNAME");
    const na = m.index + m[1].length + 2; claim(na, na + m[2].length, "GIVENNAME");
    const re = new RegExp("(?<![\\p{L}\\p{N}_])" + m[2] + "(?![\\p{L}\\p{N}_])", "gu");
    for (const o of text.matchAll(re)) claim(o.index, o.index + m[2].length, "GIVENNAME");
  }
  // a person-role label followed by words in a non-Latin script: "Courier: أحمد يوسف", "नाम: प्रिया शर्मा"
  const ROLE = /\b(?:name|courier|driver|contact|customer|patient|agent|recipient|sender|attn|attention|owner|guardian|father|mother|spouse|nominee|doctor|nurse)\s*:\s*((?:[^\x00-\x7f\s,;:|()]+\s?){1,4})/giu;
  while ((m = ROLE.exec(text))) {
    const v = m[1].trimEnd(), a = m.index + m[0].length - m[1].length;
    if (/^[\p{L}\p{M}\s]+$/u.test(v)) claim(a, a + v.length, "GIVENNAME");
  }
  // aliases: "KR (as everyone calls her)", "Kavi (aka K)", "Robert (Bob for short)"
  const AL = /\b(\p{Lu}[\p{L}.]{1,15}) \((?:as (?:everyone|everybody|we|they|people|most people|the team) calls? (?:her|him|them)|a\.?k\.?a\.?[^)]{0,30}|for short)\)/gu;
  while ((m = AL.exec(text))) {
    const prev = names().filter(s => s.end <= m.index).pop();
    if (prev) claim(m.index, m.index + m[1].length, "GIVENNAME");
  }
  return add.length ? spans.concat(add).sort((x, y) => x.start - y.start) : spans;
}

export const HONOR = /^(Yaar|Bhai|Bhaiya|Didi|Beta|Dost|Herr|Frau|Señor|Señora|Senor|Senora|Monsieur|Madame|Signor|Signora|Shri|Smt|Sri|Kumari)\.?(\s+|$)/;

export function fixNames(text, spans) {
  const out = [];
  for (const s of spans) {
    if (/^(GIVENNAME|LASTNAME|PERSON|_NAME)$/.test(s.label)) {
      const hm = HONOR.exec(text.slice(s.start, s.end));
      if (hm) { if (hm[0].length >= s.end - s.start) { if (/^\s+\p{Lu}/u.test(text.slice(s.end, s.end + 3))) continue; } else s.start += hm[0].length; }
    }
    // a place name used as a form of address is a person: "Hi Jordan,", "Dear Paris,", "Thanks, Georgia!"
    if (/^(COUNTRY|CITY|STATE)$/.test(s.label) && /^\p{Lu}\p{Ll}+$/u.test(text.slice(s.start, s.end)) &&
        GREETING.test(text.slice(Math.max(0, s.start - 24), s.start)) && /^\s*([,!:.\n]|$)/.test(text.slice(s.end, s.end + 2))) s.label = "GIVENNAME";
    // ... or doing what a person does: "Paris says the demo is moved", "Paris from sales"
    if (/^(COUNTRY|CITY|STATE)$/.test(s.label) && /^\p{Lu}\p{Ll}+$/u.test(text.slice(s.start, s.end)) && !/\b(in|at|to|from|of|near|the|visit\w*|across)\s$/i.test(text.slice(Math.max(0, s.start - 10), s.start)) &&
        /^ (says|said|asked|told me|told us|wants|replied|thinks|wrote|messaged|texted|pinged|is out|is on leave|from (sales|hr|legal|finance|marketing|support|accounts|ops|engineering|it|design|product)\b)/.test(text.slice(s.end, s.end + 22))) s.label = "GIVENNAME";
    if (s.label === "GIVENNAME") {
      const nx = spans.find(o => o.start === s.end + 1 && /^(CITY|COUNTRY|STATE)$/.test(o.label) && text[s.end] === " " && /^\p{Lu}\p{Ll}+$/u.test(text.slice(o.start, o.end)));
      if (nx) nx.label = "LASTNAME";
    }
    if (NAME_LABELS.has(s.label)) {
      const after = text.slice(s.end, s.end + 24), before = text.slice(Math.max(0, s.start - 24), s.start);
      if (FIRM_NEXT.test(after) || (FIRM_PREV.test(before) && !/^\s*(and|said|wrote|,)/.test(after))) continue;
      const ini = /^,? \p{Lu}\.(?!\w)/u.exec(after);                 // "KUMAR, A." / "Ananya I."
      if (ini && !spans.some(o => o !== s && o.start >= s.end && o.start < s.end + ini[0].length)) { s.end += ini[0].length; s.text = text.slice(s.start, s.end); }
    }
    out.push(s);
  }
  return out;
}


// consistency: a name or handle detected once is the same entity wherever else it is written
export const ORG_TAIL = /^\s*(&|Co\.?\b|Ltd|LLP|LLC|Inc|Pvt|Street|St\.|Road|Rd\.?|Avenue|Ave|Lane|Hospital|University|College|School|Bank|Group|Chartered|Associates|Partners|Foundation|Trust|Law|law|Memorial|Ward)\b/;

// after a person's name a lower-case word is a verb or a function word ("April that", "Ravi said"); after a common
// noun it is usually another noun ("Grace period") or a pronoun ("Hope you're")
export const PERSON_NEXT = /^\s+(that|and|or|but|to|about|with|for|from|of|in|on|at|by|is|was|has|had|will|would|can|could|should|did|does|said|says|asked|told|who|whose|which|again|too|also|here|there|yesterday|today|tomorrow|\p{Ll}+ed|\p{Ll}{2,}[^s\W]s)\b/u;

// at the start of a sentence a capitalised word is often an ordinary word ("Grace periods apply", "Hope this helps"):
// there only an explicit verb or a function word counts
export const PERSON_NEXT_STRONG = /^\s+(and|or|is|was|has|had|will|would|can|could|should|did|does|said|says|asked|told|wrote|replied|called|emailed|who|whose|from|at|to)\b/u;

export const sentenceStart = (text, a) => a === 0 || /(^|[.!?]\s+|\n\s*)$/.test(text.slice(Math.max(0, a - 4), a));

// a word inside a list of three or more capitalised words ("Rose, Hope, May, Will and Bill") is being talked about
export function inNameList(text, a, b) {
  const left = text.slice(Math.max(0, a - 60), a), right = text.slice(b, b + 60);
  const L = left.match(/((?:\p{Lu}\p{Ll}+(?:,\s+|\s+(?:and|or)\s+))+)$/u), R = right.match(/^((?:(?:,\s+|\s+(?:and|or)\s+)\p{Lu}\p{Ll}+)+)/u);
  const n = 1 + (L ? (L[1].match(/\p{Lu}\p{Ll}+/gu) || []).length : 0) + (R ? (R[1].match(/\p{Lu}\p{Ll}+/gu) || []).length : 0);
  return n >= 3;
}

export function propagate(text, spans) {
  const covered = new Uint8Array(text.length + 1);
  for (const s of spans) for (let i = s.start; i < s.end; i++) covered[i] = 1;
  const add = [];
  const seen = new Set();
  for (const s of spans) {
    const v = text.slice(s.start, s.end);
    const partOfFull = spans.some(o => o !== s && NAME_LABELS.has(o.label) && (/^\s+["“'‘]?$|^["”'’]\s+$/.test(text.slice(o.end, s.start)) || /^\s+["“'‘]?$|^["”'’]\s+$/.test(text.slice(s.end, o.start))));
    const isName = (s.label === "GIVENNAME" || partOfFull) && NAME_LABELS.has(s.label) && /^[\p{Lu}][\p{L}'’-]{2,}$/u.test(v);
    const isHandle = (s.label === "USERNAME" && v.length >= 4) || s.label === "EMAIL";
    if (!(isName || isHandle) || seen.has(s.label + v)) continue;
    seen.add(s.label + v);
    const re = new RegExp("(?<![\\p{L}\\p{N}_@.])" + v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\p{L}\\p{N}_])", "gu");
    let m;
    while ((m = re.exec(text))) {
      const a = m.index, b = a + v.length;
      if (covered[a] || covered[b - 1]) continue;
      if (isName && s.label === "LASTNAME" && /^\s+\p{Ll}/u.test(text.slice(b, b + 3)) && !/^\s+(said|says|asked|told|wrote|replied|approved|signed|has|had|is|was|will|and|or)\b/.test(text.slice(b, b + 12))) continue;
      if (isName && (ORG_TAIL.test(text.slice(b, b + 14)) || /^\s+[\p{Lu}][\p{L}]/u.test(text.slice(b, b + 4)) || (/^\s+\p{Ll}/u.test(text.slice(b, b + 3)) && !(sentenceStart(text, a) ? PERSON_NEXT_STRONG : PERSON_NEXT).test(text.slice(b, b + 16))) ||
                     (/\b(in|on|at|of|the|a|an|by|from|to|until|since|during|this|next|last|every)\s+$/i.test(text.slice(Math.max(0, a - 10), a)) &&
                      /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|mon|tue|wed|thu|fri|sat|sun)/i.test(v)) ||
                     inNameList(text, a, b) ||
                     /\b(the|a|an)\s+$/i.test(text.slice(Math.max(0, a - 4), a)) || PRODUCTS.test(v)))
        continue;
      add.push({ start: a, end: b, label: s.label, text: v, propagated: true });
      for (let i = a; i < b; i++) covered[i] = 1;
    }
  }
  let all = spans.concat(add).sort((x, y) => x.start - y.start);
  for (const s of all) {
    if (!NAME_LABELS.has(s.label)) continue;
    // "Vikram D'Souza (विक्रम डिसूज़ा on the Hindi form)": the same name glossed in another script
    const gl = /^ \(([^\x00-\x1f\x21-\x7f(),;]+?)(?=\s+[a-z]|\)|,)/u.exec(text.slice(s.end, s.end + 80));
    if (gl && /\p{L}/u.test(gl[1]) && !/[A-Za-z]/.test(gl[1])) {
      const a = s.end + 2, b = a + gl[1].trimEnd().length;
      if (!covered[a]) { add.push({ start: a, end: b, label: s.label, text: text.slice(a, b), glossOf: s.start }); for (let i = a; i < b; i++) covered[i] = 1; }
    }
  }
  return spans.concat(add.filter(x => !spans.includes(x))).sort((x, y) => x.start - y.start);
}


// the people of this document, from the name spans (adjacent parts form one person)
export function peopleOf(text, spans) {
  const people = [];
  const names = spans.filter(s => NAME_LABELS.has(s.label)).sort((x, y) => x.start - y.start);
  for (let i = 0; i < names.length; i++) {
    let j = i, parts = [];
    const take = s => text.slice(s.start, s.end).split(/[\s,]+/).map(w => w.replace(/[.'’]s?$/, "").toLowerCase()).filter(w => w.length >= 2);
    parts.push(...take(names[i]));
    while (j + 1 < names.length && /^(\s+|, |\s+["“'‘]|["”'’]\s+)$/.test(text.slice(names[j].end, names[j + 1].start))) { j++; parts.push(...take(names[j])); }
    if (parts.length) people.push({ parts, latin: parts.every(p => /^[a-z'-]+$/.test(p)) });
    i = j;
  }
  return people;
}

export const STOP_SPEAKERS = /^(system|bot|admin|agent|user|customer|support|note|error|warning|info|debug|subject|from|to|cc|date|re|fwd|summary|answer|question|q|a|status|reply|update|team|host|server|client|you|me)$/i;

// names written inside tokens, in odd case, spaced out, in leetspeak, ROT13, other scripts, initials, chat speakers
export function namesInTokens(text, spans) {
  // the document's people are defined by names written with a capital (or in another script); lower-case finds are
  // checked against them, never the other way round
  const capNames = spans.filter(s => !NAME_LABELS.has(s.label) || !/^\p{Ll}/u.test(text.slice(s.start, s.end)));
  const people = peopleOf(text, capNames).filter(p => p.latin);
  const partOf = new Map();                       // part -> people containing it
  for (const p of people) for (const x of p.parts) if (x.length >= 3) { if (!partOf.has(x)) partOf.set(x, new Set()); partOf.get(x).add(p); }
  const covered = new Uint8Array(text.length + 1);
  for (const s of spans) if (!KEEP_LABELS.has(s.label)) for (let i = s.start; i < s.end; i++) covered[i] = 1;
  const free = (a, b) => { for (let i = a; i < b; i++) if (covered[i]) return false; return true; };
  const add = [];
  const isName = s => NAME_LABELS.has(s.label);
  const push = (a, b, extra = {}) => {
    if (b <= a) return;
    if (!free(a, b) && extra.parts) {           // a fuller reading of a name the network found only part of
      const inside = spans.filter(s => s.start < b && a < s.end && !KEEP_LABELS.has(s.label));
      if (inside.length && inside.every(s => isName(s) && s.start >= a && s.end <= b)) {
        for (const s of inside) { s.drop = true; for (let i = s.start; i < s.end; i++) covered[i] = 0; }
      }
    }
    if (free(a, b)) { add.push({ start: a, end: b, label: "GIVENNAME", text: text.slice(a, b), ...extra }); for (let i = a; i < b; i++) covered[i] = 1; }
  };
  const known = w => partOf.has(w);
  const leetKnown = w => /\d/.test(w) && /[a-z]/i.test(w) && [unleet(w), unleet(w).replace(/i/g, "l")].some(known);
  // 1. compound tokens: camelCase, snake_case, kebab, dotted, hashtags, emoji-wrapped, paths
  const TOK = /[^\s"'`<>()\[\]{},;|=:!?]+/gu;
  let m;
  while ((m = TOK.exec(text))) {
    const tok = m[0].replace(/[.…]+$/, ""), base = m.index;            // a sentence's full stop is not part of the token
    if (tok.length > 200) continue;                                      // names inside a token are short; bounds the work
    if (/^\p{L}{3,}$/u.test(tok) && known(tok.toLowerCase()) && /\p{Ll}\p{Lu}/u.test(tok) && /\p{Lu}\p{Ll}/u.test(tok.slice(1))) {
      push(base, base + tok.length, { parts: [tok.toLowerCase()] }); continue;
    }
    const pieces = [];
    const SUB = /[\p{L}\d]*\d[\p{L}\d]*|[\p{Lu}]?[\p{Ll}]+|[\p{Lu}]+(?![\p{Ll}])/gu;
    let q;
    while ((q = SUB.exec(tok))) pieces.push({ w: q[0], a: base + q.index, b: base + q.index + q[0].length });
    const nameOf = w => known(w.toLowerCase()) ? w.toLowerCase() : [unleet(w), unleet(w).replace(/i/g, "l")].find(known);
    const matched = pieces.map(p => known(p.w.toLowerCase()) || leetKnown(p.w));
    const nMatch = matched.filter(Boolean).length;
    if (!nMatch) continue;
    const compound = pieces.length >= 2 || /[^\p{L}\d]/u.test(tok);
    const odd = pieces.length === 1 && (/^(?=.*\p{Ll})(?=.*\p{Lu})/u.test(tok) && !/^\p{Lu}\p{Ll}+$/u.test(tok) || /\d/.test(tok) || (/^\p{Lu}{4,}$/u.test(tok)));
    if (!compound && !odd) continue;
    // mask runs of matched pieces (with the separators between them)
    for (let i = 0; i < pieces.length; i++) {
      if (!matched[i]) continue;
      let j = i;
      while (j + 1 < pieces.length && matched[j + 1] && /^[_\-.]?$/.test(text.slice(pieces[j].b, pieces[j + 1].a))) j++;
      let endB = pieces[j].b;
      const nx = pieces[j + 1], ps = pieces.slice(i, j + 1).map(x => nameOf(x.w));
      if (nx && (nx.a === endB || (nx.a === endB + 1 && /[_.-]/.test(text[endB]))) && /^\p{Lu}$/u.test(nx.w) && people.some(p => ps.every(x => p.parts.includes(x)) && p.parts.some(x => !ps.includes(x) && x[0] === nx.w.toLowerCase()))) endB = nx.b;
      push(pieces[i].a, endB, { inToken: true, parts: ps });
      i = j;
    }
  }
  for (const s of spans) {
    if (s.label !== "USERNAME") continue;
    const ps = text.slice(s.start, s.end).split(/[._\-]+/).map(x => x.toLowerCase());
    const key = text.slice(Math.max(0, s.start - 14), s.start);
    if (ps.every(known) && (ps.length >= 2 || /^\p{L}+$/u.test(text.slice(s.start, s.end))) && !/(user|login|handle|account|uid)\w*"?\s*[:=]\s*"?$/i.test(key)) { s.label = "GIVENNAME"; s.parts = ps; }
  }
  // a lower-case name span keeps only its words that are names of this document's people ("ms sharma ive noted")
  for (const s of spans) {
    if (!NAME_LABELS.has(s.label) || s.drop) continue;
    const t = text.slice(s.start, s.end);
    if (!/^[\p{Ll}][\p{Ll}' -]*$/u.test(t) || !/\s/.test(t)) continue;
    const ws = [...t.matchAll(/\p{Ll}[\p{Ll}'-]*/gu)];
    const kn = ws.filter(w => known(w[0]));
    if (kn.length && kn.length < ws.length) { s.start += kn[0].index; s.end = s.start - kn[0].index + kn[kn.length - 1].index + kn[kn.length - 1][0].length; s.text = text.slice(s.start, s.end); }
  }
  // an unknown lower-case word glued to a known name part is not part of that name ("sharma ive")
  for (const s of spans) {
    if (!NAME_LABELS.has(s.label) || s.drop) continue;
    const t = text.slice(s.start, s.end);
    if (!/^\p{Ll}+$/u.test(t) || known(t) || /^(van|von|der|den|de|del|della|di|da|das|dos|du|la|le|bin|binti|bint|ibn|al|el|ter|ten|af|av|y|e|zu|abu|ben|bat|mac|mc|st)$/.test(t)) continue;
    const nb = spans.find(o => o !== s && !o.drop && NAME_LABELS.has(o.label) && known(text.slice(o.start, o.end).toLowerCase()) &&
                          (/^\s+$/.test(text.slice(o.end, s.start)) || /^\s+$/.test(text.slice(s.end, o.start))));
    if (nb) s.drop = true;
  }
  for (const s of spans) {
    if (s.label !== "USERNAME" || s.drop) continue;
    const v = text.slice(s.start, s.end).toLowerCase();
    if (/^\p{L}+$/u.test(v) && known(v) && text[s.end] === ":" && /(^|\n)(\[[\d:apmAPM ]+\]\s*)?$/.test(text.slice(Math.max(0, s.start - 14), s.start))) { s.label = "GIVENNAME"; s.parts = [v]; }
  }
  // a role word at a chat line's start is not a handle ("[09:00] agent: ...")
  for (const s of spans) if (s.label === "USERNAME" && STOP_SPEAKERS.test(text.slice(s.start, s.end)) && text[s.end] === ":") s.drop = true;
  // 2. two plain lower-case words that are a known person's name in order ("priya sharma")
  for (const p of people) {
    if (p.parts.length < 2) continue;
    const re = new RegExp("(?<![\\p{L}])" + p.parts.join("[\\s._-]+") + "(?![\\p{L}])", "gu");          // lower-case spelling only
    while ((m = re.exec(text))) push(m.index, m.index + m[0].length, { parts: p.parts.slice() });
  }
  // "Iyengar (Arun)": a surname with the given name in brackets is that one person
  const SG = /(\p{Lu}[\p{Ll}'-]+) \((\p{Lu}[\p{Ll}'-]+)\)/gu;
  while ((m = SG.exec(text))) {
    const a = m[1].toLowerCase(), b = m[2].toLowerCase();
    if (people.some(p => p.parts.includes(a) && p.parts.includes(b))) {
      for (const sp of spans) if (sp.start >= m.index && sp.end <= m.index + m[0].length) sp.drop = true;
      for (let i = m.index; i < m.index + m[0].length; i++) covered[i] = 0;
      push(m.index, m.index + m[0].length, { parts: [b, a] });
    }
  }
  // formulas: literals joined by CONCATENATE / & that spell a known person's name or address
  const FX = /=\s*(CONCATENATE|CONCAT|TEXTJOIN)?\s*\(?([^\n]*)/gi;
  while ((m = FX.exec(text))) {
    const lits = [...m[2].matchAll(/"([^"]*)"/g)];
    if (lits.length < 2) continue;
    const fparts = lits.map(l => l[1].toLowerCase()).filter(known);
    for (const l of lits) {
      const w = l[1].toLowerCase(), a = m.index + m[0].length - m[2].length + l.index + 1;
      if (known(w)) {
        for (const sp of spans) if (sp.start < a + w.length && a < sp.end && !KEEP_LABELS.has(sp.label)) { sp.drop = true; for (let i = sp.start; i < sp.end; i++) covered[i] = 0; }
        push(a, a + w.length, { parts: fparts });
      }
    }
  }
  // 3. spaced-out letters: "P R I Y A", "m.e.e.r.a"
  const SP = /(?<![\p{L}])(\p{L})((?:[ .](\p{L})){2,})(?![\p{L}])/gu;
  while ((m = SP.exec(text))) { const w = m[0].replace(/[ .]/g, "").toLowerCase(); if (known(w)) push(m.index, m.index + m[0].length, { parts: [w] }); }
  // 4. other scripts and transliterations (Devanagari, Tamil, Latin with diacritics), and ROT13 pairs
  const people2 = peopleOf(text, spans);
  const skel = new Map();
  for (const p of people2) if (p.latin) p.skel = p.parts.map(skeleton);
  const SCR = /(?:[\u0900-\u097F\u0B80-\u0BFF]+|[\p{L}\p{M}]*[^\x00-\x7f\s][\p{L}\p{M}]*)(?:\s+(?:[\u0900-\u097F\u0B80-\u0BFF]+|[\p{L}\p{M}]*[^\x00-\x7f\s][\p{L}\p{M}]*))*/gu;
  while ((m = SCR.exec(text))) {
    const words = m[0].split(/\s+/).filter(Boolean);
    if (!words.every(w => /^[\p{L}\p{M}]+$/u.test(w))) continue;          // letters only: an emoji is not part of a name
    const sk = words.map(skeleton);
    const hit = people2.find(p => p.skel && sk.length >= 1 && sk.length <= p.skel.length && sk.every(x => x.length >= 2 && p.skel.includes(x)));
    if (hit) push(m.index, m.index + m[0].length, { parts: hit.parts.slice(0, sk.length) });
  }
  const CAP2 = /\b(\p{Lu}\p{Ll}{2,})\s+(\p{Lu}\p{Ll}{2,})\b/gu;
  while ((m = CAP2.exec(text))) {
    const a = rot13(m[1]).toLowerCase(), b = rot13(m[2]).toLowerCase();
    const count = w => (text.match(new RegExp("\\b" + w + "\\b", "gi")) || []).length;
    if (people.some(p => p.parts.includes(a) && p.parts.includes(b)) && count(a) + count(b) > count(m[1]) + count(m[2]))
      push(m.index, m.index + m[0].length, { parts: [a, b] });
  }
  // a short run in another script inside a mostly Latin-script line: a name written in its own script
  // (runs bounded to 30 letters: unbounded runs on both sides of a non-Latin letter backtrack quadratically on long input)
  const NL = /(?<![\p{L}\p{M}])((?:[\p{L}\p{M}]{0,30}[^\x00-\u024F\s\p{P}\p{S}\p{N}][\p{L}\p{M}]{0,30})(?:[ ·・][\p{L}\p{M}]{0,30}[^\x00-\u024F\s\p{P}\p{S}\p{N}][\p{L}\p{M}]{0,30}){0,3})(?![\p{L}\p{M}])/gu;
  const lineStats = new Map();                    // letters per line, counted once per line (not once per match)
  while ((m = NL.exec(text))) {
    const ls = text.lastIndexOf("\n", m.index) + 1;
    if (!lineStats.has(ls)) {
      const le = text.indexOf("\n", m.index) < 0 ? text.length : text.indexOf("\n", m.index), line = text.slice(ls, le);
      lineStats.set(ls, [(line.match(/[A-Za-z]/g) || []).length, (line.match(/[^\x00-\u024F\s\p{P}\p{S}\p{N}]/gu) || []).length]);
    }
    const [latin, other] = lineStats.get(ls);
    if (latin >= 12 && latin >= 2 * other && m[1].length >= 2 && !/^[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]{5,}$/u.test(m[1])) push(m.index, m.index + m[1].length);
  }
  // 5. initials of exactly one known person ("AK said", not "P.S.")
  const multi = people.filter(p => p.parts.length >= 2);
  const INI = /(?<![\p{L}.])\p{Lu}{2,3}(?![\p{L}.])/gu;
  while ((m = INI.exec(text))) {
    const ini = p => [p.parts.map(x => x[0]).join("").toUpperCase(), (p.parts[0][0] + p.parts[p.parts.length - 1][0]).toUpperCase()];
    const hits = [...new Map(multi.filter(p => ini(p).includes(m[0]) || ini({ parts: p.parts.slice().reverse() }).includes(m[0])).map(p => [p.parts.slice().sort().join(" "), p])).values()];
    if (hits.length === 1) push(m.index, m.index + m[0].length, { parts: hits[0].parts });
  }
  // 6. chat speakers: "[10:02] Kavya: done", "🌼Meera🌼: hi"
  const SPK = /^(?:\[[\d:apmAPM ]+\]\s*|\d{1,2}:\d{2}\s*(?:[AP]M)?\s*[-–]?\s*)?([^\p{L}\s\d:]{0,4})(\p{Lu}[\p{Ll}'-]{1,20})([^\p{L}\s\d:]{0,4}):\s/gmu;
  while ((m = SPK.exec(text))) {
    const name = m[2], stamped = /^\[|\d:\d/.test(m[0]), decorated = !!(m[1] || m[3]);
    if ((stamped || decorated) && !STOP_SPEAKERS.test(name)) { const a = m.index + m[0].indexOf(name, m[1].length); push(a, a + name.length); }
  }
  return spans.filter(s => !s.drop).concat(add).sort((x, y) => x.start - y.start);
}
