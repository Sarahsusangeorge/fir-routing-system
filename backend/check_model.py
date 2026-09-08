"""
check_model.py - run this the moment Track A's model lands, before the demo.

Verifies the four things that can silently break integration:
  1. the model folder is complete
  2. the model actually loads and predicts
  3. every label the model can emit exists in the ipc_sections table
  4. the full pipeline produces a sensible priority and routing decision

Run:
    set FIR_USE_MODEL=1        (Windows)
    export FIR_USE_MODEL=1     (Mac/Linux)
    python check_model.py

Failure 3 is the dangerous one. If a predicted section is missing from
ipc_sections it falls back to a default severity of 5, so priority scoring
becomes arbitrary while the screen still looks completely normal.
"""

import json
import os
import sys

import classifier
import db
import routing as routing_engine
import scoring

OK = "  [ok]  "
BAD = "  [!!]  "


def step(n, title):
    print(f"\n{n}. {title}")
    print("   " + "-" * (len(title) + 2))


def main():
    failures = 0

    # ---------------------------------------------------------------- 1
    step(1, "Model folder")
    required = ["config.json", "label_set.json"]
    optional = ["threshold.json"]
    if not os.path.isdir(classifier.MODEL_DIR):
        print(BAD + f"{classifier.MODEL_DIR} does not exist.")
        print("        Unzip Track A's fir_distilbert_model/ to backend/model/")
        return 1

    for f in required:
        p = os.path.join(classifier.MODEL_DIR, f)
        print((OK if os.path.exists(p) else BAD) + f)
        failures += 0 if os.path.exists(p) else 1

    weights = [f for f in os.listdir(classifier.MODEL_DIR)
               if f.endswith((".bin", ".safetensors"))]
    print((OK if weights else BAD) + f"weights: {weights or 'MISSING'}")
    failures += 0 if weights else 1

    for f in optional:
        p = os.path.join(classifier.MODEL_DIR, f)
        if os.path.exists(p):
            with open(p) as fh:
                print(OK + f"{f} -> {json.load(fh)}")
        else:
            print(f"  [--]  {f} absent; using default threshold "
                  f"{classifier.THRESHOLD}")

    if not classifier.USE_MODEL:
        print(BAD + "FIR_USE_MODEL is not set to 1 - still running the stub.")
        failures += 1

    # ---------------------------------------------------------------- 2
    step(2, "Model loads and predicts")
    sample = ("The accused murdered the deceased following a dispute over land "
              "and later threatened the witnesses with dire consequences.")
    try:
        preds = classifier.predict(sample)
        print(OK + f"backend = {classifier.backend_name()}")
        for p in preds:
            print(f"         {p['code']:<8} {p['confidence']:.3f}")
        if classifier.backend_name() != "distilbert":
            print(BAD + "fell back to the stub - check the console for the "
                        "load error above")
            failures += 1
    except Exception as e:
        print(BAD + f"prediction failed: {e}")
        return failures + 1

    # ---------------------------------------------------------------- 3
    step(3, "Label coverage against ipc_sections")
    db.init_db()
    with open(os.path.join(classifier.MODEL_DIR, "label_set.json")) as f:
        raw_labels = json.load(f)["labels"]
    labels = [classifier.normalise_code(l) for l in raw_labels]

    print(f"   model can emit {len(labels)} sections")
    print(f"   raw label example: {raw_labels[0]!r} -> "
          f"normalised {labels[0]!r}")

    known = db.get_sections_by_code(labels)
    missing = [l for l in labels if l not in known]

    print(f"   {len(known)}/{len(labels)} present in ipc_sections")
    if missing:
        print(BAD + f"{len(missing)} sections missing from seed.sql:")
        print("        " + ", ".join(sorted(missing)))
        print("        These fall back to severity 5, which makes their")
        print("        priority scores meaningless. Add them to seed.sql,")
        print("        or confirm they never appear in your demo complaints.")
        failures += 1
    else:
        print(OK + "every predictable section has severity and routing data")

    # ---------------------------------------------------------------- 4
    step(4, "End-to-end pipeline")
    cases = [
        ("murder + threat", sample),
        ("cheating", "The accused, posing as a bank official, fraudulently "
                     "obtained her account details and cheated her of a "
                     "substantial sum."),
        ("precedence", "The complainant states that she was raped by the "
                       "accused, who then threatened her with dire "
                       "consequences if she reported the matter."),
    ]
    from app import process_complaint
    for name, text in cases:
        try:
            r = process_complaint(text)
            codes = ", ".join(s["code"] for s in r["sections"]) or "none"
            print(f"   {name:<16} [{r['priority']['level']:<6} "
                  f"{r['priority']['score']:>4}]  {codes:<22} -> "
                  f"{r['routing']['unit']}")
            print(f"                    explanation tokens: "
                  f"{len(r['explanation'])}")
        except Exception as e:
            print(BAD + f"{name}: {e}")
            failures += 1

    # ---------------------------------------------------------------- done
    print("\n" + "=" * 60)
    if failures:
        print(f"{failures} problem(s) found - fix before the demo.")
    else:
        print("All checks passed. The model is integrated.")
    print("=" * 60)
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
