// Finishing rules: the common false positives of everyday documents, decided by the text around a value.
import { NAME_LABELS } from "./common.js";
import { HOST_DEV } from "./labels.js";
import { pieces } from "./mask.js";
import { overlay, resolve } from "./spans.js";
import { luhn } from "./validators.js";


export const SCORE = "PHQ-?9|PHQ-?2|GAD-?7|EPDS|MMSE|MoCA|AUDIT-?C|BDI-?II|BDI|HAM-?D|HAM-?A|K10|PCL-?5|HbA1c|A1c|TSH|LDL|HDL|BMI|eGFR|GFR|INR|PSA|CRP|ESR|Hgb|Hb|FT4|T3|T4|BNP|SpO2|glucose|cholesterol|creatinine|triglycerides|ferritin";

export const SCORE_RE = new RegExp(`(?<![\\w-])(${SCORE})(?![\\w-])("?\\s*[:=]\\s*|\\s+(?:score\\s+)?(?:was|is|of|at|=|:)?\\s*|\\s+score:?\\s*)(\\d{1,3}(?:\\.\\d{1,2})?(?:\\/\\d{2,3})?%?)(?![\\w]|\\.\\d)`, "gi");

export const ID_WORDS = /^(PAN|GSTIN|GST|Aadhaar|Aadhar|AADHAAR|SSN|IBAN|SWIFT|BIC|IFSC|ABHA|UPI|MRN|NHS|NIN|EPIC|VID|UAN|PF|ESIC|TIN|EIN|ITIN|CVV|CVC|OTP|PIN|KYC|DOB|PNR|UTR)$/i;

export const LANG_WORDS = /^(Hinglish|Tanglish|Benglish|Spanglish|Romanised|Romanized|Devanagari|Latin|Cyrillic|Greek|Arabic|Hebrew|Tamil|Telugu|Kannada|Malayalam|Bengali|Bangla|Gurmukhi|Gujarati|Odia|Oriya|Hindi|Marathi|Punjabi|Urdu|Sanskrit|English|Spanish|French|German|Chinese|Japanese|Korean|Thai|Hiragana|Katakana|Kanji|Hangul|IAST|ITRANS|Unicode|ASCII)$/;

export const PRODUCTS = /^(slack|jira|confluence|trello|asana|notion|zoom|teams|discord|github|gitlab|bitbucket|stripe|twilio|heroku|vercel|netlify|docker|kubernetes|terraform|jenkins|figma|shopify|paypal|razorpay|paytm|google|microsoft|apple|amazon|azure|windows|linux|android|tesla|ford|lincoln|toyota|honda|hyundai|mercedes|chevrolet|jaguar|porsche|ferrari|nissan|kia|audi|bmw|volvo|uber|ola|swiggy|zomato|flipkart|netflix|spotify|whatsapp|telegram|signal|instagram|facebook|twitter|linkedin|youtube|chrome|firefox|safari|excel|outlook|gmail|okta|datadog|sentry|grafana|splunk|postgres|redis|kafka|mongo|mongodb|openai|anthropic|claude|gemini|copilot)$/i;

export const TECH = /^(base64|multipart|application|octet-stream|form-data|urlencoded|x-www-form-urlencoded|webkitformboundary|base32|base58|utf-?8|ascii|hex|sha\d*|md5|ipv4|ipv6|https?|http2|json|xml|yaml|toml|csv|oauth2?|jwt|jwk|b64|s3|ec2|k8s|x509|pkcs\d*|aes\d*|rsa\d*|ed25519|tls|ssl|ssh|gpg|pgp|totp|hotp|otp|saml|ldap|smtp|imap)$/i;

export const SAFE_PARAM = /[?&;](issuer|digits|period|algorithm|algo|lang|locale|theme|next|redirect|redirect_uri|return_to|utm_[a-z]+|page|sort|order|view|ref|source|format|v|version|sv|ss|srt|sp|se|st|spr|sslmode|charset|tz|region|mode|type|scope)=$/i;

