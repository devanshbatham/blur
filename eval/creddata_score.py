"""Score only manifest-covered files, with unlabelled alerts reported separately.

python3 eval/creddata_score.py DATASET PREDICTIONS_GLOB OUTPUT.json
Each predictions file must have a completed .coverage.json sidecar.
The conservative line F1 counts unlabelled alerts as FP, matching the historical
blur comparison. They are not independently verified false positives.
"""
import collections
import csv
import glob
import hashlib
import json
import sys
from pathlib import Path


def prf(tp, fp, fn):
    p, r = tp / (tp + fp or 1), tp / (tp + fn or 1)
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r or 1)}


def main():
    dataset, pattern, output = sys.argv[1:]
    files, predicted, hashes, shards, limits = {}, collections.defaultdict(list), set(), set(), set()
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise ValueError("no prediction files")
    expected_shards = None
    for path in paths:
        coverage = json.loads(Path(path + ".coverage.json").read_text())
        hashes.add(coverage["modelSha256"])
        limits.add(coverage["limit"])
        shard = coverage["shard"]
        if shard in shards:
            raise ValueError("duplicate shard")
        shards.add(shard)
        if expected_shards is not None and expected_shards != coverage["shards"]:
            raise ValueError("incompatible shard counts")
        expected_shards = coverage["shards"]
        for f in coverage["scanned"]:
            if f["file"] in files:
                raise ValueError("duplicate file")
            files[f["file"]] = f
        for line in Path(path).read_text().splitlines():
            pred = json.loads(line)
            if pred["file"] not in files:
                raise ValueError("prediction outside completed coverage")
            predicted[pred["file"], pred["line"]].append((pred["start"], pred["end"]))
    if len(hashes) != 1 or len(limits) != 1 or shards != set(range(expected_shards)):
        raise ValueError("mixed models/limits or incomplete scan")
    positive, negative, values = set(), set(), set()
    annotation_hash = hashlib.sha256()
    for path in sorted((Path(dataset) / "meta").glob("*.csv")):
        annotation_hash.update(path.name.encode())
        annotation_hash.update(path.read_bytes())
        with path.open() as stream:
            for row in csv.DictReader(stream):
                if row["FilePath"] not in files:
                    continue
                start, end = int(row["LineStart"]), int(row["LineEnd"])
                keys = {(row["FilePath"], line) for line in range(start, end + 1)}
                if row["GroundTruth"] == "T":
                    positive.update(keys)
                    a, b = row["ValueStart"], row["ValueEnd"]
                    if start == end and a not in ("", "-1") and b not in ("", "-1") and int(b) > int(a):
                        values.add((row["FilePath"], start, int(a), int(b)))
                elif row["GroundTruth"] == "F":
                    negative.update(keys)
    negative -= positive
    hits = set(predicted)
    tp, marked_fp, unknown = len(hits & positive), len(hits & negative), len(hits - positive - negative)
    complete = 0
    for f, line, start, end in values:
        cursor = start
        for a, b in sorted(predicted.get((f, line), [])):
            if a > cursor:
                break
            cursor = max(cursor, b)
        complete += cursor >= end
    manifest_hash = hashlib.sha256(json.dumps(sorted((f, d["sha256"]) for f, d in files.items())).encode()).hexdigest()
    report = {"modelSha256": next(iter(hashes)), "coverageSha256": manifest_hash,
              "annotationSha256": annotation_hash.hexdigest(), "maxFileUTF16Units": next(iter(limits)), "files": len(files),
              "characters": sum(f["characters"] for f in files.values()), "positiveLines": len(positive),
              "negativeLines": len(negative), "tp": tp, "markedFalsePositives": marked_fp,
              "unlabelledAlerts": unknown, "fn": len(positive) - tp,
              "conservativeLine": prf(tp, marked_fp + unknown, len(positive) - tp),
              "labelledLine": prf(tp, marked_fp, len(positive) - tp),
              "completeKnownSingleLineValues": {"masked": complete, "total": len(values), "recall": complete / (len(values) or 1)}}
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
