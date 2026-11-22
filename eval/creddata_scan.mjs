// Reproducible, resource-bounded CredData scan. No skipped file is silently scored as scanned.
// node eval/creddata_scan.mjs DATASET MODEL OUTPUT [MAX_CHARS=100000] [SHARD=0] [SHARDS=1]
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { loadModel } from "../web/engine.js";
import { maskStandalone } from "../web/standalone.js";

const [dir, modelPath, output, limitArg = "100000", shardArg = "0", shardsArg = "1"] = process.argv.slice(2);
if (!output) throw new Error("usage: creddata_scan.mjs DATASET MODEL OUTPUT [MAX_CHARS] [SHARD] [SHARDS]");
const limit = Number(limitArg), shard = Number(shardArg), shards = Number(shardsArg);
if (![limit, shard, shards].every(Number.isInteger) || limit < 1 || shards < 1 || shard < 0 || shard >= shards) throw new Error("invalid limits/shard");
// A failed rerun must not inherit a previous run's completion marker.
fs.rmSync(output + ".coverage.json", { force: true });
const modelBytes = fs.readFileSync(modelPath), model = await loadModel(modelBytes);
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const files = [];
function walk(folder) {
  for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
    const p = path.join(folder, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.isFile()) files.push(p);
  }
}
walk(path.join(dir, "data")); files.sort();
const scanned = [], skipped = [], fd = fs.openSync(output, "w"), started = Date.now();
try {
  for (let index = shard; index < files.length; index += shards) {
    const file = path.relative(dir, files[index]), bytes = fs.readFileSync(files[index]), text = bytes.toString("utf8");
    if (text.length > limit) { skipped.push(file); continue; }
    const starts = [0];
    for (let i = 0; i < text.length; i++) if (text[i] === "\n") starts.push(i + 1);
    const lineOf = pos => {
      let lo = 0, hi = starts.length - 1;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (starts[mid] <= pos) lo = mid; else hi = mid - 1; }
      return lo;
    };
    for (const span of maskStandalone(model, text).spans) {
      if (span.label !== "secret") continue;
      for (let line = lineOf(span.start); line <= lineOf(span.end - 1); line++) {
        const start = starts[line], end = starts[line + 1] == null ? text.length : starts[line + 1] - 1;
        const a = Math.max(start, span.start), b = Math.min(end, span.end);
        if (b <= a) continue;
        fs.writeSync(fd, JSON.stringify({ file, line: line + 1,
          start: [...text.slice(start, a)].length, end: [...text.slice(start, b)].length }) + "\n");
      }
    }
    scanned.push({ file, sha256: hash(bytes), characters: [...text].length });
    if (scanned.length % 500 === 0) console.error(`${scanned.length} files, ${Math.round((Date.now() - started) / 1000)} s`);
  }
} finally { fs.closeSync(fd); }
fs.writeFileSync(output + ".coverage.json", JSON.stringify({ modelSha256: hash(modelBytes), limit, shard, shards,
  seconds: (Date.now() - started) / 1000, scanned, skipped }, null, 2) + "\n");
console.log(`Scanned ${scanned.length}; skipped ${skipped.length} files above ${limit} UTF-16 code units`);