export const PERSON_EVIDENCE = /^(\s*:|\s+(said|says|wrote|asked|replied|called|told|will|would|has|had|is|was|and \p{Lu})\b)/u;

// is position a inside a URL, and which path segment precedes it?
export function urlContext(text, a) {
  const ls = Math.max(text.lastIndexOf(" ", a), text.lastIndexOf("\n", a), text.lastIndexOf('"', a), text.lastIndexOf("(", a)) + 1;
  const head = text.slice(ls, a);
  if (!/^(https?:\/\/|www\.)|^[\w.-]+\.[a-z]{2,}\//i.test(head)) return null;
  const segs = head.replace(/^https?:\/\//i, "").split("/");
  return { host: segs[0].toLowerCase(), prev: (segs[segs.length - 2] || "").toLowerCase(), depth: segs.length - 1, inQuery: /[?#]/.test(head) };
}

export const PERSON_ROUTE = /^(users?|u|profile|profiles|people|person|in|id|customers?|patients?|accounts?|members?|employees?|students?|j|meeting|wa\.me|pay)$/;

export function finishing(text, spans) {
  let out = [];
  for (const s of spans) {
    let v = text.slice(s.start, s.end);
    // a social-profile URL: the site and route stay, the handle is the identifier; a repository or page is not a profile
    if (s.label === "PROFILE") {
      if (/^\/[\w@]/.test(text.slice(s.end, s.end + 2))) continue;                    // github.com/org/repo/...
      const cut = v.lastIndexOf("/");
      if (cut < 0 || cut === v.length - 1) continue;
      s.start += cut + 1; s.label = "USERNAME"; s.text = v = text.slice(s.start, s.end);
      if (v.startsWith("@")) { s.start++; v = v.slice(1); }
    }
    // --- measured on 1,000 everyday documents: the common false positives, as general rules ---
    // a number that is part of a money amount ("$20,000", "₹1,48,250.00", "USD 5,000")
    if (/^(ID|IDCARD|TEL|SOCIALNUMBER|CARD|POSTCODE|PASSPORT|DRIVERLICENSE)$/.test(s.label) && /^[\d,. ]+$/.test(v)) {
      let a0 = s.start, b0 = s.end;
      while (a0 > 0 && /[\d,.]/.test(text[a0 - 1])) a0--;
      while (b0 < text.length && /[\d,.]/.test(text[b0]) && /\d/.test(text[b0 + 1] || text[b0])) b0++;
      const tok = text.slice(a0, b0), pre = text.slice(Math.max(0, a0 - 5), a0);
      if (/([$€£₹¥]|\b(Rs\.?|INR|USD|EUR|GBP|AED|SGD))\s?$/i.test(pre) || (/^\d{1,3}(,\d{2,3})+(\.\d+)?$/.test(tok) && tok.length > v.length)) continue;
    }
    // an address has a number and a word; headings ("Section 1"), list numbers and phrases are not addresses
    if (/^(ADDRESS|STREET|POSTCODE)$/.test(s.label) && !s.fromColumn) {
      if (!/\d/.test(v) && !/,/.test(v)) continue;
      if (s.label === "ADDRESS" && /^\d+\.?$/.test(v)) continue;
      if (/^(Section|Article|Clause|Chapter|Step|Part|Item|Appendix|Figure|Table|Annex|Schedule|Rule|Paragraph|Question|Page|Line|Version|Phase|Stage|Level|Tier)\s+\d+[A-Za-z]?\.?$/i.test(v)) continue;
    }
    // cookie attributes are not values
    if (/^(COOKIE|SECRET)$/.test(s.label) && /\b(Path|Domain|Expires|Max-Age|SameSite|Secure|HttpOnly|Priority)=$/i.test(text.slice(Math.max(0, s.start - 10), s.start))) continue;
    // scientific notation and laboratory units are not passwords
    if (/^(PASS|SECRET)$/.test(s.label) && (/^\d+(\.\d+)?\^\d+/.test(v) || /^[\d.]+\s?(x\s?)?10\^/.test(v) || /^[\d.x^ ]*\/?(u|µ|m|d|k)?(L|l|g|mol|dL|mL|uL)\b/.test(v) && /\d/.test(v) && v.length < 12)) continue;
    // health: field labels and empty values are not facts about a person
    if (s.label === "HEALTH" && s.kind !== "LAB_RESULT" && s.kind !== "HEALTH_SCORE") {
      if (/^\**\s*:/.test(text.slice(s.end, s.end + 4))) continue;                                              // "Allergies:" is a key
      if (/^(none|none listed|not listed|not specified|not applicable|n\/a|nil|unknown|no known|nka|nkda|name|dosage|dose|frequency|medications?|allergies|allergy|diagnosis|diagnoses|conditions?|treatment|status|details|history|notes?|type|list|quantity|route|strength)$/i.test(v.trim())) continue;
      if (/\|\s*$/.test(text.slice(Math.max(0, s.start - 3), s.start)) && /^\s*\|/.test(text.slice(s.end, s.end + 12)) && /^\p{Lu}\p{Ll}+$/u.test(v) && /\n\s*\|[\s:|-]+\|\s*\n/.test(text.slice(s.end, s.end + 200).split("\n").slice(0, 3).join("\n") + "\n")) continue;   // table header cell
    }
    // in a URL query only user-type parameters hold a username
    // (the network reads URL structure itself: a handle or record it claimed in a URL stands)
    if (s.label === "USERNAME" && !s.net) {
      const q = /[?&]([\w.-]+)=$/.exec(text.slice(Math.max(0, s.start - 32), s.start));
      if (q && urlContext(text, s.start) && !/^(u|user|username|user_?name|login|handle|account|acct|uid|user_?id|email|name|owner|author|by|from|to|member|profile)$/i.test(q[1])) continue;
    }
    // a number that is a URL path segment is a page / issue / question number unless the route names a person or meeting
    if (/^(ID|IDCARD|TEL|SOCIALNUMBER)$/.test(s.label) && !s.net && /^\d+$/.test(v) && text[s.start - 1] === "/") {
      const u = urlContext(text, s.start);
      if (u && !u.inQuery && !PERSON_ROUTE.test(u.prev) && !/^(wa\.me|api\.whatsapp\.com|t\.me)$/.test(u.host)) continue;
    }
    // nothing inside a template reference is a value: ${{ vault.kyc.db_pass }}, ${DB_PASS}
    { const open = text.lastIndexOf("${", s.start), close = open >= 0 ? text.indexOf("}", open) : -1;
      if (open >= 0 && s.start - open < 60 && close >= s.end - 1 && !/\n/.test(text.slice(open, s.start))) continue; }
    // a value the same line calls a sample that is not real ("sample PAN from the spec, not a real person")
    if (/^(ID|IDCARD|SOCIALNUMBER|CARD|TEL|PASSPORT)$/.test(s.label)) {
      // (the sentence or code line that holds the value, not the whole paragraph)
      const from = Math.max(text.lastIndexOf("\n", s.start), text.lastIndexOf(". ", s.start)) + 1;
      const ends = [text.indexOf("\n", s.end), text.indexOf(". ", s.end)].filter(x => x >= 0);
      const ln = text.slice(from, ends.length ? Math.min(...ends) : text.length);
      if (/\b(sample|example|dummy|test|placeholder)\b/i.test(ln) && /\b(not (a )?real|fake|invalid|from the (spec|docs?|documentation|standard)|made[- ]up)\b/i.test(ln)) continue;
    }
    // service accounts in a URL's userinfo
    if (s.label === "USERNAME" && /:\/\/$/.test(text.slice(Math.max(0, s.start - 3), s.start)) && /(^(svc|sa|app|api|sys|bot|db)[_-]|[_-](rw|ro|svc|app|admin|user|service|bot|reader|writer|readonly)$)/i.test(v)) continue;
    // words being talked about: "Sterling, Hope, Grace and Banks are ordinary words"
    if (NAME_LABELS.has(s.label) && /^\p{Lu}\p{Ll}+$/u.test(v)) {
      const L = /((?:\p{Lu}\p{Ll}+(?:,\s+|\s+(?:and|or)\s+))*)$/u.exec(text.slice(Math.max(0, s.start - 80), s.start))[1];
      const R = /^((?:(?:,\s+|\s+(?:and|or)\s+)\p{Lu}\p{Ll}+)*)\s+(?:are|is|were|should|must|can|may)\b[^.\n]{0,60}\b(words?|names?|terms?|masked|kept|ordinary|common)\b/u.exec(text.slice(s.end, s.end + 160));
      if (R && (L.match(/\p{Lu}\p{Ll}+/gu) || []).length + (R[1].match(/\p{Lu}\p{Ll}+/gu) || []).length >= 2) continue;
    }
    // references and templates are never values: ${VAR}, ${{ secrets.X }}, <YOUR_TOKEN>, %(pw)s, $VAR
    if (/^(SECRET|PASS|COOKIE|ID)$/.test(s.label)) {
      const pre = text.slice(Math.max(0, s.start - 4), s.start), post = text.slice(s.end, s.end + 3);
      if (/\$\{\{?\s*$/.test(pre) || /^\$\{/.test(v) || /^\$[A-Z_][A-Z0-9_]*$/.test(v) || (/<$/.test(pre) && /^>/.test(post)) || /^%\([^)]*\)s$/.test(v)) continue;

      if (SAFE_PARAM.test(text.slice(Math.max(0, s.start - 16), s.start))) continue;
    }
    if (NAME_LABELS.has(s.label)) {
      const before = text.slice(Math.max(0, s.start - 24), s.start), after = text.slice(s.end, s.end + 24), one = /^[\p{L}\p{M}'.-]+$/u.test(v);
      // symbols, not names: a Greek letter in a short or mixed-script token ("πr", "ΔH")
      if (/\p{Script=Greek}/u.test(v) && (v.length <= 3 || /[A-Za-z]/.test(v))) continue;
      // a product or platform, not a person: "works with X", "compatible with X"
      if (one && /\b(works? with|compatible with|powered by|integrat\w+ with|pairs? with|available on|built[- ]in)\s+$/i.test(before)) continue;
      // a counted thing: "1 Allen key", "2 Phillips screws"
      if (one && /(^|[\s,(])\d+\s$/.test(before) && /^\s\p{Ll}{3,}/u.test(after) && !/^\s(said|says|and|or|from|at|in|on|is|was|has|had|will|called|asked|wrote)\b/.test(after)) continue;
      // a saint's name names a place, plant or institution: "St John's", "St. Mary"
      if (/\b(St\.?|Saint)\s$/.test(before) && !/\b(Mr|Mrs|Ms|Dr)\.?\s+\S*\s*St\.?\s$/.test(before)) continue;
      // one item in a list of places: "Jaipur, Agra and Delhi"
      if (one) {
        const isPlace = x => /^(CITY|COUNTRY|STATE)$/.test(x.label);
        const L = spans.some(x => isPlace(x) && x.end <= s.start && /^(, |,? and |,? or )$/.test(text.slice(x.end, s.start)));
        const R = spans.some(x => isPlace(x) && x.start >= s.end && /^(, |,? and |,? or )$/.test(text.slice(s.end, x.start)));
        if (L && (R || /^\s*([.!?\n]|$)/.test(after))) continue;
      }
    }
    // a key is never masked: "sessionid=", "\"name\":\"lang\"", "otp=" (its value may be)
    if (!s.value && /^[A-Za-z_][\w.-]{1,30}$/.test(v) && /[A-Za-z]{2}/.test(v) && (/^=(?!=)/.test(text.slice(s.end, s.end + 2)) || /"$/.test(text.slice(Math.max(0, s.start - 1), s.start)) && (/^"\s*:/.test(text.slice(s.end, s.end + 3)) && /[{,]\s*"$/.test(text.slice(Math.max(0, s.start - 12), s.start)) || /^"\s*,\s*"value"/.test(text.slice(s.end, s.end + 14)) && /"name"\s*:\s*"$/.test(text.slice(Math.max(0, s.start - 12), s.start)))) && s.label !== "EMAIL") continue;
    if (s.label === "USERNAME" && /^(__token__|oauth2|x-access-token|x-oauth-basic|x-token-auth|git|token|apikey|api|anonymous|guest)$/i.test(v)) continue;
    if (!NAME_LABELS.has(s.label) && /\.$/.test(v) && /^(\s|$)/.test(text.slice(s.end, s.end + 1)) && v.length > 2) { s.end--; }   // a sentence's full stop
    // a value that says it is an example is one; an authorisation code of a payment is a reference, not a credential
    if (/^(SECRET|PASS)$/.test(s.label) && (/(^|[-_ ])(example|sample|dummy)([-_ ]|\d*$)|^your[-_ ]|[-_]here$/i.test(v) || /\bauth(ori[sz]ation)? code:? ?$/i.test(text.slice(Math.max(0, s.start - 20), s.start)))) continue;
    // placeholders and dummy values are never secrets, whichever route found them
    if (/^(SECRET|PASS)$/.test(s.label) && /^["']?(changeme|change_me|change-me|password\d*|passw0rd|secret|xxx+|x{3,}|\*+|•+|null|none|nil|n\/a|redacted|hidden|example|sample|dummy|placeholder|todo|tbd|test\d*|admin|default|root|letmein|qwerty|123456\d*|your[-_ ]?\w*|replace[-_ ]?me|insert[-_ ]?\w*|<[^>]*>|\$\{[^}]*\}?)["']?$/i.test(v)) continue;
    if (/^[A-Za-z_][\w.-]{0,30}=$/.test(v) && /^["'A-Za-z0-9%$]/.test(text[s.end] || "")) continue;      // "otp=" before its value (not base64 padding)
    if (s.label === "USERNAME" && (TECH.test(v) || /^\.(com|org|net|io|in|co|uk|dev|app|ai|gov|edu|local|internal|cloud)\b/.test(text.slice(s.end, s.end + 9)))) continue;
    // software, brand and vehicle names are people only with evidence of a person
    if (NAME_LABELS.has(s.label) && PRODUCTS.test(v.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, ""))) {
      const near = spans.some(o => o !== s && NAME_LABELS.has(o.label) && (/^\s+$/.test(text.slice(o.end, s.start)) || /^\s+$/.test(text.slice(s.end, o.start))));
      const titled = /\b(Mr|Mrs|Ms|Mx|Dr|Prof)\.?\s+$/.test(text.slice(Math.max(0, s.start - 6), s.start));
      if (!near && !titled && !PERSON_EVIDENCE.test(text.slice(s.end, s.end + 12))) continue;
    }
    if (/^(ID|IDCARD)$/.test(s.label) && /^\p{L}+$/u.test(v) && !s.value) continue;          // a single plain word is not an identifier
    // (a UUID the network itself claimed was already judged in context: under a secret key, or introduced as an identifier)
    if (/^(ID|IDCARD|SECRET)$/.test(s.label) && !s.net && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v) &&
        !/(user|customer|patient|member|account|person|subject|uid)\w*["']?\s*[:=]\s*["']?$/i.test(text.slice(Math.max(0, s.start - 24), s.start)) &&
        !/\b(gaid|idfa|idfv|adid|aaid|advertising\s+id|ad\s+id|device\s+id|android\s+id|install\s+id|instance\s+id)\W*$/i.test(text.slice(Math.max(0, s.start - 24), s.start))) continue;
    if (NAME_LABELS.has(s.label) && (LANG_WORDS.test(v) || ID_WORDS.test(v))) continue;                 // scripts, languages, ID-type words
    // dotted lower-case names are code or hosts, not handles: "requests.exceptions", "payroll.example.com"
    if (s.label === "USERNAME" && /^[a-z0-9_-]+(\.[a-z0-9_-]+)+$/.test(v) && !HOST_DEV.test(v) && !(s.net && /[\/\\@]$/.test(text.slice(s.start - 1, s.start)))) {
      const line = text.slice(text.lastIndexOf("\n", s.start) + 1, (text.indexOf("\n", s.end) + 1 || text.length + 1) - 1);
      if (/\.(com|org|net|io|in|co|uk|dev|app|ai|gov|edu|local|internal|cloud|xyz|info|biz)$/.test(v) ||
          /(Traceback|File "|Error\b|Exception\b|^\s*at\s|import\s|raise\s|\.py\b|\.js\b|\.java\b)/.test(line)) continue;
    }
    // a value the text itself calls a template / placeholder / sample is kept
    if (/^(SOCIALNUMBER|ID|IDCARD|TEL|CARD|PASSPORT|DRIVERLICENSE)$/.test(s.label)) {
      const d = v.replace(/\D/g, "");
      const around = text.slice(Math.max(0, s.start - 70), Math.min(text.length, s.end + 70));
      const seq = d.length >= 7 && ("0123456789".includes(d) || "1234567890".includes(d) || /^(\d)\1+$/.test(d));
      if (seq && /\b(template|placeholder|example|sample|dummy|format|e\.g\.|test|fake|mask)\b/i.test(around)) continue;
    }
    if (s.label === "COOKIE" || s.label === "SECRET") {
      const key = /([\w.\-]+)=$/.exec(text.slice(Math.max(0, s.start - 30), s.start));
      if (key && /^_?(theme|lang|language|locale|tz|timezone|consent|currency|mode|font|region|country|display|layout|view|sort|density)$/i.test(key[1])) continue;
    }
    if (s.label === "USERNAME" && text[s.start] === "@") { s.start++; s.text = text.slice(s.start, s.end); }
    if (s.label === "CARD") {
      const d = text.slice(s.start, s.end).replace(/\D/g, "");
      // the sentence the number is in (a full stop ends it, with or without a space: "3208.Here are a few examples")
      const before = text.slice(Math.max(0, s.start - 160), s.start), after = text.slice(s.end, s.end + 160);
      const bs = Math.max(before.lastIndexOf("\n"), ...[...before.matchAll(/[.!?](?=\s|\p{Lu})/gu)].map(m => m.index));
      const ae = after.search(/[.!?](?=\s|\p{Lu}|$)|\n/u);
      const sent = before.slice(bs + 1) + text.slice(s.start, s.end) + (ae < 0 ? after : after.slice(0, ae));
      if (d.length >= 13 && !luhn(d) && /\b(invalid|sample|example|test|dummy|fake)\b/i.test(sent)) continue;
    }
    out.push(s);
  }
  // "/@handle" in a URL path: medium.com/@name, youtube.com/@channel
  for (const m2 of text.matchAll(/(?<=[a-z]\/)@([A-Za-z0-9._-]{2,40})(?=[\/?#\s"')]|$)/g)) {
    const a = m2.index + 1;
    if (urlContext(text, m2.index)) out = overlay(out, [{ start: a, end: a + m2[1].replace(/[.]+$/, "").length, label: "USERNAME" }]);
  }
  // an account number written in hyphenated groups is one value: "FR76-3000-6000-0100-0100-130"
  for (const s of out) {
    if (!/^(ID|IDCARD|CARD)$/.test(s.label)) continue;
    const pre = /(?:[A-Z0-9]{2,6}-)+$/.exec(text.slice(Math.max(0, s.start - 40), s.start)), post = /^(?:-?[A-Z0-9]{2,6})(?:-[A-Z0-9]{2,6})*(?![A-Za-z0-9])/.exec(text.slice(s.end, s.end + 40));
    const v0 = text.slice(s.start, s.end);
    if (pre && /\d/.test(pre[0]) && /^[A-Z0-9-]+$/.test(v0)) s.start -= pre[0].length;
    if (post && (v0.endsWith("-") || post[0].startsWith("-")) && /^[A-Z0-9-]+$/.test(v0) && /\d/.test(post[0])) s.end += post[0].length;
  }
  out = resolve(out);
  // values of lab tests and screening scores, as key/value or in prose
  let m;
  SCORE_RE.lastIndex = 0;
  const add = [];
  while ((m = SCORE_RE.exec(text))) {
    const a = m.index + m[0].length - m[3].length;
    add.push({ start: a, end: a + m[3].length, label: "HEALTH", kind: /^[a-z]/i.test(m[1]) && /PHQ|GAD|EPDS|MMSE|MoCA|AUDIT|BDI|HAM|K10|PCL/i.test(m[1]) ? "HEALTH_SCORE" : "LAB_RESULT" });
  }
  const DOSE_RE = /\b([A-Za-z][a-z]{4,}(?:\s+(?:ER|XR|SR|CR|XL|LA|DR))?)\s+(\d+(?:\.\d+)?\s?(?:mg|mcg|µg|ml|mL|IU|units?))\b/g;
  while ((m = DOSE_RE.exec(text))) {
    const ctx = text.slice(Math.max(0, m.index - 160), m.index + m[0].length + 60);
    if (/\b(her|his|my|their|patient|prescribed|taking|takes|took|on|medication|medicine|dose|tablet|leave|treatment)\b/i.test(ctx) && !/^(water|coffee|milk|juice|sugar|salt|tea|alcohol)$/i.test(m[1]))
      add.push({ start: m.index, end: m.index + m[0].length, label: "HEALTH", kind: "MEDICATION" });
  }
  for (const s of out) {
    if (s.label !== "HEALTH" || /^[\d.%\/]+$/.test(text.slice(s.start, s.end))) continue;
    const tail = /^((?: [a-z]{4,}){0,2}) \(([A-TV-Z]\d{2}(?:\.\d{1,3})?)\)/.exec(text.slice(s.end, s.end + 40));       // "... mellitus (O24.4)"
    if (tail) { s.end += tail[1].length; add.push({ start: s.end + 2, end: s.end + 2 + tail[2].length, label: "HEALTH", kind: "DIAGNOSIS" }); }
    const wk = /^[^.\n]{0,24}?[,;]\s*(\d{1,2} weeks(?: pregnant| gestation)?)\b/.exec(text.slice(s.end, s.end + 50));
    if (wk && /gestation|pregnan|antenatal|prenatal|obstetric|trimester/i.test(text.slice(Math.max(0, s.start - 40), s.end + 50))) {
      const a = s.end + wk[0].length - wk[1].length; add.push({ start: a, end: a + wk[1].length, label: "HEALTH", kind: "DIAGNOSIS" });
    }
  }
  out = overlay(out, add);
  const PEM = /-----BEGIN ([A-Z0-9 ]+)-----\r?\n([\s\S]*?)\r?\n-----END \1-----/g;
  const pem = [];
  while ((m = PEM.exec(text))) {
    if (/PUBLIC KEY|CERTIFICATE/.test(m[1]) && !/PRIVATE/.test(m[1])) continue;
    const a = m.index + m[0].indexOf(m[2]); pem.push({ start: a, end: a + m[2].length, label: "SECRET", kind: "SECRET" });
  }
  if (pem.length) {
    out = out.filter(s => !pem.some(p => s.start < p.end + 40 && p.start - 40 < s.end && /BEGIN|END|^[A-Za-z0-9+\/=\s-]+$/.test(text.slice(s.start, s.end))));
    out = overlay(out, pem);
  }
  // a machine-readable passport zone: every line of it is the same document
  const MRZ = /^[A-Z0-9<]{28,44}$/gm;
  const mrz = [];
  while ((m = MRZ.exec(text))) if (/<</.test(m[0])) mrz.push({ start: m.index, end: m.index + m[0].length });
  if (mrz.length) {
    const val = mrz.map(x => text.slice(x.start, x.end)).join("\n");
    out = overlay(out, mrz.map(x => ({ ...x, label: "ID", kind: "PASSPORT_MRZ", value: val })));
  }
  // after an address cue, capitalised words followed by a house number are an address, not a person
  for (const s of out) {
    if (!NAME_LABELS.has(s.label)) continue;
    const cue = text.slice(Math.max(0, s.start - 40), s.start);
    if (!/\b(address|addr|home|house|property|premises|office|located|residing|resides|lives|living|upkeep|deliver(?:y|ed)?|ship(?:ping|ped)?)\b[^.\n]{0,24}\b(is|at|to|:)\s*$/i.test(cue)) continue;
    const tail = /^(?:\s\p{Lu}[\p{L}.'-]+){0,3},?\s\d{1,5}[A-Za-z]?(?![\w@])/u.exec(text.slice(s.end, s.end + 50));
    const own = /\d/.test(text.slice(s.start, s.end));
    if (tail || own) { s.label = "ADDRESS"; s.kind = undefined; s.parts = undefined; if (tail) s.end += tail[0].length; s.addrFromCue = true; }
  }
  { const A = out.filter(s => s.addrFromCue); if (A.length) out = out.filter(s => s.addrFromCue || !A.some(a => a.start <= s.start && s.end <= a.end)); }
  // an address runs through its comma-separated parts up to the PIN / postcode on the same line
  for (const s of out) {
    if (s.label !== "ADDRESS") continue;
    const tail = /^((?:,\s*[\p{Lu}\d][\p{L}\d .'\/-]{0,40}?){0,6}?)(?:,\s*|\s+)(\p{Lu}[\p{L}]+(?: \p{Lu}[\p{L}]+)?\s+)?(\d{6}|\d{5}(?:-\d{4})?|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})(?![\w])/u.exec(text.slice(s.end, s.end + 160));
    if (tail && !/[\n(]/.test(tail[0])) s.end += tail[0].length;
  }
  const AW = /\b(No\.?|Flat|House|Plot|Door|Apt|Unit|Floor|Wing|Tower|Block|Cross|Main|Road|Rd|Street|St|Lane|Nagar|Layout|Sector|Phase|Stage|Colony|Extension|Apartments|Residency|Enclave|Marg|Chowk|Society|Village|Post)\b|\d/;
  for (const s of out) {
    if (s.label !== "ADDRESS") continue;
    let a = s.start;
    for (let k = 0; k < 8; k++) {
      const seg = /,\s*$/.test(text.slice(Math.max(0, a - 2), a)) ? /(?:^|[,:]\s*|\s(?=No\.|Flat|House|Plot|\d))([\p{Lu}\d][\p{L}\d .'\/#-]{0,40}?),\s*$/u.exec(text.slice(Math.max(0, a - 48), a)) : null;
      if (!seg || !AW.test(seg[1]) || /\n/.test(seg[0])) break;
      a = a - seg[0].length + seg[0].indexOf(seg[1]);
    }
    s.start = a;
  }
  // an address written over several lines: continue through short lines up to the one that ends with a PIN / postcode
  for (const s of out) {
    if (s.label !== "ADDRESS") continue;
    const le = text.indexOf("\n", s.end);
    if (le < 0 || !/^[\s,]*[\p{L}\d .'-]{0,40}$/u.test(text.slice(s.end, le))) continue;
    let p = le + 1, end = -1;
    for (let k = 0; k < 5; k++) {
      const ne = text.indexOf("\n", p) < 0 ? text.length : text.indexOf("\n", p), line = text.slice(p, ne);
      if (!line.trim() || line.length > 70 || /[:|=<>{}]/.test(line)) break;
      if (/(\b\d{6}|\b\d{5}(-\d{4})?|\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\s*$/.test(line)) { end = p + line.trimEnd().length; break; }
      p = ne + 1;
    }
    if (end > 0) s.end = end;
  }
  // pieces of one address on the same or next lines become one span
  const addr = out.filter(s => s.label === "ADDRESS").sort((x, y) => x.start - y.start);
  for (let i = 0; i + 1 < addr.length; i++) {
    const a = addr[i], b = addr[i + 1], gap = text.slice(a.end, b.start);
    if (/^((?:,\s*|\s*\n\s*)[\p{Lu}\d][\p{L}\d .'\/-]{0,30}){0,3}(,\s*|\s*\n\s*|\s+-\s+)$/u.test(gap)) { b.start = a.start; a.drop = true; }
  }
  return out.filter(s => !s.drop);
}
