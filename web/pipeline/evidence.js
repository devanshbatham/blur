// Evidence gate: a weak span is kept only with positive evidence (a cue, a shape, a structure).
import { TOKEN_PREFIX } from "../structure.js";
import { KEEP_LABELS } from "./common.js";
import { urlContext } from "./finishing.js";
import { HOST_DEV, roleOf } from "./labels.js";
import { specificKind } from "./validators.js";


// ---- positive evidence: a value guessed from its shape alone is not masked. It needs a cue before it, a structural
// position (key, column, URL part, chat speaker), or a format that validates (checksum, provider prefix).
export const CUE = {
  USERNAME: /(user ?name|username|user ?id|user|login|log(ged)? in|sign(ed)? in|handle|account|acct|nick(name)?|alias|screen ?name|gamer ?tag|ign|uid|member|profile|author|owner|posted by|sent by|from|by|dm|follow(ing)?|tag(ged)?|mention(ed)?|ping(ed)?|under|as)\b[^a-z0-9\n]{0,4}((is|was|as|under|named|called|id|name)\b[^a-z0-9\n]{0,3}){0,2}$/i,
  ID: /(\bid|\bno\.?|number|\bnum|#|\bmrn|uhid|abha|aadhaa?r|\bpan|\bssn|\bsin|\bnin|nric|\bnhs|passport|licen[cs]e|\bdl|voter|epic|policy|member(ship)?|customer|client|patient|employee|\bemp|staff|student|roll|admission|enrol\w*|registration|\breg\.?|account|a\/c|acct|iban|\bupi|\bvpa|card|\btax|\btin|gstin|\bvat|beneficiary|folio|\buan|imei|serial|\bvin|plate|vehicle|\buid|identifier|badge|permit|certificate|insurance)\b[^.\n]{0,26}$/i,
  SECRET: /(pass(word|code|phrase)?|pwd|passwd|secret|token|api[_ -]?key|\bkey|\botp|\bpin|cvv|cvc|\bcode|credential|auth\w*|bearer|basic|cookie|session|\bsid|csrf|xsrf|jwt|sig(nature)?|answer|seed|mnemonic|recovery|backup|\bpsk|wi-?fi|hash|salt|private)\b[^\n]{0,40}$/i,
  ADDRESS: /(address|addr|ship(ping|ped)? to|deliver(y|ed)? to|bill(ing)? to|lives? (at|in|on)|living (at|in)|resid\w+|home|located at|house|flat|apartment|premises|property|venue|pickup|drop)\b[^.\n]{0,30}$/i,
};

export const ADDR_WORD = /\b(street|st\.?|road|rd\.?|lane|ln\.?|avenue|ave\.?|drive|dr\.?|boulevard|blvd|way|court|ct\.?|place|square|terrace|close|crescent|highway|flat|apt\.?|apartment|suite|unit|floor|block|tower|sector|phase|nagar|colony|layout|marg|chowk|cross|main|enclave|society|residency|villa|cottage|house|plot|door|po box|straße|strasse|rue|calle|via|avenida|rua|platz|weg|gasse)\b/i;

export const PRIVATE_IP = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|169\.254\.|0\.0\.0\.0|255\.)|^(::1|fe80:(?!.*ff:fe)|fc|fd)/i;

