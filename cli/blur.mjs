#!/usr/bin/env node
// blur: mask personal data and secrets in text (command line, built on the SDK in sdk/index.js).
import fs from "fs";
import { createBlur, LABELS, VERSION } from "../sdk/index.js";

const HELP = `blur ${VERSION}: mask personal data and secrets in text

Usage
  blur [options] [file ...]          read files, or standard input when none (or "-") is given

Output (default: masked text)
  -j, --json            one JSON object per input: {"file", "masked", "spans": [{start, end, label, text}]}
  -s, --spans           one finding per line: label, start, end, text (tab-separated)
  -c, --count           number of findings per label
  -o, --output FILE     write to FILE instead of standard output

Masking
  -p, --pipeline        full pipeline: cross-document name linking (default: the network alone)
  -n, --numbered        numbered placeholders such as [PERSON_1] (implies --pipeline)
      --only LABELS     mask only these labels (comma-separated)
      --keep LABELS     never mask these labels (comma-separated)
      --char C          replace each masked character with C instead of a [label] placeholder

Other
  -m, --model FILE      model file (default: built in, or $BLUR_MODEL)
  -l, --labels          list the output labels
  -v, --version         print the version
  -h, --help            print this help

Labels: ${LABELS.join(", ")}

Examples
  echo "Call Priya on +91 98765 43210" | blur
  blur --json --only secret,private_email logs/*.txt
  blur -n -o masked.txt report.txt
`;

const die = (msg, code = 2) => { process.stderr.write(`blur: ${msg}\n`); process.exit(code); };
const labels = v => v.split(",").map(x => x.trim()).filter(Boolean);

// ---------- arguments
const argv = process.argv.slice(2), opt = { files: [] };
const takesValue = new Set(["-o", "--output", "-m", "--model", "--only", "--keep", "--char"]);
for (let i = 0; i < argv.length; i++) {
  let a = argv[i], val = null;
  if (a.startsWith("--") && a.includes("=")) { val = a.slice(a.indexOf("=") + 1); a = a.slice(0, a.indexOf("=")); }
  if (takesValue.has(a) && val === null) { val = argv[++i]; if (val === undefined) die(`${a} needs a value`); }
  switch (a) {
    case "-h": case "--help": process.stdout.write(HELP); process.exit(0);
    case "-v": case "--version": console.log(VERSION); process.exit(0);
    case "-l": case "--labels": console.log(LABELS.join("\n")); process.exit(0);
    case "-j": case "--json": opt.format = "json"; break;
    case "-s": case "--spans": opt.format = "spans"; break;
    case "-c": case "--count": opt.format = "count"; break;
    case "-p": case "--pipeline": opt.pipeline = true; break;
    case "-n": case "--numbered": opt.numbered = opt.pipeline = true; break;
    case "-o": case "--output": opt.output = val; break;
    case "-m": case "--model": opt.model = val; break;
    case "--only": opt.only = labels(val); break;
    case "--keep": opt.keep = labels(val); break;
    case "--char": opt.char = val; break;
    default:
      if (a !== "-" && a.startsWith("-")) die(`unknown option ${a} (try --help)`);
      opt.files.push(a);
  }
}

// ---------- model: --model, $BLUR_MODEL, the copy built into a binary, or the bundled file
let model = opt.model || process.env.BLUR_MODEL;
if (model) { try { model = fs.readFileSync(model); } catch (e) { die(`cannot read model ${model}: ${e.message}`, 1); } }
else if (globalThis.__BLUR_MODEL_B64) model = Buffer.from(globalThis.__BLUR_MODEL_B64, "base64");

let blur;
try { blur = await createBlur({ model: model || undefined, pipeline: !!opt.pipeline }); }
catch (e) { die(e.message.replace(/^blur: /, ""), 1); }

// ---------- inputs and output
const inputs = [];
for (const f of opt.files.length ? opt.files : ["-"]) {
  try { inputs.push([f, f === "-" ? fs.readFileSync(0, "utf8") : fs.readFileSync(f, "utf8")]); }
  catch (e) { die(`cannot read ${f}: ${e.message}`, 1); }
}
let result = "";
for (const [name, text] of inputs) {
  let r;
  try { r = blur.mask(text, { only: opt.only, keep: opt.keep, numbered: opt.numbered, char: opt.char }); }
  catch (e) { die(e.message.replace(/^blur: /, "")); }
  const prefix = inputs.length > 1 ? name + "\t" : "";
  if (opt.format === "json") result += JSON.stringify({ file: name, masked: r.text, spans: r.spans }) + "\n";
  else if (opt.format === "spans") for (const s of r.spans) result += `${prefix}${s.label}\t${s.start}\t${s.end}\t${JSON.stringify(s.text)}\n`;
  else if (opt.format === "count") {
    const c = {}; for (const s of r.spans) c[s.label] = (c[s.label] || 0) + 1;
    for (const [l, k] of Object.entries(c).sort((a, b) => b[1] - a[1])) result += `${prefix}${l}\t${k}\n`;
  } else result += r.text;
}
if (opt.output) fs.writeFileSync(opt.output, result); else process.stdout.write(result);
