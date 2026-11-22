// Contrastive syntax tests: the same token as a symbol and as a credential.
// All values are invented. Both execution modes must satisfy the same contract.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { loadModel } from "../../web/engine.js";
import { maskStandalone } from "../../web/standalone.js";
import { maskText } from "../../web/postprocess.js";

const model = await loadModel(readFileSync(process.argv[2] || new URL("../../web/model-general.bin", import.meta.url)));
const cases = [];
const add = (text, mask = [], keep = []) => cases.push({ text, mask, keep });
const tokens = ["q7Az91pB", "r8Bx62nC", "s9Cy73mD", "t6Dz84kE"];
for (const value of tokens) {
  for (const prefix of ["var", "let", "const"]) {
    for (const space of [" ", "\t", "   "]) {
      add(`${prefix}${space}${value} = 0;`, [], [value]);
      add(`${prefix}${space}password = "${value}";`, [value]);
    }
  }
  for (const prefix of ["function", "def"]) add(`${prefix} ${value}(argument) {}`, [], [value]);
  for (const prefix of ["class", "struct", "enum", "interface", "namespace"]) add(`${prefix} ${value} {}`, [], [value]);
  add(`import ${value} from "module";`, [], [value]);
  add(`type ${value} = string;`, [], [value]);
  add(`password: ${value}`, [value]);
  add(`{"password":"${value}"}`, [value]);
}
// A secret cue on one line must not turn an unrelated number on the next into a PIN.
for (const newline of ["\n", "\r\n"]) {
  add(`PIN policy${newline}The buffer size is 864209`, [], ["864209"]);
  add(`pw policy${newline}the identifier is abcdef9274`, [], ["abcdef9274"]);
  add(`PIN is 864209`, ["864209"]);
}
// Quoting makes the complete value explicit, even when it resembles prose or code.
for (const value of ["Moon River Lantern 2846", "this is a valid long passphrase", "correct-horse-battery-staple",
  "cedar.brook.lantern", "Raven()Garden9", "Maple_Grove_Lantern", "m4ple;grove", "oak#tree=branch"]) {
  for (const text of [`password = "${value}"`, `{"password":"${value}"}`, `passphrase = '${value}'`]) {
    add(text, [value]);
  }
}
for (const key of ["password_help", "password_label", "password_hint", "password_placeholder"]) {
  add(`{"${key}":"Enter your current password"}`, [], ["Enter your current password"]);
}
for (const value of tokens) {
  add(`const password = ${value};`, [], [value]);
  add(`const password = "${value}";`, [value]);
  add(`PASSWORD=${value}`, [value]);
}
add("Tensor<[XY_Float64, AB_Integer32]>", [], ["XY_Float64", "AB_Integer32"]);
add('password = "XY_Float64"', ["XY_Float64"]);
for (const key of ["api_key", "consumer_key", "access_key", "signing_key"]) {
  add(`${key} = "zvqmrptl_kxb"`, ["zvqmrptl_kxb"]);
}
for (const count of [1, 3, 5, 7]) {
  const value = "cedar" + "\\".repeat(count) + '"brook9274';
  add(`password = "${value}"`, [value]);
}
for (const count of [2, 4, 6, 8]) {
  const value = "cedar9274" + "\\".repeat(count);
  add(`password = "${value}"; ordinary text follows`, [value], ["ordinary text follows"]);
}
for (const key of ["database_password", "service_api_key"]) {
  for (const fields of ["", "  type = string\n  sensitive = true\n"]) {
    const value = "zvqmrptl_kxb9274";
    add(`variable "${key}" {\n${fields}  default = "${value}"\n}\nvariable "display_label" {\n  default = "ordinary text"\n}`,
      [value], ["ordinary text"]);
  }
}

let failed = 0;
for (const [mode, run] of [["model", maskStandalone], ["pipeline", maskText]]) {
  let passed = 0;
  for (const { text, mask, keep } of cases) {
    const spans = run(model, text).spans.filter(s => s.label === "secret" || s.tag10 === "[secret]");
    try {
      for (const value of [...mask, ...keep]) assert.ok(text.includes(value), `invalid fixture ${value}`);
      for (const value of mask) {
        const start = text.indexOf(value);
        for (let i = start; i < start + value.length; i++) {
          if (!/\s/.test(text[i])) assert.ok(spans.some(s => s.start <= i && i < s.end), `leaked byte ${i}`);
        }
      }
      for (const value of keep) {
        const start = text.indexOf(value);
        assert.ok(!spans.some(s => s.start < start + value.length && start < s.end), `masked ${value}`);
      }
      passed++;
    } catch (error) {
      failed++;
      console.error(`${mode}: ${error.message}: ${JSON.stringify(text)}`);
    }
  }
  console.log(`SECRET CONTEXT ${mode}: ${passed}/${cases.length}`);
}
if (failed) process.exitCode = 1;
