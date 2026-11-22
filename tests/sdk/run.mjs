// SDK contract: node tests/sdk/run.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createBlur, LABELS, VERSION } from "../../sdk/index.js";

const text = "Hi Priya Sharma, mail priya@example.org, call +91 98765 43210. password: Crimson#Valley2026";
let n = 0;
const ok = (name, fn) => Promise.resolve(fn()).then(() => { n++; }, e => { console.error(`FAIL ${name}: ${e.message}`); process.exitCode = 1; });

const blur = await createBlur();
await ok("labels", () => { assert.equal(LABELS.length, 10); assert.equal(typeof VERSION, "string"); });
await ok("mask", () => assert.equal(blur.mask(text).text, "Hi [private_person], mail [private_email], call [private_phone]. password: [secret]"));
await ok("detect offsets", () => { for (const s of blur.detect(text)) assert.equal(text.slice(s.start, s.end), s.text); });
await ok("detect fields", () => assert.deepEqual(Object.keys(blur.detect(text)[0]).sort(), ["end", "label", "start", "text"]));
await ok("only", () => assert.ok(blur.mask(text, { only: ["secret"] }).spans.every(s => s.label === "secret")));
await ok("keep", () => assert.ok(!blur.mask(text, { keep: ["private_person"] }).spans.some(s => s.label === "private_person")));
await ok("char", () => assert.equal(blur.mask("mail priya@example.org", { char: "*" }).text, "mail *****************"));
await ok("unknown label", () => assert.throws(() => blur.mask(text, { only: ["nope"] }), /unknown label/));
await ok("numbered needs pipeline", () => assert.throws(() => blur.mask(text, { numbered: true }), /pipeline/));
await ok("not a string", () => assert.throws(() => blur.mask(42), /string/));
await ok("empty", () => assert.deepEqual(blur.mask(""), { text: "", spans: [] }));
await ok("model bytes", async () => {
  const b = await createBlur({ model: readFileSync(new URL("../../web/model-general.bin", import.meta.url)) });
  assert.equal(b.mask(text).text, blur.mask(text).text);
});
await ok("pipeline numbered", async () => {
  const p = await createBlur({ pipeline: true });
  assert.match(p.mask(text, { numbered: true }).text, /\[PERSON_1\].*\[EMAIL_1\]/);
});
console.log(`SDK: ${n}/13 checks pass`);
