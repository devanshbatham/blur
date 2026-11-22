// Fine-grained kinds of value from their cue (PAN, MRN, passport, bank account, ...).
import { normalize } from "../normalize.js";
import { NAME_LABELS } from "./common.js";
import { specificKind } from "./validators.js";


// --- labels: the most specific label that the value's role, the cue before it, or a format check supports
export const HOST_DEV = /-(PC|LT|DT|MBP|MBA|LAPTOP|DESKTOP|MACBOOK(-PRO|-AIR)?|THINKPAD|IDEAPAD|XPS|SURFACE|IMAC|MINI|NOTEBOOK|WS|WKS|VM|PIXEL|GALAXY|IPHONE|IPAD|PHONE|TABLET)(\.local)?$|\.local$/i;

export const DOSE = /\b\d+(\.\d+)?\s?(mg|mcg|µg|g|ml|iu|units?|tabs?|tablets?|puffs?)\b|\b(daily|bid|tid|qid|od|bd|prn|nightly)\b/i;

export const DRUG = /(statin|pril|sartan|olol|dipine|xaban|parin|oxetine|traline|pram|faxine|azepam|zolam|prazole|tidine|mycin|cillin|cycline|floxacin|vir|mab|tinib|formin|gliptin|thyroxine|semide|profen|insulin|lithium|truvada)\b/i;

// Role cues: the words right before a value say what it is, and that outranks what its shape looks like.
// One ordered table; each entry is (cue words, label, test on the value). A few filler words may sit between cue and value.
export const FILL = "[^a-z0-9]{0,4}(?:(?:is|was|are|were|be|will|which|code|number|no\\.?|num|id|#|:|=|of|for|the|this|that|used|as|entered|provided|given|listed|shown|value|name|your|my|his|her|their|any|payments?)[^a-z0-9]{0,4}){0,4}$";

export const role = words => new RegExp("(?:^|[^a-z0-9])(?:" + words + ")" + FILL);

export const NUMERIC = v => /\d/.test(v) && !/\s[a-z]{3,}/i.test(v);

export const ROLES = [
  [role("cvv2?|cvc2?|cid|card verification(?: value| code)?|security code"), "CVV", v => /^[\d ]{3,7}$/.test(v) || /[a-z]/i.test(v)],
  [role("pin code|pincode|zip code|zip|postal code|postcode|post code"), "POSTCODE", v => /^\d{5,6}$|^\d{5}-\d{4}$|^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$/.test(v)],
  [role("pin|passcode|pin code|access code|unlock code|activation pin"), "SECRET", v => /^[\d. ]{3,20}$/.test(v)],
  [role("password|passwd|pwd|passphrase"), "PASSWORD", v => !/\s{2}/.test(v)],
  [role("api key|apikey|secret key|access key|access token|auth token|bearer token|client secret|api token"), "SECRET", v => v.length >= 6],
  [role("device identifier|device id|imei|imsi|meid|udid|android id|advertising id|serial number|serial no|serial"), "DEVICE_ID", NUMERIC],
  [role("routing number|routing no|bank routing|aba|swift bic|swift code|swift|bic|ifsc|sort code"), "BANK_ACCOUNT", v => /^[A-Z0-9 -]{6,20}$/i.test(v)],
  [role("account number|account no|acct number|acct no|a\\/c|bank account|iban"), "BANK_ACCOUNT", NUMERIC],
  [role("credit debit card|credit card|debit card|card number|card no"), "CARD", v => /^[\d -]{12,23}$/.test(v)],
  [role("fax number|fax no|fax|phone number|phone no|telephone|mobile number|mobile no|contact number|cell"), "PHONE", v => /^[+()\d][\d ().+-]{6,22}$/.test(v)],
  [role("health plan beneficiary number|beneficiary number|member id|membership number|policy number|employee id|employee number|staff id|customer id|customer number|client id|patient id|student id|medical record number|mrn|national id|tax id|tin|licen[cs]e number|licen[cs]e plate|registration number|certificate number"), "ID", NUMERIC],
  [role("ip address|ip addr|ipv4|ipv6|source ip|client ip"), "IP", v => /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-f:]{6,39}$/i.test(v)],
  [role("user ?name|user|login|handle|screen name|nickname"), "USERNAME", v => /^[A-Za-z][\w.-]{2,30}$/.test(v) && /[\d_.]|[a-z][A-Z]/.test(v)],
];

