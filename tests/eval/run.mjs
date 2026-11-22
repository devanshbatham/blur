// Check the evaluation protocol's Unicode offsets, exclusions and full-value recall.
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "blur-eval-"));
try {
  const email = "cedar@example.org", prefix = "🙂 mail ", text = prefix + email;
  const entity = { entity_type: "Personal_Email_Address", entity_string: email,
    start: [...prefix].length, end: [...text].length, disclosed: true };
  const rows = [
    { text, axes: { language: "EN" }, entities: [entity] },
    { text, axes: { language: "EN" }, entities: [{ ...entity, disclosed: false }] },
    { text, axes: { language: "EN" }, entities: [{ ...entity, entity_type: "Org_Name" }] },
    { text, axes: { language: "EN" }, entities: [{ ...entity, start: entity.start + 1 }] },
  ];
  const input = path.join(dir, "input.json"), output = path.join(dir, "output.json");
  fs.writeFileSync(input, JSON.stringify(rows));
  const result = spawnSync(process.execPath, [path.join(root, "eval/redact.mjs"), input,
    path.join(root, "web/model-general.bin"), output], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(fs.readFileSync(output));
  assert.equal(report.total.documents, 3);
  assert.equal(report.invalidDocuments, 1);
  assert.equal(report.total.tp, email.length);
  assert.equal(report.total.fp, 0);
  assert.equal(report.total.fn, 0);
  assert.equal(report.total.entities, 1);
  assert.equal(report.total.complete, 1);
  assert.equal(report.total.f1, 1);
  console.log("EVALUATION: Unicode offsets, policy exclusions and invalid annotation handling pass");

  // CredData's Python columns are code points too. Verify known positives,
  // explicit negatives and unlabelled alerts are kept separate by the scorer.
  fs.mkdirSync(path.join(dir, "data")); fs.mkdirSync(path.join(dir, "meta"));
  const credential = "q7Az91pB", linePrefix = '🙂 password = "';
  const content = linePrefix + credential + '"\nThe queue is empty.\npassword = "r8Bx62nC"\n';
  fs.writeFileSync(path.join(dir, "data", "fixture.txt"), content);
  const start = [...linePrefix].length;
  fs.writeFileSync(path.join(dir, "meta", "fixture.csv"),
    "FilePath,LineStart,LineEnd,GroundTruth,ValueStart,ValueEnd\n" +
    `data/fixture.txt,1,1,T,${start},${start + credential.length}\n` +
    "data/fixture.txt,2,2,F,0,19\n");
  const predictions = path.join(dir, "predictions.jsonl"), score = path.join(dir, "score.json");
  const scan = spawnSync(process.execPath, [path.join(root, "eval/creddata_scan.mjs"), dir,
    path.join(root, "web/model-general.bin"), predictions], { encoding: "utf8" });
  assert.equal(scan.status, 0, scan.stderr);
  const scored = spawnSync(process.env.PYTHON || "python3", [path.join(root, "eval/creddata_score.py"),
    dir, predictions, score], { encoding: "utf8" });
  assert.equal(scored.status, 0, scored.stderr);
  const metrics = JSON.parse(fs.readFileSync(score));
  assert.equal(metrics.tp, 1);
  assert.equal(metrics.markedFalsePositives, 0);
  assert.equal(metrics.unlabelledAlerts, 1);
  assert.equal(metrics.fn, 0);
  assert.deepEqual(metrics.completeKnownSingleLineValues, { masked: 1, total: 1, recall: 1 });
  const failedRerun = spawnSync(process.execPath, [path.join(root, "eval/creddata_scan.mjs"), dir,
    path.join(dir, "missing-model.bin"), predictions], { encoding: "utf8" });
  assert.notEqual(failedRerun.status, 0);
  assert.equal(fs.existsSync(predictions + ".coverage.json"), false, "failed reruns must invalidate stale coverage");
  const incomplete = spawnSync(process.env.PYTHON || "python3", [path.join(root, "eval/creddata_score.py"),
    dir, predictions, score], { encoding: "utf8" });
  assert.notEqual(incomplete.status, 0, "an incomplete scan must never produce a score");
  console.log("EVALUATION: CredData columns, coverage and labelled/unlabelled accounting pass");
} finally {
  fs.rmSync(dir, { recursive: true, force: true });
}
