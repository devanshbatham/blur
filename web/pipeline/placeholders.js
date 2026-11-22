// Numbered placeholders ([PERSON_1]) and the ten output labels.
import { normalize } from "../normalize.js";
import { NAME_LABELS, OPTIONS } from "./common.js";
import { dateKeys } from "./consistency.js";
import { tryDecode } from "./decode.js";
import { labelOf } from "./labels.js";


// --- 3. numbered placeholders: one tag per entity (normalised, decoded, spoken, reversed and partly masked forms
// of a value share its tag; people are resolved by their name parts, never by a shared surname alone)
// --- the 10 output labels: OpenAI Privacy Filter's 8 plus private_health and online_identifier. Detection keeps its
// fine-grained labels internally (they drive linking and checks); only the written placeholder uses these.
export const LABEL10 = {
  PERSON: "private_person",
  ADDRESS: "private_address", POSTCODE: "private_address", GEO_COORDINATES: "private_address", SCHOOL: "private_address",
  EMAIL: "private_email",
  PHONE: "private_phone",
  DATE_OF_BIRTH: "private_date", DATE: "private_date",
  URL: "private_url",
  // account_number = financial accounts only
  CARD: "account_number", CARD_EXPIRY: "account_number", BANK_ACCOUNT: "account_number", IBAN: "account_number",
  UPI_ID: "account_number", CRYPTO_WALLET: "account_number",
  // personal_id = identifiers of a person issued by a government or an organisation
  AADHAAR: "personal_id", AADHAAR_VID: "personal_id", PAN: "personal_id", GSTIN: "personal_id", PASSPORT: "personal_id",
  PASSPORT_MRZ: "personal_id", DRIVING_LICENCE: "personal_id", VOTER_ID: "personal_id", SSN: "personal_id",
  NATIONAL_ID: "personal_id", VEHICLE_REG: "personal_id", MRN: "personal_id", HEALTH_ID: "personal_id",
  EMPLOYEE_ID: "personal_id", CUSTOMER_ID: "personal_id", CLASS: "personal_id", ROLL_NUMBER: "personal_id", ID: "personal_id",
  SECRET: "secret", PASSWORD: "secret", CVV: "secret", SESSION_TOKEN: "secret",
  DIAGNOSIS: "private_health", MEDICATION: "private_health", LAB_RESULT: "private_health", HEALTH_SCORE: "private_health",
  HEALTH: "private_health",                      // only written when OPTIONS.health is switched on
  USERNAME: "online_identifier", SOCIAL_HANDLE: "online_identifier", USER_ID: "online_identifier", IP: "online_identifier",
  MAC: "online_identifier", HOSTNAME: "online_identifier", DEVICE_ID: "online_identifier",
  POSTCODE: "private_address",
};

// an internal label without a mapping is an online identifier at most, never an account number by accident
export const label10 = kind => LABEL10[kind] || "personal_id";