export function evidenceGate(text, spans) {
  const out = [];
  for (const s of spans) {
    const v = text.slice(s.start, s.end), lineStart = text.lastIndexOf("\n", s.start - 1) + 1;
    const before = text.slice(Math.max(lineStart, s.start - 64), s.start), prevLine = text.slice(Math.max(0, lineStart - 80), lineStart);
    const after = text.slice(s.end, s.end + 40);
    // a record line: a line that already holds two or more other masked values is a record about a person
    const le = text.indexOf("\n", s.end) < 0 ? text.length : text.indexOf("\n", s.end);
    const inRecord = spans.filter(o => o !== s && !KEEP_LABELS.has(o.label) && o.start >= lineStart && o.end <= le).length >= 2;
    const structural = s.byRule || s.fromColumn || s.value !== undefined || s.fromDecode || (s.kind && s.kind !== "ID") || s.propagated || inRecord;
    const keyed = /[\w"'\]]\s*[:=]\s*["'`]?$/.test(before);                      // right after  key:  key=  "key":
    const inUrl = !!urlContext(text, s.start) || /\b[a-z][a-z0-9+.-]{1,10}:\/\/\S*$/i.test(before) || /[?&;][\w.\-]+=$/.test(before);
    const acronym = /(?:^|[^A-Za-z])[A-Z]{2,8}(?:\s(?:No\.?|number|ID|code))?[\s:#]{1,3}$/.test(before);     // "DNI 12345678Z", "FIR No. 123"
    const digits = v.replace(/\D/g, "").length;
    let ok = true;
    if (s.label === "IP") ok = !PRIVATE_IP.test(v);
    else if (s.label === "USERNAME") {
      const speaker = /^(\[[\d:apmAPM ]+\]\s*|<)?$/.test(text.slice(lineStart, s.start)) && /^[>:]/.test(text.slice(s.end, s.end + 1));
      const handleShape = /[_\d]/.test(v) && /[a-z]/i.test(v) && v.length >= 5 && !/^[a-z]+\d$/.test(v) && !/\.[a-z]+$/.test(v) && /^[\w.-]+$/.test(v);
      // "@word" is a handle when it looks like one (digit, _, ., inner capital) or a cue says so; "@decorator" is code
      const atHandle = text[s.start - 1] === "@" && (/[_\d.]|[a-z][A-Z]/.test(v) || /(follow|dm|tag|mention|ping|cc|contact|handle|twitter|instagram|insta|telegram|x\.com|on x|by|from|thanks|hi|hey)\W{0,3}@?$/i.test(before) || /^\s+(on|at)\s+(x|twitter|instagram|insta|telegram|github|linkedin|slack|discord)\b/i.test(after));
      const pathSeg = s.net && /[\/\\]$/.test(text.slice(s.start - 1, s.start));          // "/home/<user>/", "C:\\Users\\<user>\\"
      ok = structural || atHandle || inUrl || pathSeg || speaker || HOST_DEV.test(v) || /^[\w.-]+@[\w.-]+$/.test(v) || CUE.USERNAME.test(before) ||
           /(^|\s)(-u|--user(name)?=?)\s*$/.test(before) || (keyed && /(user|login|handle|account|author|owner|member|nick|name|uid|by|ssid)\w*["']?\s*[:=]\s*["'`]?$/i.test(before)) ||
           (handleShape && /(^|[\s,(])$/.test(before.slice(-1)) && !/^[a-z]+[._-][a-z]+$/.test(v) && !/^\s*(=|\(|\.|\[)/.test(after));
    } else if (/^(ID|IDCARD)$/.test(s.label)) {
      // only shapes that are ambiguous by themselves need a cue: model-number-like codes, version strings, algorithm names
      const codeLike = (/^[A-Za-z]{1,10}[-\/ ]?\d[\w.\/-]*$/.test(v) && digits < 10) || /^\d+(\.\d+)+[\w-]*$/.test(v) || /^[A-Z]+\d*(-[A-Z]+\d*)+$/.test(v);
      const cls = /^(class|grade|std|standard)\b/i.test(v);
      const shape = specificKind(v) || /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(v) || /^[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}$/.test(v);
      const idCue = /((?<![a-z])id|\bno\.?|number|\bnum|#|\bmrn|uhid|abha|aadhaa?r|\bpan|\bssn|\bsin|\bnin|nric|\bnhs|passport|licen[cs]e|\bdl|voter|epic|policy|member(ship)?|customer|client|patient|employee|\bemp|staff|student|roll|admission|enrol\w*|registration|\breg\.?|account|a\/c|acct|iban|\bupi|\bvpa|card|\btax|\btin|gstin|\bvat|beneficiary|folio|\buan|imei|serial|\bvin|plate|vehicle|\buid|identifier|badge|permit|certificate|insurance|claim|medicare|fiscal\w*)(?![a-z])[^\n]{0,26}$/i.test(before);
      if (cls) ok = /\b(son|daughter|child|kid|ward|student|pupil|studies|studying|roll|admission|enrolled|his|her|my)\b/i.test(text.slice(Math.max(0, s.start - 90), s.end + 50));
      else if (codeLike) ok = structural || !!shape || !!roleOf(text, s.start, v) || idCue || acronym || inUrl;
    } else if (/^(SECRET|PASS)$/.test(s.label)) {
      const strong = TOKEN_PREFIX.test(v) || /^eyJ[\w-]+\.[\w-]+\./.test(v) || /^\$\d[a-z]?\$/.test(v) || /BEGIN [A-Z ]*PRIVATE KEY|\n/.test(v) ||
                     (v.length >= 20 && /\d/.test(v) && /[a-z]/.test(v) && /[A-Z]/.test(v) && !/\s/.test(v));
      const ui = text[s.start - 1] === ":" && /^@/.test(text.slice(s.end, s.end + 1));
      const secCue = new RegExp(CUE.SECRET.source.replace("private)", "private|cid|maiden name|first pet|memorable|security question|favou?rite|birthplace|first school|nickname|mother'?s|father'?s)"), "i");
      const pair = /(login|user(name)?|credentials?|creds)\b[^\n]{0,40}[\/:,]\s*$/i.test(before) || /(^|\s)(-u|--user)\s+[^\s:]+:$/.test(before);   // "user: priya / pass123", "-u priya:pass123"
      // (a secret the network found carries its own evidence: its cues and shapes are in the weights)
      ok = s.net || structural || strong || ui || inUrl || pair || secCue.test(before) || secCue.test(prevLine.trimEnd().slice(-50));
      if (ok && /^(yes|no|true|false|on|off|enabled|disabled|required|optional)$/i.test(v)) ok = false;
    } else if (s.label === "ADDRESS") {
      ok = structural || /[,\n]/.test(v) || ADDR_WORD.test(v) || /[^\x00-\x7f]/.test(v) || CUE.ADDRESS.test(before) || s.addrFromCue;
    } else if (s.label === "TEL") {
      ok = !(/^[\d,\s]+$/.test(v) && (v.match(/,\s/g) || []).length >= 3) && !/(product|model|sku|part|item|hsn|sac|batch|lot|isbn|ean|upc|order|invoice|tracking|ref(erence)?)\s*(code|no\.?|number|id|#)?\W{0,3}$/i.test(before);
    }
    if (ok) out.push(s);
  }
  return out;
}


// names next to firm markers, "SURNAME, I.", file-path users
export const FIRM_NEXT = /^\s*&\s*\p{Lu}|^\s+(&|and)\s+(Sons|Co\b|Company|Associates|Partners|Brothers|Bros)|^\s+(Co\.|Ltd|LLP|LLC|Inc|Pvt|PLC|GmbH|Memorial|Ward|Hospital|Clinic|University|College|School|Road|Rd|Lane|Street|St\.|Marg|Nagar|Sweets|Stores|Traders|Enterprises|Industries|Foundation|Trust)\b/u;

export const FIRM_PREV = /\p{Lu}[\p{L}'-]*\s*&\s*$/u;

export const MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];

export const MON_ABBR = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)$/i;

export function editDistance(x, y) {
  const d = Array.from({ length: x.length + 1 }, (_, i) => [i, ...Array(y.length).fill(0)]);
  for (let j = 1; j <= y.length; j++) d[0][j] = j;
  for (let i = 1; i <= x.length; i++) for (let j = 1; j <= y.length; j++)
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (x[i - 1] === y[j - 1] ? 0 : 1),
                       i > 1 && j > 1 && x[i - 1] === y[j - 2] && x[i - 2] === y[j - 1] ? d[i - 2][j - 2] + 1 : 99);
  return d[x.length][y.length];
}

// "exact" for a month name or its abbreviation, "fuzzy" for a misspelling of a full month name (same first letter,
// one edit for short names, two for long ones), null otherwise
export function monthMatch(w0) {
  const w = w0.toLowerCase();
  if (MON_ABBR.test(w) || MONTH_NAMES.includes(w)) return "exact";
  if (w.length < 4) return null;
  for (const m of MONTH_NAMES) if (m.length >= 5 && m[0] === w[0] && editDistance(w, m) <= (m.length >= 7 ? 2 : 1)) return "fuzzy";
  if (/^(sep|set)t?e?m?$/.test(w) || w === "setp") return "fuzzy";
  return null;
}

export const GREETING = /(^|\n|[.!?]\s)\s*(hi|hello|hey|dear|thanks|thank you|good (morning|afternoon|evening)|greetings|hola|bonjour|namaste|cheers)[,!]?\s+$/i;

export const nm0 = s => s.label === "GIVENNAME" || s.label === "LASTNAME";