export function roleOf(text, start, v) {
  const cue = text.slice(Math.max(0, start - 60), start).toLowerCase().replace(/[*_`"'\[\](){}<>|]/g, " ").replace(/\s+/g, " ");
  for (const [re, lab, ok] of ROLES) if (re.test(cue) && ok(v)) return lab;
  return null;
}

export function labelOf(s, text) {
  if (s.keyed) return s.keyed;                                   // decided by the key the value belongs to
  const v = text.slice(s.start, s.end), cue = text.slice(Math.max(0, s.start - 32), s.start).toLowerCase();
  const near = re => re.test(cue);
  if (!NAME_LABELS.has(s.label) || /[\d_]/.test(v)) {            // (a plain name is never relabelled by a cue)
    const r = !s.kind || /^(ID|CARD|AADHAAR|IBAN)$/.test(s.kind) ? roleOf(text, s.start, v) : null;      // a cue outranks a shape or checksum match
    // (an identifier the network found stays an identifier: "the biometric identifier for this user is G7329485216")
    if (r && !(s.label === "EMAIL" || s.label === "URL") && !(r === "USERNAME" && s.net && /^(ID|IDCARD)$/.test(s.label))) return r;
  }
  if (s.label === "ADDRESS" && /^(\d{1,3}\.){3}\d{1,3}$/.test(v)) return "IP";
  // a cue word decides a number's role, over the network's shape guess (an account number can look like a phone)
  if (/^(TEL|CARD|ID|IDCARD|SOCIALNUMBER)$/.test(s.label) && /\d/.test(v)) {
    if (near(/\b(vid|virtual id)\W*$/)) return "AADHAAR_VID";
    if (near(/(a\/c|acct|account|bank a\/c|savings|current)\W*(no\.?|number|#)?\W*$/)) return "BANK_ACCOUNT";
    if (near(/aadhaa?r\w*\W*(no\.?|number)?\W*$/)) return "AADHAAR";
  }
  if (near(/(pass(?!port)|passwd|pwd|password|passphrase)\w*['"]?\s*[:=]\s*['"]?$/) ||
      /(pass(?!port)|passwd|pwd|password|passphrase)\w*\s*:\s*[>|][-+]?\s*\n(?:[ \t]+\S+\s*\n)*[ \t]+$/i.test(text.slice(Math.max(0, s.start - 120), s.start))) return "PASSWORD";
  if (/^(ID|TEL|IDCARD)$/.test(s.label) && /^\D*\d{10,13}\D*$/.test(normalize(v).text.replace(/[\s-]/g, "")) && near(/(phone|mobile|cell|tel|msisdn|whatsapp)[\w-]*["']?\s*[:=]\s*["']?$/)) return "PHONE";
  if (near(/(private_key_id|key_?id|kid|fingerprint|thumbprint)["']?\s*[:=]\s*["']?$/)) return "SECRET";        // key ids and fingerprints
  // a password inside a URL's user:password@ is a password
  if (s.label === "SECRET" && text[s.start - 1] === ":" && /^@/.test(text.slice(s.end, s.end + 1)) && /\/\/[^\s\/:@]+$/.test(text.slice(0, s.start - 1))) return "PASSWORD";
  switch (s.label) {
    case "GIVENNAME": case "LASTNAME": return "PERSON";
    case "EMAIL": return "EMAIL";
    case "TEL": return "PHONE";
    case "BOD": return "DATE_OF_BIRTH";
    case "DATE_PLAIN": return "DATE";
    case "PASS": return "PASSWORD";
    case "COOKIE": return "SESSION_TOKEN";
    case "GEOCOORD": return "GEO_COORDINATES";
    case "IP": case "MAC": case "CARD": case "CARD_EXPIRY": case "SCHOOL": case "URL": return s.label;
    case "ADDRESS": case "STREET": case "BUILDING": case "SECADDRESS": case "POSTCODE": return "ADDRESS";
    case "HEALTH":
      if (s.kind === "HEALTH_SCORE" || s.kind === "LAB_RESULT") return s.kind;
      if (/^[\d.\/%]+$/.test(v)) return "LAB_RESULT";
      return DOSE.test(v) || DRUG.test(v) ? "MEDICATION" : "DIAGNOSIS";
    case "SECRET":
      if (s.kind === "CVV" || near(/\b(cvv2?|cvc2?|cid|security code)\W*(is\W*)?$/)) return "CVV";
      return "SECRET";
    case "USERNAME":
      if (HOST_DEV.test(v)) return "HOSTNAME";
      if (text[s.start - 1] === "@" && text[s.start - 2] === "<") return "USER_ID";
      if (text[s.start - 1] === "@") return "SOCIAL_HANDLE";
      return "USERNAME";
  }
  // identifiers: format first, then the cue before the value
  const k = s.kind || specificKind(v);
  if (k && k !== "CARD") return k;
  if (k === "CARD") return "CARD";
  const compact = v.replace(/[\s-]/g, "");
  if (/^0x[0-9a-fA-F]{40}$/.test(v) || /^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$/.test(v)) return "CRYPTO_WALLET";
  if (/^P<[A-Z]{3}/.test(v) || /^[A-Z0-9<]{30,44}$/.test(compact) && /<{3,}/.test(v)) return "PASSPORT_MRZ";
  if (/^[\w.-]+@[a-z]+$/i.test(v)) return near(/health id|abha/) ? "HEALTH_ID" : "UPI_ID";
  if (/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(v)) return "GSTIN";
  if (/^(\d{2}\s?BH\s?\d{4}\s?[A-Z]{1,2}|[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4})$/.test(v)) return "VEHICLE_REG";
  if (/^(class|grade|std|standard)\b/i.test(v)) return "CLASS";
  if (near(/\b(vid|virtual id)\W*$/)) return "AADHAAR_VID";
  if (near(/aadhaa?r\w*\W*$/)) return "AADHAAR";
  if (near(/(a\/c|acct|account|bank a\/c|savings|current)\W*(no\.?|number|#)?\W*$/)) return "BANK_ACCOUNT";
  if (near(/\bpan\W*(no\.?|number)?\W*$/)) return "PAN";
  if (near(/gstin\W*$/)) return "GSTIN";
  if (near(/passport\W*(no\.?|number)?\W*$/)) return "PASSPORT";
  if (near(/(driving licen[cs]e|\bdl\b|driver'?s licen[cs]e)\W*(no\.?|number)?\W*$/)) return "DRIVING_LICENCE";
  if (near(/voter\W*(id|card)?\W*(no\.?)?\W*$/)) return "VOTER_ID";
  if (near(/(vehicle|registration|reg\.? no)\W*$/)) return "VEHICLE_REG";
  if (near(/\b(uid|user_?id|userid)\W*$/)) return "USER_ID";
  if (near(/(emp_?id|employee\s*id|employee no|staff id)\W*$/)) return "EMPLOYEE_ID";
  if (near(/\bmrn\W*$/)) return "MRN";
  if (near(/(health id|abha)\W*$/)) return "HEALTH_ID";
  if (near(/roll\s*(no\.?|number)?\W*$/)) return "ROLL_NUMBER";
  if (near(/\bupi\W*(id)?\W*$/)) return "UPI_ID";
  if (s.label === "SOCIALNUMBER") return /^\d{3}-\d{2}-\d{4}$/.test(v) ? "SSN" : "NATIONAL_ID";
  if (s.label === "PASSPORT") return "PASSPORT";
  if (s.label === "DRIVERLICENSE") return "DRIVING_LICENCE";
  return s.kind || "ID";
}
