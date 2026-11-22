// Build a single-file `blur` executable with the model embedded:  node tools/build_binary.mjs [--target bun-linux-x64]
// Needs Bun (https://bun.sh). Output: dist/blur (or dist/blur.exe for Windows targets).
import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";
import { fileURLToPath } from "url";
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const target = process.argv.includes("--target") ? process.argv[process.argv.indexOf("--target") + 1] : null;
const dist = path.join(root, "dist");
fs.mkdirSync(dist, { recursive: true });
const model = fs.readFileSync(path.join(root, "web", "model-general.bin")).toString("base64");
const entry = path.join(dist, ".entry.mjs");
fs.writeFileSync(entry, `globalThis.__BLUR_MODEL_B64 = ${JSON.stringify(model)};\nawait import("../cli/blur.mjs");\n`);
const out = path.join(dist, target && target.includes("windows") ? "blur.exe" : "blur");
execFileSync("bun", ["build", "--compile", "--minify", entry, "--outfile", out, ...(target ? ["--target", target] : [])], { stdio: "inherit", cwd: root });
fs.rmSync(entry);
console.log(`built ${path.relative(root, out)} (${(fs.statSync(out).size / 1e6).toFixed(1)} MB)`);
