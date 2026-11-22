// The model on its own: run the network, keep the spans of labels that are personal data, and map each network label
// to one of the ten output labels. No rules, no context logic, no post-processing: everything else is in the weights.
// This file plus engine.js (the runtime that evaluates the weights) is the whole product.
const OUT = {
  GIVENNAME: "private_person", LASTNAME: "private_person", PERSON: "private_person", _NAME: "private_person",
  ADDRESS: "private_address", STREET: "private_address", SECADDRESS: "private_address", POSTCODE: "private_address", GEOCOORD: "private_address",
  EMAIL: "private_email", TEL: "private_phone", BOD: "private_date", DATE: "private_date",
  CARD: "account_number", IBAN: "account_number", BANK: "account_number",
  ID: "personal_id", IDCARD: "personal_id", SOCIALNUMBER: "personal_id", PASSPORT: "personal_id", DRIVERLICENSE: "personal_id",
  SECRET: "secret", PASS: "secret", COOKIE: "secret",
  USERNAME: "online_identifier", IP: "online_identifier", MAC: "online_identifier", PROFILE: "online_identifier",
};
export function maskStandalone(model, text) {
  const spans = model.detect(text).filter(s => OUT[s.label]).map(s => ({ start: s.start, end: s.end, label: OUT[s.label], raw: s.label }));
  spans.sort((a, b) => a.start - b.start || b.end - a.end);
  const out = []; let end = 0;
  for (const s of spans) {
    if (s.start < end) continue;
    const last = out[out.length - 1];
    // neighbouring parts of one value ("Morgan" "Vale", a street and its number) become one placeholder
    if (last && last.label === s.label && /^[ \-]?$/.test(text.slice(last.end, s.start))) { last.end = s.end; end = s.end; continue; }
    out.push({ ...s }); end = s.end;
  }
  let masked = "", p = 0;
  for (const s of out) { masked += text.slice(p, s.start) + "[" + s.label + "]"; p = s.end; }
  return { text: masked + text.slice(p), spans: out };
}
