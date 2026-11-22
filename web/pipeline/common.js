// Shared labels, output policy (OPTIONS) and the debug hook.
export const DELIM = /[\s,"':=&?;()<>\[\]{}`]/;

export const NAME_LABELS = new Set(["GIVENNAME", "LASTNAME"]);

export const CANON = { GIVENNAME: "PERSON", LASTNAME: "PERSON", BOD: "DATE_OF_BIRTH", TEL: "PHONE", SOCIALNUMBER: "NATIONAL_ID",
  IDCARD: "NATIONAL_ID", PASS: "PASSWORD", BANK: "BANK_ACCOUNT", SECADDRESS: "ADDRESS", STREET: "ADDRESS", BUILDING: "ADDRESS", POSTCODE: "POSTCODE" };

export const DBG = typeof process !== "undefined" && process.env && process.env.PPDEBUG;

export const dbg = (stage, text, spans) => { if (DBG) console.error(stage.padEnd(10), JSON.stringify(spans.filter(s => !KEEP_LABELS.has(s.label)).map(s => s.label[0] + ":" + text.slice(s.start, s.end)))); return spans; };


// --- one entry point: text in, masked text out (Standard policy keeps event dates, places, organisations, URLs)
export const KEEP_LABELS = new Set(["DATE", "TIME", "CITY", "STATE", "COUNTRY", "BUILDING", "STREET", "SECADDRESS", "URL", "TITLE", "SEX",
  "ORG", "CARD_SHAPE"]);

// opts.numbered: write the fine-grained, numbered tags ([PERSON_1]) instead of the 10 labels (used by the tests that
// check entity linking against numbered answer keys)
// Output policy switches. health: false = health facts are not a label of this product (the neurons stay, for tests and
// for callers that want them: set OPTIONS.health = true)
// dates: true = every date is masked, not only dates of birth (PII_DATES=0 in the environment restores the older policy, which
// the answer keys of the earlier test suites were written for)
export const OPTIONS = { health: false, dates: !(typeof process !== "undefined" && process.env && process.env.PII_DATES === "0") };
