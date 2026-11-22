"""Integration checks for the official-scorer adapter; run on the evaluation host.

python tests/opf/run.py /path/to/pinned/openai/privacy-filter
Requires the same torch/tiktoken environment as eval/opf_score.py.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
official = str(Path(sys.argv[1]).resolve())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    data, pred, report = (folder / name for name in ("data.jsonl", "pred.jsonl", "report.json"))
    text = "🙂 mail cedar@example.org"
    gold = [[7, len(text), "private_email"]]
    rows = [{"index": 0, "id": "unicode", "language": "fixture", "text": text, "gold": gold},
            {"index": 1, "id": "background", "language": "fixture", "text": "Queue status green", "gold": []}]
    data.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    # Same token coverage, wrong category: binary detection stays perfect while
    # typed span matching fails. A separate false alarm must reduce precision.
    predictions = [
        {"index": 0, "id": "unicode", "model": gold, "pipeline": [[7, len(text), "private_person"]]},
        {"index": 1, "id": "background", "model": [], "pipeline": [[0, 5, "private_person"]]},
    ]
    pred.write_text("".join(json.dumps(row) + "\n" for row in predictions))
    marker = Path(str(pred) + ".complete.json")
    manifest = {"shard": 0, "shards": 1, "count": 2, "limit": 0, "modelSha256": "fixture",
                "datasetSha256": digest(data), "predictionsSha256": digest(pred)}
    marker.write_text(json.dumps(manifest))
    cmd = [sys.executable, str(ROOT / "eval/opf_score.py"), official, str(data), str(pred), str(report)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(report.read_text())["results"]
    assert result["model"]["ALL"]["tokenDetection"]["f1"] == 1
    assert result["model"]["ALL"]["typedSpanContainment"]["f1"] == 1
    assert result["pipeline"]["ALL"]["tokenDetection"]["recall"] == 1
    assert 0 < result["pipeline"]["ALL"]["tokenDetection"]["precision"] < 1
    assert result["pipeline"]["ALL"]["typedSpanContainment"]["f1"] == 0
    assert result["model"]["ALL"]["counts"]["documents"] == 2
    manifest["shards"] = 2
    marker.write_text(json.dumps(manifest))
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    assert not report.exists(), "a failed rerun must invalidate its old report"
    manifest["shards"] = 1
    marker.write_text(json.dumps(manifest))
    with pred.open("a") as stream:
        stream.write("\n")
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    print("OPF adapter: Unicode, token-versus-typed-span scoring, false positives, incomplete shards and hash validation passed")