export function numberedMask(text, spans, opts = {}) {
  const counters = {}, byValue = new Map();
  const norm = v0 => {
    let v = normalize(v0).text;
    for (const dec of tryDecode(v.trim())) { if (/^[\x20-\x7e]{3,}$/.test(dec)) { v = dec; break; } }
    const d = v.replace(/\D/g, "");
    if (d.length >= 10 && d.length >= v.replace(/[\s.\-()+]/g, "").length - 1) return d.slice(-10);   // phone numbers: last 10 digits
    return v.toLowerCase().replace(/[\s.\-()+]/g, "").replace(/'s$/, "");
  };
  const keep = [];
  let end = 0;
  for (const s of spans.slice().sort((x, y) => x.start - y.start)) { if (s.start >= end) { keep.push({ ...s }); end = s.end; } }
  // one mention per run of adjacent name parts; "Kumar (Sunita)" is one mention
  const merged = [];
  const partsOf = s => s.parts || text.slice(s.start, s.end).split(/[\s,;._\/-]+/).map(w => normalize(w).text.toLowerCase().replace(/[.'’]s?$/, "")).filter(Boolean);
  for (const s of keep) {
    const p = merged[merged.length - 1], gap = p ? text.slice(p.end, s.start) : null;
    const pn = p && NAME_LABELS.has(p.label), sn = NAME_LABELS.has(s.label);
    const listy = gap === ", " && (p.joinedByComma || p.parts.length > 1 || /\s/.test(text.slice(s.start, s.end)) || /^\s*(,|and\b|or\b|&)/.test(text.slice(s.end, s.end + 5)) ||
                                   !/^\p{Lu}/u.test(text.slice(p.start, p.end)) || !/^\p{Lu}/u.test(text.slice(s.start, s.end)));
    if (pn && sn && s.glossOf === undefined && ((/^\s+$/.test(gap) && !!s.inToken === !!p.inToken) || (gap === ", " && !listy && !s.inToken && !p.inToken))) {
      p.end = s.end; p.parts = p.parts.concat(partsOf(s)); if (gap === ", ") p.joinedByComma = true; continue;
    }
    if (pn && sn && /^[_.-]$/.test(gap)) { p.end = s.end; p.parts = p.parts.concat(partsOf(s)); continue; }   // ANIL_KUMAR, anil.kumar
    merged.push({ ...s, parts: sn ? partsOf(s) : [] });
  }
  // vCard "N:Kumar;Anil;;" — fields of one structured name are one person
  for (let i = 0; i + 1 < merged.length; i++) {
    const a = merged[i], b = merged[i + 1];
    if (NAME_LABELS.has(a.label) && NAME_LABELS.has(b.label) && /^(;|['"]\s*,\s*['"])$/.test(text.slice(a.end, b.start))) { const u = a.parts.concat(b.parts); a.parts = u; b.parts = u; }
  }
  // people: multi-part mentions define entities; a short form links only when exactly one entity fits
  const ents = [];
  const isInit = x => x.length === 1;
  for (const s of merged) {
    if (!NAME_LABELS.has(s.label) || s.parts.filter(x => !isInit(x)).length < 2) continue;
    const full = s.parts.filter(x => !isInit(x));
    let e = ents.find(e => full.every(x => e.parts.includes(x)) || e.parts.every(x => full.includes(x)));
    if (!e) { e = { parts: full.slice() }; ents.push(e); } else for (const x of full) if (!e.parts.includes(x)) e.parts.push(x);
    s.ent = e;
  }
  for (const s of merged) {
    if (!NAME_LABELS.has(s.label) || s.ent) continue;
    const words = s.parts.filter(x => !isInit(x)), inits = s.parts.filter(isInit);
    let c = ents.filter(e => words.every(x => e.parts.includes(x)) && inits.every(i => e.parts.some(x => x[0] === i && !words.includes(x))));
    if (s.glossOf !== undefined) { const g = merged.find(x => x.start <= s.glossOf && s.glossOf < x.end); if (g && g.ent) c = [g.ent]; }
    if (c.length === 1) s.ent = c[0];
    else if (c.length > 1) {                                              // never guess between two people ...
      const ls = text.lastIndexOf("\n", s.start) + 1, le = text.indexOf("\n", s.end) < 0 ? text.length : text.indexOf("\n", s.end);
      const here = c.filter(e => merged.some(o => o !== s && o.ent === e && o.start >= ls && o.end <= le));
      s.ent = here.length === 1 ? here[0] : { ambiguous: s.start };      // ... unless the same line names exactly one of them
    }
  }
  // quoted nickname right after a full name: "Ananya Iyer, "Annie" to the team"
  for (let i = 1; i < merged.length; i++) {
    const s = merged[i], prev = merged[i - 1];
    if (NAME_LABELS.has(s.label) && !s.ent && prev.ent && s.parts.length === 1 && s.start - prev.end <= 6 && /^\W*["'“‘(]$/.test(text.slice(prev.end, s.start).replace(/\s+/g, ""))) s.ent = prev.ent;
  }
  const entTag = new Map();
  // values: identity key per span, and one label per identity (the most specific any of its forms supports)
  const famOf = kind => (kind === "PASSWORD" || kind === "SECRET") ? "CRED" : kind === "PHONE" ? "PHONE" :
    /^(ID|AADHAAR|AADHAAR_VID|PAN|BANK_ACCOUNT|EMPLOYEE_ID|USER_ID|MRN|PASSPORT|PASSPORT_MRZ|DRIVING_LICENCE|VOTER_ID|NATIONAL_ID|SSN|VEHICLE_REG|GSTIN|IBAN)$/.test(kind) ? "IDENT" : kind;
  const phones = new Set();
  for (const s of merged) { s.kind0 = labelOf(s, text); if (s.kind0 === "PHONE") phones.add(norm(s.value || text.slice(s.start, s.end))); }
  for (const s of merged) {
    let v = norm(s.value || text.slice(s.start, s.end));
    if (s.kind0 !== "PHONE" && /^\d{10}$/.test(v) && phones.has(v.split("").reverse().join(""))) { s.kind0 = "PHONE"; v = v.split("").reverse().join(""); }
    if (s.kind0 === "DATE_OF_BIRTH") { const k = [...dateKeys(text.slice(s.start, s.end))]; if (k.length) v = k.sort()[0]; }
    s.key = famOf(s.kind0) + ":" + v;
  }
  const dobKeys = merged.filter(s => s.kind0 === "DATE_OF_BIRTH").map(s => [s, [...dateKeys(text.slice(s.start, s.end))]]);
  for (const [s, ks] of dobKeys) for (const [o, ko] of dobKeys) if (o !== s && ks.some(k => ko.includes(k))) { const kk = [s.key, o.key].sort()[0]; s.key = o.key = kk; }
  const bestKind = new Map();
  for (const s of merged) { const b = bestKind.get(s.key); if (!b || (b === "ID" && s.kind0 !== "ID")) bestKind.set(s.key, s.kind0); }
  for (const s of merged) {
    const kind = s.kind0 === "PERSON" ? "PERSON" : bestKind.get(s.key) || s.kind0;
    s.labelOut = kind;
    let tag = null;
    if (kind === "PERSON") {
      const key = s.ent && s.ent.ambiguous !== undefined ? "PERSON@" + s.start : s.ent || ("PERSON:" + s.parts.join(" "));
      tag = entTag.get(key);
      if (!tag) { counters.PERSON = (counters.PERSON || 0) + 1; tag = `[PERSON_${counters.PERSON}]`; entTag.set(key, tag); }
    } else {
      // one value, one tag: the family decides identity (an Aadhaar written plain or partly masked; a password in base64)
      tag = byValue.get(s.key);
      if (!tag) { counters[kind] = (counters[kind] || 0) + 1; tag = `[${kind}_${counters[kind]}]`; }
      byValue.set(s.key, tag);
    }
    s.tag = tag;
  }
  // write back so structured text still parses: a number in JSON / SQL becomes a quoted placeholder
  let outText = "", p = 0;
  for (const s of merged) {
    const before = text.slice(Math.max(0, s.start - 40), s.start), after = text.slice(s.end, s.end + 2);
    const bare = !/["']$/.test(before);
    const jsonNum = bare && /"\s*:\s*$/.test(before) && /^\s*[,}\]]/.test(after + "}");
    const sqlNum = bare && (s.quote || (/VALUES\s*\([^)]*$/i.test(before) && /[,(]\s*$/.test(before)));
    s.tag10 = `[${label10(s.labelOut)}]`;
    const shown = opts.numbered ? s.tag : s.tag10;
    const tag = jsonNum ? `"${shown}"` : sqlNum ? `'${shown}'` : shown;
    s.shown = tag;
    outText += text.slice(p, s.start) + tag; p = s.end;
  }
  return { text: outText + text.slice(p), spans: merged };
}
