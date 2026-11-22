// Hard release budget: model AND complete shipped runtime must fit in decimal 1 MB.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const limit = 1_000_000;
function bytes(relative) {
  const p = path.join(root, relative), stat = fs.lstatSync(p);
  if (stat.isSymbolicLink()) throw new Error(`size check cannot follow symlink: ${relative}`);
  if (stat.isDirectory()) return fs.readdirSync(p).reduce((sum, name) => sum + bytes(path.join(relative, name)), 0);
  return stat.size;
}
const model = bytes("web/model-general.bin");
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const shippedPaths = new Set(["package.json", "README.md", "LICENSE", ...pkg.files].map(p => p.replace(/\/$/, "")));
for (const p of shippedPaths) {
  if (/[!*?\[\]{}]/.test(p) || !path.resolve(root, p).startsWith(root)) {
    throw new Error(`size check requires a literal path inside the package: ${p}`);
  }
}
const shipped = [...shippedPaths].reduce((sum, p) => sum + bytes(p), 0);
console.log(`SIZE: model ${model} bytes; shipped files ${shipped} bytes; limit ${limit} bytes`);
if (model > limit || shipped > limit) {
  console.error("blur exceeds its 1 MB release budget");
  process.exitCode = 1;
}
