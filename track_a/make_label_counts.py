#!/usr/bin/env python3
"""
make_label_counts.py -- per-label document counts for Figure 1 (label frequency, long tail).

Uses only the Python standard library, so it runs on a stock Mac/Windows/Linux Python.

    python3 make_label_counts.py --ilsi ~/Downloads/fir_lab/data/ILSI \
                                 --aci  ~/Downloads/fir_lab/data/ACI \
                                 --labels ~/Downloads/results_upload/label_set.json

Writes label_counts_ilsi.csv and label_counts_aci.csv in the current folder.
ILSI: counts of documents containing each KEPT label (the labels in label_set.json, i.e. exactly the K labels the
models were trained on), per released split. ACI: counts per charge name over the released train and test files.
"""
import argparse, csv, json, os
from collections import Counter

ap = argparse.ArgumentParser()
ap.add_argument("--ilsi", default="data/ILSI")
ap.add_argument("--aci", default="data/ACI")
ap.add_argument("--labels", default="label_set.json")
args = ap.parse_args()
P = lambda p: os.path.expanduser(p)

def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

# ---------------- ILSI ----------------
label_path = P(args.labels)
if os.path.exists(label_path):
    kept = json.load(open(label_path))["labels"]
    kept_set = set(kept)
    counts = {s: Counter() for s in ["train", "dev", "test"]}
    docs = {s: 0 for s in counts}
    for split in counts:
        path = os.path.join(P(args.ilsi), split + ".jsonl")
        if not os.path.exists(path):
            raise SystemExit(f"missing {path}")
        for r in read_jsonl(path):
            docs[split] += 1
            for l in set(r["labels"]):
                if l in kept_set:
                    counts[split][l] += 1
    rows = []
    for l in kept:
        tr, dv, te = counts["train"][l], counts["dev"][l], counts["test"][l]
        rows.append((l, tr, dv, te, tr + dv + te))
    rows.sort(key=lambda r: -r[4])
    with open("label_counts_ilsi.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["rank", "label", "train_docs", "dev_docs", "test_docs", "total_docs"])
        for i, r in enumerate(rows, 1):
            wr.writerow([i, *r])
    print(f"ILSI: K = {len(kept)} labels kept; released documents train/dev/test = {docs['train']}/{docs['dev']}/{docs['test']}")
    print("  most frequent:", ", ".join(f"{r[0]} ({r[4]})" for r in rows[:5]))
    print(f"  rarest kept label: {rows[-1][0]} ({rows[-1][4]} documents)")
    print("  wrote label_counts_ilsi.csv")
else:
    print(f"(skipped ILSI: {label_path} not found)")

# ---------------- ACI ----------------
tr_path = os.path.join(P(args.aci), "Train-Sent.jsonl")
te_path = os.path.join(P(args.aci), "Test-Doc.jsonl")
if os.path.exists(tr_path) and os.path.exists(te_path):
    ctr, cte = Counter(), Counter()
    ntr = nte = 0
    for r in read_jsonl(tr_path):
        ntr += 1
        ctr.update(set(r.get("doc_labels", [])))
    for r in read_jsonl(te_path):
        nte += 1
        cte.update(set(r.get("doc_labels", [])))
    names = sorted(set(ctr) | set(cte), key=lambda l: -(ctr[l] + cte[l]))
    with open("label_counts_aci.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["rank", "label", "train_file_docs", "test_docs", "total_docs"])
        for i, l in enumerate(names, 1):
            wr.writerow([i, l, ctr[l], cte[l], ctr[l] + cte[l]])
    print(f"ACI: {len(names)} charge names; train file {ntr} docs, test file {nte} docs")
    print("  most frequent:", ", ".join(f"{l} ({ctr[l] + cte[l]})" for l in names[:5]))
    print("  wrote label_counts_aci.csv")
else:
    print(f"(skipped ACI: files not found in {P(args.aci)})")
