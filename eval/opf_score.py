"""Score frozen Blur spans through the pinned, unmodified official OPF scorer.

python opf_score.py OFFICIAL_REPO DATA.jsonl PREDICTIONS_GLOB OUTPUT.json
Requires torch and tiktoken on the remote evaluation machine. No example text
or per-example errors are printed. Published gold cleanup is NOT reconstructed.
"""
import collections
import glob
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import torch
import tiktoken

OFFICIAL_COMMIT = "f7f00ca7fb869683eb732c010299d901457f19c3"


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metric(p_num, p_den, r_num, r_den):
    p, r = p_num / (p_den or 1), r_num / (r_den or 1)
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r or 1)}


def main():
    official, data, pattern, output = sys.argv[1:]
    Path(output).unlink(missing_ok=True)
    commit = subprocess.check_output(["git", "-C", official, "rev-parse", "HEAD"], text=True).strip()
    if commit != OFFICIAL_COMMIT or subprocess.check_output(["git", "-C", official, "status", "--porcelain"], text=True).strip():
        raise ValueError("official evaluator must be the pinned, unmodified checkout")
    sys.path.insert(0, official)
    from opf._common.label_space import BACKGROUND_CLASS_LABEL, NER_CLASS_NAMES_BY_CATEGORY_VERSION
    from opf._core.sequence_labeling import build_label_info
    from opf._core.spans import labels_to_spans, token_spans_to_char_spans, trim_char_spans_whitespace
    from opf._eval.preprocess import NamedEntity, labels_from_entities, token_char_ranges
    from opf._eval.metrics import compute_metrics

    torch.set_num_threads(1)
    encoding = tiktoken.get_encoding("o200k_base")
    classes = NER_CLASS_NAMES_BY_CATEGORY_VERSION["v2"]
    info = build_label_info(classes)
    dataset_hash = file_hash(data)
    predictions, manifests, shard_ids = {}, [], set()
    for path in sorted(glob.glob(pattern)):
        manifest = json.loads(Path(path + ".complete.json").read_text())
        if manifest["limit"] or manifest["datasetSha256"] != dataset_hash or manifest["predictionsSha256"] != file_hash(path):
            raise ValueError("partial, different-dataset or modified predictions")
        if manifest["shard"] in shard_ids:
            raise ValueError("duplicate shard")
        shard_ids.add(manifest["shard"])
        rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
        if len(rows) != manifest["count"]:
            raise ValueError("prediction count mismatch")
        for row in rows:
            if row["index"] in predictions or row["index"] % manifest["shards"] != manifest["shard"]:
                raise ValueError("duplicate or misassigned prediction")
            predictions[row["index"]] = row
        manifests.append(manifest)
    if not manifests or len({m["shards"] for m in manifests}) != 1 or shard_ids != set(range(manifests[0]["shards"])) or len({m["modelSha256"] for m in manifests}) != 1:
        raise ValueError("incomplete shards or mixed models")

    totals = {mode: collections.defaultdict(collections.Counter) for mode in ("model", "pipeline")}
    batches = collections.defaultdict(list)
    started = time.monotonic()
    seen = set()

    def flush(language):
        batch = batches[language]
        if not batch:
            return
        for mode in totals:
            examples, texts, offsets = {}, {}, {}
            gold_positive = pred_positive = gold_spans = pred_spans = 0
            for row, tokens, ranges, gold in batch:
                key = str(row["index"])
                entities = [NamedEntity(a, b, label) for a, b, label in predictions[row["index"]][mode]]
                pred = labels_from_entities(tokens, row["text"], entities, info, encoding, token_char_ranges_hint=ranges)
                scores = torch.nn.functional.one_hot(torch.tensor(pred), len(classes)).to(torch.float32)
                examples[key] = SimpleNamespace(length=len(tokens), token_ids=tuple(tokens), score_matrix=scores, labels=torch.tensor(gold))
                texts[key], offsets[key] = row["text"], ranges
                gold_positive += sum(label != info.background_token_label for label in gold)
                pred_positive += sum(label != info.background_token_label for label in pred)
                def span_count(labels):
                    spans = labels_to_spans(dict(enumerate(labels)), info)
                    return len(trim_char_spans_whitespace(token_spans_to_char_spans(spans, *ranges), row["text"]))
                gold_spans += span_count(gold)
                pred_spans += span_count(pred)
            metrics, _, _ = compute_metrics(examples, info, decoder=None, example_texts=texts, encoding=encoding,
                span_metrics_space="char", trim_span_whitespace=True,
                discard_overlapping_predicted_spans=False, discard_overlapping_ground_truth_spans=False,
                ner_class_names=classes, background_class_label=BACKGROUND_CLASS_LABEL,
                token_char_ranges_fn=token_char_ranges, token_char_ranges_by_example=offsets)
            tp = round(metrics.get("detection.precision", 0) * pred_positive)
            if tp != round(metrics.get("detection.recall", 0) * gold_positive):
                raise ValueError("official token metric aggregation mismatch")
            counts = {"documents": len(batch), "tokens": round(metrics["n_tokens"]), "tp": tp,
                      "fp": pred_positive - tp, "fn": gold_positive - tp,
                      "predictedSpans": pred_spans, "goldSpans": gold_spans,
                      "precisionMatchedSpans": round(metrics.get("detection.span.precision", 0) * pred_spans),
                      "recallMatchedSpans": round(metrics.get("detection.span.recall", 0) * gold_spans)}
            for group in (language, "ALL"):
                totals[mode][group].update(counts)
        batch.clear()

    with Path(data).open() as stream:
        for line in stream:
            row = json.loads(line)
            index = row["index"]
            if index in seen or index not in predictions or predictions[index]["id"] != row["id"]:
                raise ValueError("missing, duplicate or mismatched example")
            seen.add(index)
            tokens = encoding.encode(row["text"], allowed_special="all")
            ranges = token_char_ranges(tokens, encoding, row["text"])
            entities = [NamedEntity(a, b, label) for a, b, label in row["gold"]]
            gold = labels_from_entities(tokens, row["text"], entities, info, encoding, token_char_ranges_hint=ranges)
            batch = batches[row["language"]]
            batch.append((row, tokens, ranges, gold))
            if len(batch) >= 256:
                flush(row["language"])
            if len(seen) % 5000 == 0:
                print(json.dumps({"scored": len(seen), "seconds": round(time.monotonic() - started, 1)}), flush=True)
    for language in batches:
        flush(language)
    if seen != set(predictions):
        raise ValueError("predictions outside dataset")
    report = {}
    for mode, groups in totals.items():
        report[mode] = {}
        for language, c in groups.items():
            report[mode][language] = {"counts": dict(c),
                "tokenDetection": metric(c["tp"], c["tp"] + c["fp"], c["tp"], c["tp"] + c["fn"]),
                "typedSpanContainment": metric(c["precisionMatchedSpans"], c["predictedSpans"], c["recallMatchedSpans"], c["goldSpans"])}
    result = {"protocol": "Public, uncorrected holdout; model-card category map; unmodified official OPF token detection and typed containment span scorer; not an exact reproduction of published baseline or corrected scores.",
              "officialCommit": commit, "datasetSha256": dataset_hash, "modelSha256": manifests[0]["modelSha256"],
              "encoding": encoding.name, "scoringSeconds": time.monotonic() - started,
              "versions": {"torch": torch.__version__, "tiktoken": tiktoken.__version__},
              "predictionManifests": manifests, "results": report,
              "limitations": ["OpenAI's rule-based gold cleanup and adjudicated exclusions were not available.",
                  "The public scorer uses binary token detection and directional span containment; span scores are not exact-boundary match scores.",
                  "Blur spans are projected onto OPF tokens with the official gold-span projection; deterministic hard labels are supplied to the scorer. Synthetic loss and token accuracy are not reported.",
                  "Published OpenAI scores are reference numbers, not a paired run on these uncorrected labels."]}
    Path(output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({mode: values["ALL"] for mode, values in report.items()}))


if __name__ == "__main__":
    main()
