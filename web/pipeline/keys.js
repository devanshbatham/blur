// Keys: values judged by the key they sit under, in JSON, YAML, CSV headers, forms and query strings.
import { KEEP_LABELS, NAME_LABELS } from "./common.js";

// ---------- keys: what a value is, judged by the key it belongs to ----------
// keyOf finds the key of the value that contains position a: a JSON key ("key": "...), a parameter (key=... in a query,
// form body, cookie or header), a header or record line (Key: ...), an XML element (<key>...), or an HTML field
// (name="key" ... value="..."). The key is normalised: lower case, a leading x- dropped, separators as "_".
export const normKey = k => k.toLowerCase().replace(/^x[-_]/, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

export function keyOf(text, a) {
  const ls = text.lastIndexOf("\n", a - 1) + 1, before = text.slice(Math.max(ls, a - 160), a);
  let m;
  if ((m = /"([A-Za-z_][\w.-]{0,40})"\s*:\s*"?[^",{}\[\]]*$/.exec(before))) return normKey(m[1]);
  if ((m = /(?:^|[?&;,#\s])([A-Za-z_][\w.-]{0,40})=["']?[^&;\s"'=:]*$/.exec(before))) return normKey(m[1]);
  { const c = csvKey(text, a); if (c) return c; }
  if ((m = /<([A-Za-z_][\w.-]{0,40})(?:\s[^<>]*)?>[^<]*$/.exec(before))) return normKey(m[1]);
  if ((m = /\bname=["']([\w.-]{1,40})["'][^<>]*\bvalue=["'][^"']*$/.exec(before))) return normKey(m[1]);
  if ((m = /(?:^|[\s,;(])([A-Za-z][\w-]{0,40})\s*:\s*[^:]*$/.exec(text.slice(ls, a))) && !/\d:\d/.test(text.slice(ls, a).slice(-12))) return normKey(m[1]);
  return null;
}

export const KEY_KEEP = new Set(("charset boundary realm qop nc nonce cnonce opaque algorithm alg typ kid type kind status event action operation operationname " +
  "scope grant_type response_type token_type currency locale lang language theme consent version api_version stripe_version app_version os_version " +
  "build region zone channel bot_id app_id client_id tenant_id project_id request_id amz_request_id amz_id_2 amz_version_id trace_id traceparent " +
  "span_id correlation_id message_id etag if_none_match cart cart_id sku product product_id item item_id " +
  "recently_viewed ab_test experiment variant remember_me label brand last4 card_last4 exp_month exp_year amount quantity battery accuracy_m " +
  "expires_in max_age path samesite method signedheaders amz_algorithm amz_expires amz_signedheaders amz_content_sha256 content_sha256 " +
  "content_type content_length accept accept_encoding vary cache_control pragma host user_agent server via connection code_challenge_method " +
  "fingerprint charge operationname dry_run synced logged_out marketing_opt_in contacts_hash checksum " +
  "hash sha256 md5 digest").split(/\s+/));

export const KEY_DEVICE = new Set("device_id advertising_id ad_id adid idfa idfv gaid aaid android_id imei imsi bssid mac mac_address device_serial serial_number".split(" "));

export const KEY_TRACK = new Set("ga gid ga_id fbp fbc ajs_anonymous_id anonymous_id visitor_id distinct_id amplitude_id mp_distinct_id".split(" "));

export const KEY_ADDR = new Set("line1 line2 line3 address_line1 address_line2 address1 address2 street street_address street1 street2".split(" "));

export const KEY_PLACE = new Set("city town state province country region_name district nationality county".split(" "));

export const KEY_POSTCODE = new Set("pin pincode pin_code postal_code postalcode zip zipcode zip_code postcode".split(" "));

export const KEY_PASSPORT = /^passport(_?(no|num|number|id))?$/;

export const KEY_SSID = /(^|_)(ssid|network_name|wifi_name)$/;

export const KEY_SECRETISH = /(pass|secret|token|key|auth|cred|sig|session|cookie|otp|pin|cvv|cvc|dsn|code_verifier|^code$)/;

export const KEY_HEADERLIKE = /^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+$/;

// the set of words used as keys with a non-prose value in this text ("Content-Type: application/json", "Host: api.x")
export function keyWords(text) {
  const out = new Set();
  for (const m of text.matchAll(/(?:^|\n)[ \t]*([A-Za-z][A-Za-z0-9-]{1,40})[ \t]*:[ \t]*([^\n]*)/g)) {
    // a key: a header-shaped name (Content-Type), a lower-case field name (charset), or any label whose value is machine
    // text - a URL, a MIME type, parameters (=, ;), a number, a host name, a hyphenated token - not a person speaking
    const v = m[2].trim();
    const machine = /^https?:|[=;]|^[\w.+-]+\/[\w.+*-]+|^[\d\s:.,+-]+$|^\S*[._-]\S*$|^(Bearer|Basic|Digest|AWS4|Negotiate)\b|\b\d{1,2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}|(^|, )[A-Z][a-z]+-[A-Z][\w-]*/.test(v);
    if (KEY_HEADERLIKE.test(m[1]) || /^[a-z_][a-z0-9_]*$/.test(m[1]) || machine && v.length > 0) out.add(m[1]);
  }
  return out;
}

// split a CSV line into cells (quotes respected); returns [start, end) offsets relative to the line
export function csvCells(line) {
  const out = []; let i = 0;
  while (i <= line.length) {
    let j = i;
    if (line[i] === '"') { j = i + 1; while (j < line.length && !(line[j] === '"' && line[j + 1] !== '"')) j += line[j] === '"' ? 2 : 1; j = line.indexOf(",", j); }
    else j = line.indexOf(",", i);
    if (j < 0) j = line.length;
    out.push([i, j]); i = j + 1;
    if (j >= line.length) break;
  }
  return out;
}

// the first line of a block of comma-separated lines whose cells are all short field names is a header row
export function csvHeader(text, a) {
  let ls = text.lastIndexOf("\n", a - 1) + 1;
  const lineAt = p => text.slice(p, text.indexOf("\n", p) < 0 ? text.length : text.indexOf("\n", p));
  if ((lineAt(ls).match(/,/g) || []).length < 2) return null;
  let p = ls;
  while (p > 1) { const q = text.lastIndexOf("\n", p - 2) + 1, l = lineAt(q); if (q >= p || (l.match(/,/g) || []).length < 2) break; p = q; }   // (q >= p: no earlier line)
  const head = lineAt(p);
  if (!/^[A-Za-z_][\w .-]{0,30}(,[A-Za-z_][\w .-]{0,30}){2,}$/.test(head) || /@|\d{3}/.test(head)) return null;
  return { start: p, end: p + head.length, cells: csvCells(head).map(([x, y]) => head.slice(x, y).trim()), lineStart: ls };
}

export function csvKey(text, a) {
  const h = csvHeader(text, a);
  if (!h || a < h.end + 1 && a >= h.start) return null;
  const line = text.slice(h.lineStart, text.indexOf("\n", h.lineStart) < 0 ? text.length : text.indexOf("\n", h.lineStart));
  const cells = csvCells(line), off = a - h.lineStart, k = cells.findIndex(([x, y]) => off >= x && off <= y);
  return k >= 0 && k < h.cells.length ? normKey(h.cells[k]) : null;
}

export function keyAware(text, spans) {
  const out = [], kw = keyWords(text);
  const isHeaderBlock = [...kw].filter(k => KEY_HEADERLIKE.test(k)).length >= 2;
  for (const s of spans) {
    if (KEEP_LABELS.has(s.label)) { out.push(s); continue; }
    const v = text.slice(s.start, s.end), k = keyOf(text, s.start), ls = text.lastIndexOf("\n", s.start - 1) + 1;
    { const h = csvHeader(text, s.start); if (h && s.start >= h.start && s.end <= h.end) continue; }      // a header cell is a field name
    const lineKey = (/^\s*([A-Za-z][A-Za-z0-9-]{1,40})\s*:/.exec(text.slice(ls, s.start)) || [])[1];
    const nm = NAME_LABELS.has(s.label) || s.label === "_NAME";
    // a word used as a key is not a name ("Host", "Content-Type", "Authorization"), nor is a header name in a header list
    if (nm && (kw.has(v) || isHeaderBlock && KEY_HEADERLIKE.test(v) || /^[ \t]*$/.test(text.slice(ls, s.start)) && /^\s*:/.test(text.slice(s.end, s.end + 3)) && kw.has(v))) continue;
    if (nm && isHeaderBlock && lineKey && KEY_HEADERLIKE.test(lineKey) && !/name|from|to|cc|author|owner|recipient|contact|user|customer|signed|by/i.test(lineKey) && !/filename=["'][^"']*$/.test(text.slice(ls, s.start))) continue;
    // an HTML or form field name is not a person: name="csrfmiddlewaretoken"
    if (nm && /<[a-z][\w-]*\b[^<>\n]*\bname=["']$/i.test(text.slice(ls, s.start)) && /^[\w.-]+$/.test(v) && /[a-z]/.test(v) && !/ /.test(v)) continue;
    // product and protocol tokens are not secrets, versions are not addresses: Mozilla/5.0, Safari/537.36, HTTP/1.1, Chrome/130.0.0.0
    if (/^[A-Za-z][A-Za-z.+-]{1,20}\/\d+(?:\.\d+)+$/.test(v) || s.label === "IP" && /[A-Za-z]\/$/.test(text.slice(Math.max(0, s.start - 1), s.start))) continue;
    if (/^(SECRET|PASS)$/.test(s.label) && /^(on|off|true|false|yes|no|none|null|enabled|disabled|light|dark|[a-z]{2}(-[A-Z]{2})?|utf-?8|ascii)$/i.test(v)) continue;
    if (/^(SECRET|PASS)$/.test(s.label) && /^\w+=(on|off|true|false|yes|no|\d{1,3})$/i.test(v)) continue;
    if (k) {
      if (KEY_KEEP.has(k) && s.label !== "EMAIL" && !(k === "last4" && /ssn|social/.test(text.slice(Math.max(0, s.start - 40), s.start)))) continue;
      if (KEY_PLACE.has(k) && /^[\p{L} .'-]+$/u.test(v)) continue;
      if (KEY_SSID.test(k)) { out.push({ ...s, label: "USERNAME", keyed: "DEVICE_ID" }); continue; }
      if (KEY_PASSPORT.test(k)) { out.push({ ...s, label: "ID", keyed: "PASSPORT" }); continue; }
      if (KEY_POSTCODE.has(k) && /^\d{3,7}(-\d{3,4})?$|^[A-Z0-9]{2,4} ?[A-Z0-9]{3}$/.test(v)) { out.push({ ...s, label: "POSTCODE", keyed: "POSTCODE" }); continue; }
      if (KEY_TRACK.has(k)) { out.push({ ...s, label: "USERNAME", keyed: "DEVICE_ID" }); continue; }
    }
    // an API object id ("evt_YrA3k...", "ch_D96mj...", "ct_f4dT...") is not a secret or a handle unless its key says credential
    if (/^[a-z]{2,5}_[A-Za-z0-9]{6,}$/.test(v) && k && /(^|_)(id|ids|charge|cart|order|invoice|event|object|document|doc|item|product|request|trace|message|thread|ticket|case|batch|job|run|build)$/.test(k) && !KEY_SECRETISH.test(k) && !/^(usr|user|uid|cus|acct|mem|emp)_/.test(v)) continue;
    // a dotted event or type name is not a handle: customer.updated
    if (s.label === "USERNAME" && /^[a-z]+(\.[a-z]+)+$/.test(v) && k && !/user|login|handle|nick|account/.test(k) &&
        !(s.net && /[\/\\@]$/.test(text.slice(s.start - 1, s.start)))) continue;                 // (a URL or path segment the network read)
    // a compact timestamp is a date, not an identifier: 20261116T091409Z, and the date inside an AWS credential scope
    if (/^(19|20)\d{6}(T\d{6}Z?)?$/.test(v) && (/T\d{6}/.test(v) || /\/$|%2F$/i.test(text.slice(s.start - 3, s.start)))) { out.push({ ...s, label: "DATE_PLAIN" }); continue; }
    // an AWS access key id with its credential scope: only the key id is secret
    { const m = /^(A[KS]IA[A-Z0-9]{16})(?:\/|%2F)/i.exec(v); if (m) { out.push({ ...s, end: s.start + m[1].length }); continue; } }
    if (/^(?:\/|%2F)?[a-z]{2}-[a-z]+-\d(?:\/|%2F)[a-z0-9-]+(?:\/|%2F)aws4_request$/i.test(v)) continue;
    // a name glued to a code: "OD-90311"
    if (nm && /^-\d/.test(text.slice(s.end, s.end + 2))) continue;
    out.push(s);
  }
  // additions judged by key: device identifiers, address lines, signatures
  const have = (a, b) => out.some(o => !KEEP_LABELS.has(o.label) && o.start < b && a < o.end);
  const addSpan = (a, b, label) => { if (b > a && !have(a, b)) out.push({ start: a, end: b, label, byRule: true }); };
  for (const m of text.matchAll(/(?:"([\w.-]{1,40})"\s*:\s*"([^"\n]{2,120})"|(?:^|\n)[ \t]*([A-Za-z][\w-]{1,40})[ \t]*:[ \t]*([^\n]{2,120}?)[ \t]*(?=\n|$))/g)) {
    const key = normKey(m[1] || m[3]), val = m[2] || m[4], a = m.index + m[0].lastIndexOf(val);
    if (KEY_DEVICE.has(key) && /[0-9a-f]/i.test(val) && val.length >= 8) addSpan(a, a + val.length, "USERNAME");
    if (KEY_ADDR.has(key) && /\d|\b(road|rd|street|st|lane|marg|nagar|block|cross|main|heights|apartments?|apt|floor|sector|avenue|ave)\b/i.test(val)) {
      for (const o of out) if (!/^(EMAIL|TEL)$/.test(o.label) && !KEEP_LABELS.has(o.label) && o.start >= a && o.end <= a + val.length) o.drop = true;
      if (!out.some(o => !o.drop && !KEEP_LABELS.has(o.label) && o.start < a + val.length && a < o.end)) out.push({ start: a, end: a + val.length, label: "ADDRESS", byRule: true });
    }
  }
  // a field whose name says key / token / secret / signature / session holds a secret when its value is a long random string
  const SECRET_KEY = /(^|_)(key|keys|token|tokens|secret|secrets|password|passwd|pwd|passphrase|signature|sig|session|sessionid|sid|auth|credential|credentials|cred|apikey|api_key|private_key|access_key|client_secret|csrf|xsrf)(_|$)|key_used$|keyid$/;
  for (const m of text.matchAll(/(?:"([\w.-]{1,48})"\s*:\s*"([^"\s]{16,400})"|(?:^|\n)[ \t]*([A-Za-z][\w-]{1,48})[ \t]*:[ \t]*([^\s;,]{16,400})[ \t]*(?=\n|$)|(?:^|[?&;\s])([A-Za-z_][\w.-]{1,48})=([^&;\s"']{16,400}))/g)) {
    const key = normKey(m[1] || m[3] || m[5]), val = m[2] || m[4] || m[6], a = m.index + m[0].lastIndexOf(val);
    if (!SECRET_KEY.test(key) || KEY_KEEP.has(key) || /(^|_)(type|id_type|algorithm|alg|expires?|expiry|ttl|length|name|format|version|hash|sha\d*|md5|checksum|digest|fingerprint|hint|url|uri|path|endpoint|header|scheme|method)$/.test(key)) continue;
    if (/^(https?:|\/|\$\{|<|\{\{)|^(YOUR|CHANGE|EXAMPLE|PLACEHOLDER|REDACTED|xxx)/i.test(val) || !/\d/.test(val) || !/[A-Za-z]/.test(val) || /^[\w.-]+@[\w.-]+$/.test(val)) continue;
    addSpan(a, a + val.length, "SECRET");
  }
  // signatures: AWS "Signature=<hex>", Stripe "v1=<hex>" in a signature header, X-Amz-Signature in a query
  for (const m of text.matchAll(/(?:\bSignature=|[?&]X-Amz-Signature=|(?:^|\n)[\w-]*Signature:[^\n]*?\bv\d=)([0-9a-f]{32,})/gi)) {
    const a = m.index + m[0].length - m[1].length; addSpan(a, a + m[1].length, "SECRET");
  }
  return out.filter(o => !o.drop).sort((x, y) => x.start - y.start);
}
