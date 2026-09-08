"""
Classifier wrapper.

Two backends behind one function, `predict(text)`, which always returns
    [{"code": str, "confidence": float}, ...]

  STUB  -- keyword matching. No model needed. Used until Track A delivers,
           and as a fallback if the model fails to load on demo day.
  MODEL -- the fine-tuned DistilBERT multi-label classifier.

Switch by setting USE_MODEL below, or the FIR_USE_MODEL=1 environment
variable. Nothing downstream of this file changes when you switch: that
is the whole point of freezing the API contract before implementation.

INTEGRATION NOTE FOR TRACK A HANDOFF
------------------------------------
Give me a directory containing the saved model and tokenizer
(`model.save_pretrained(dir)` and `tokenizer.save_pretrained(dir)`), plus
the `label_set.json` with the ordered label list. Set MODEL_DIR below.
I do not need your training script.
"""

import json
import os
import re

USE_MODEL = os.environ.get("FIR_USE_MODEL", "0") == "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
LABEL_SET_PATH = os.path.join(MODEL_DIR, "label_set.json")

# Sigmoid threshold for multi-label output. Track A should tune this on the
# dev set -- 0.5 is usually wrong for imbalanced multi-label problems.
THRESHOLD = 0.35
MAX_LENGTH = 256
TOP_K = 4  # cap on sections returned, so the UI stays readable


# ---------------------------------------------------------------------------
# Stub backend
# ---------------------------------------------------------------------------

# Ordered: earlier patterns win ties. Confidences are illustrative and are
# clearly labelled as stub output in the API response.
_KEYWORDS = [
    ("302",  r"\b(murder(ed|ing)?|killed|stabbed to death|shot dead)\b",      0.93),
    ("307",  r"\b(attempt(ed)? to (kill|murder)|tried to kill)\b",            0.88),
    ("376",  r"\b(rape[ds]?|raping|sexual(ly)? assault(ed)?)\b",              0.94),
    ("354",  r"\b(outrage[d]? (her )?modesty|molest(ed|ation)?|inappropriate(ly)? touch)\b", 0.86),
    ("498A", r"\b(dowry|harass(ed|ment) by (her )?(husband|in-laws)|cruelty by husband)\b", 0.89),
    ("304B", r"\b(dowry death|died.{0,30}dowry)\b",                           0.85),
    ("363",  r"\b(kidnap(ped|ping)?|abduct(ed|ion)?)\b",                      0.82),
    ("392",  r"\b(robb(ed|ery)|snatch(ed|ing)|looted)\b",                     0.87),
    ("395",  r"\b(dacoity|gang of.{0,20}robb)\b",                             0.80),
    ("420",  r"\b(cheat(ed|ing)?|fraud(ulently)?|defraud(ed)?|duped|scam)\b", 0.90),
    ("419",  r"\b(imperson(ated|ation)|fake (profile|identity)|posing as)\b", 0.83),
    ("406",  r"\b(breach of trust|misappropriat(ed|ion)|entrusted)\b",        0.81),
    ("468",  r"\b(forg(ed|ery)|fabricated document|false document)\b",        0.84),
    ("471",  r"\b(used.{0,20}forged|submitted.{0,20}fake document)\b",        0.78),
    ("379",  r"\b(theft|stole(n)?|burglar(y|ised)?)\b",                       0.88),
    ("326",  r"\b(acid attack|grievous hurt.{0,20}weapon|attacked with a (knife|rod|weapon))\b", 0.85),
    ("325",  r"\b(grievous(ly)? (hurt|injured)|fracture[d]?)\b",              0.79),
    ("323",  r"\b(beat(en)? up|assault(ed)?|hurt|slapped|punched)\b",         0.76),
    ("506",  r"\b(threat(en(ed|ing))?|intimidat(ed|ion))\b",                  0.80),
    ("447",  r"\b(trespass(ed|ing)?|entered.{0,20}without permission)\b",     0.74),
    ("120B", r"\b(conspir(acy|ed)|in collusion with)\b",                      0.72),
    ("34",   r"\b(along with (his|her|their) associates|common intention|group of (men|persons))\b", 0.70),
]


def _predict_stub(text):
    """Keyword matching. Deterministic, explainable, obviously not a model."""
    lowered = text.lower()
    hits = []
    for code, pattern, conf in _KEYWORDS:
        match = re.search(pattern, lowered)
        if match:
            hits.append({
                "code": code,
                "confidence": conf,
                "_match": match.group(0),
            })

    if not hits:
        return [{"code": "323", "confidence": 0.41, "_match": None}]

    hits.sort(key=lambda h: -h["confidence"])
    return hits[:TOP_K]


def _explain_stub(text, sections):
    """Token weights in the contract's `explanation` shape."""
    out = []
    for s in sections:
        if s.get("_match"):
            for token in str(s["_match"]).split():
                out.append({"token": token, "weight": round(s["confidence"], 2)})
    return out[:12]


# ---------------------------------------------------------------------------
# Model backend
# ---------------------------------------------------------------------------

_model = None
_tokenizer = None
_labels = None


def _load_model():
    """
    Load DistilBERT once, at first use. Loading per request takes several
    seconds and makes the demo look broken.
    """
    global _model, _tokenizer, _labels
    if _model is not None:
        return

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    with open(LABEL_SET_PATH, "r", encoding="utf-8") as f:
        _labels = json.load(f)["labels"]

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    _model.eval()
    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))


def _predict_model(text):
    import torch

    _load_model()
    enc = _tokenizer(
        text, truncation=True, max_length=MAX_LENGTH,
        padding=True, return_tensors="pt",
    )
    with torch.no_grad():
        logits = _model(**enc).logits
    probs = torch.sigmoid(logits)[0].tolist()

    scored = sorted(
        ({"code": _labels[i], "confidence": round(p, 4)}
         for i, p in enumerate(probs)),
        key=lambda d: -d["confidence"],
    )
    above = [s for s in scored if s["confidence"] >= THRESHOLD]

    # Never return nothing: fall back to the single best section so the
    # pipeline always produces a routing decision.
    return (above or scored[:1])[:TOP_K]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def predict(text):
    """Return predicted sections. Falls back to the stub if the model fails."""
    if USE_MODEL:
        try:
            return _predict_model(text)
        except Exception as e:
            print(f"[classifier] model failed ({e}); falling back to stub")
    return _predict_stub(text)


def explain(text, sections):
    """Token-level attributions for the `explanation` field."""
    if USE_MODEL:
        return []  # Track A supplies integrated-gradients output here
    return _explain_stub(text, sections)


def backend_name():
    return "distilbert" if USE_MODEL else "keyword-stub"
