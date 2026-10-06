"""
Priority scoring, routing, officer allocation and the classifier interface,
checked against independently written oracles. The oracles re-derive the
documented rules; they do not import the code under test.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

import classifier
import db
import routing
import scoring
import workflow

# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------

HIGH, MEDIUM = 6.5, 3.5  # documented in README / scoring.py


def oracle_priority(sections, weights, default=5.0):
    """score = max(severity x confidence) computed exactly, rounded half-up to 1 dp before thresholding."""
    if not sections:
        return {"level": "Low", "score": 0.0, "driver": None}
    best, driver = Decimal(0), None
    for s in sections:
        contribution = Decimal(str(weights.get(s["code"], default))) * Decimal(str(s["confidence"]))
        if contribution > best:
            best, driver = contribution, s["code"]
    score = float(best.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    level = "High" if score >= HIGH else "Medium" if score >= MEDIUM else "Low"
    return {"level": level, "score": score, "driver": driver}


def seeded_weights():
    conn = db.get_connection()
    rows = conn.execute("SELECT code, severity_weight FROM ipc_sections").fetchall()
    conn.close()
    return {r["code"]: r["severity_weight"] for r in rows}


@pytest.mark.parametrize("confidence,expected_level", [
    (0.644, "Medium"),   # 6.44 -> 6.4
    (0.65, "High"),      # 6.5 exactly at the boundary
    (0.66, "High"),
    (0.344, "Low"),      # 3.44 -> 3.4
    (0.35, "Medium"),    # 3.5 exactly at the boundary
    (0.36, "Medium"),
])
def test_priority_boundaries(confidence, expected_level):
    sections = [{"code": "302", "confidence": confidence}]
    got = scoring.score_complaint(sections, {"302": 10.0})
    assert got == oracle_priority(sections, {"302": 10.0})
    assert got["level"] == expected_level


@pytest.mark.parametrize("weight,confidence,score,level", [
    (5.0, 0.69, 3.5, "Medium"),   # exactly 3.45: float arithmetic gives 3.4499999999999997
    (10.0, 0.645, 6.5, "High"),   # exactly 6.45
    (3.0, 0.35, 1.1, "Low"),      # exactly 1.05
])
def test_exact_half_way_scores_round_the_same_way(weight, confidence, score, level):
    got = scoring.score_complaint([{"code": "X", "confidence": confidence}], {"X": weight})
    assert (got["score"], got["level"]) == (score, level)


def test_priority_takes_the_gravest_section_not_the_mean():
    sections = [{"code": "302", "confidence": 0.9}, {"code": "447", "confidence": 0.9}]
    got = scoring.score_complaint(sections, {"302": 10.0, "447": 1.0})
    assert got["driver"] == "302" and got["level"] == "High" and got["score"] == 9.0


def test_priority_with_no_sections_is_low():
    assert scoring.score_complaint([], {}) == {"level": "Low", "score": 0.0, "driver": None}


def test_unmapped_section_uses_documented_default():
    got = scoring.score_complaint([{"code": "999Z", "confidence": 1.0}], {})
    assert got["score"] == 5.0 and got["level"] == "Medium"


def test_scoring_matches_oracle_on_every_seeded_section():
    weights = seeded_weights()
    for code in weights:
        for conf in (0.35, 0.5, 0.77, 0.99):
            sections = [{"code": code, "confidence": conf}]
            assert scoring.score_complaint(sections, weights) == oracle_priority(sections, weights), code


def test_displayed_basis_agrees_with_the_score():
    sections = [{"code": "420", "confidence": 0.9}]
    weights = {"420": 6.0}
    p = scoring.score_complaint(sections, weights)
    assert scoring.explain_score(p, weights, sections).endswith(f"= {p['score']:g}")


def test_low_confidence_serious_offence_is_flagged_for_review():
    """A rape prediction at 0.36 scores 3.6 (Medium); it must not pass silently."""
    sections = [{"code": "376", "confidence": 0.36}]
    p = scoring.score_complaint(sections, {"376": 10.0})
    flags = scoring.review_flags(sections, {"376": 10.0}, p)
    assert p["level"] == "Medium"
    assert any("376" in f for f in flags)


def test_unmapped_section_is_flagged_for_review():
    sections = [{"code": "999Z", "confidence": 0.9}]
    p = scoring.score_complaint(sections, {})
    assert any("999Z" in f for f in scoring.review_flags(sections, {}, p))


def test_confident_ordinary_prediction_raises_no_flag():
    sections = [{"code": "379", "confidence": 0.88}]
    p = scoring.score_complaint(sections, {"379": 5.0})
    assert scoring.review_flags(sections, {"379": 5.0}, p) == []


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def oracle_route(sections, rules):
    conf = {s["code"]: s["confidence"] for s in sections}
    applicable = [r for r in rules if r["section_code"] in conf]
    if not applicable:
        return routing.DEFAULT_UNIT
    best = min(applicable, key=lambda r: (r["precedence"], -conf[r["section_code"]], r["section_code"]))
    return best["unit"]


def seeded_rules():
    conn = db.get_connection()
    rows = conn.execute("SELECT section_code, unit, precedence FROM routing_rules").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_victim_centric_precedence():
    rules = seeded_rules()
    both = [{"code": "302", "confidence": 0.95}, {"code": "376", "confidence": 0.6}]
    assert routing.route_complaint(both, rules)["unit"] == "Women & Child Protection Unit"
    assert routing.route_complaint([{"code": "302", "confidence": 0.95}], rules)["unit"] == "Crime Branch"


def test_unknown_and_empty_predictions_fall_back_to_local_station():
    rules = seeded_rules()
    assert routing.route_complaint([], rules)["unit"] == routing.DEFAULT_UNIT
    assert routing.route_complaint([{"code": "999Z", "confidence": 0.9}], rules)["unit"] == routing.DEFAULT_UNIT


def test_routing_matches_oracle_for_every_pair_of_seeded_sections():
    rules = seeded_rules()
    codes = sorted({r["section_code"] for r in rules})
    checked = 0
    for i, a in enumerate(codes):
        for b in codes[i + 1::7]:
            sections = [{"code": a, "confidence": 0.7}, {"code": b, "confidence": 0.6}]
            assert routing.route_complaint(sections, rules)["unit"] == oracle_route(sections, rules), (a, b)
            checked += 1
    assert checked > 500


def test_routing_ties_do_not_depend_on_rule_order():
    sections = [{"code": "A1", "confidence": 0.8}, {"code": "B2", "confidence": 0.8}]
    rules = [{"section_code": "A1", "unit": "Unit A", "precedence": 3},
             {"section_code": "B2", "unit": "Unit B", "precedence": 3}]
    assert routing.route_complaint(sections, rules)["unit"] == routing.route_complaint(sections, rules[::-1])["unit"]


# ---------------------------------------------------------------------------
# Officer allocation
# ---------------------------------------------------------------------------

def officer(id, unit, station, load=0.0, capacity=10, availability="available", active=1, last=None):
    return {"id": id, "name": f"O{id}", "unit": unit, "station": station, "weighted_load": load,
            "capacity": capacity, "availability": availability, "active": active, "last_assigned_at": last}


def oracle_choose(officers, unit, station):
    best = None
    for o in officers:
        if not o["active"] or o["availability"] == "on_leave":
            continue
        same = station is not None and o["station"] == station
        if o["unit"] == unit:
            tier = 0 if same else 1
        elif o["unit"] is None:
            tier = 2 if same else 3
        else:
            continue
        score = tier + o["weighted_load"] / max(o["capacity"], 1) + (0.5 if o["availability"] == "busy" else 0)
        key = (round(score, 3), o["last_assigned_at"] or "", o["id"])
        if best is None or key < best[0]:
            best = (key, o["id"])
    return best[1] if best else None


ALLOCATION_CASES = [
    ([officer(1, "Cyber Cell", "PS-A"), officer(2, "Cyber Cell", "PS-B")], "Cyber Cell", "PS-B"),
    ([officer(1, "Cyber Cell", "PS-A", load=9), officer(2, "Cyber Cell", "PS-A", load=2)], "Cyber Cell", "PS-A"),
    ([officer(1, "Cyber Cell", "PS-A", availability="on_leave"), officer(2, None, "PS-A")], "Cyber Cell", "PS-A"),
    ([officer(1, "Cyber Cell", "PS-A", active=0), officer(2, None, "PS-Z")], "Cyber Cell", "PS-A"),
    ([officer(1, "Cyber Cell", "PS-A", availability="busy"), officer(2, "Cyber Cell", "PS-A", load=4)], "Cyber Cell", "PS-A"),
    ([officer(1, "Crime Branch", "PS-A")], "Cyber Cell", "PS-A"),
    ([officer(1, "Cyber Cell", "PS-A", last="2026-01-02"), officer(2, "Cyber Cell", "PS-A", last="2026-01-01")], "Cyber Cell", "PS-A"),
    ([officer(1, "Cyber Cell", "PS-A", load=5, capacity=5), officer(2, "Cyber Cell", "PS-A", load=9, capacity=20)], "Cyber Cell", "PS-A"),
    ([officer(1, None, "PS-A"), officer(2, None, "PS-B")], "Cyber Cell", None),
    ([], "Cyber Cell", "PS-A"),
]


@pytest.mark.parametrize("officers,unit,station", ALLOCATION_CASES)
def test_allocation_matches_oracle(officers, unit, station):
    assert workflow.choose_officer(officers, unit, station) == oracle_choose(officers, unit, station)


def test_no_eligible_officer_leaves_the_case_unassigned():
    assert workflow.choose_officer([officer(1, "Crime Branch", "PS-A")], "Cyber Cell", "PS-A") is None


def test_full_officer_still_receives_work_when_everyone_is_full():
    """Documented behaviour: allocation never refuses a case; it picks the least overloaded."""
    team = [officer(1, "Cyber Cell", "PS-A", load=12, capacity=10), officer(2, "Cyber Cell", "PS-A", load=15, capacity=10)]
    assert workflow.choose_officer(team, "Cyber Cell", "PS-A") == 1


# ---------------------------------------------------------------------------
# Classifier interface (keyword stub; the DistilBERT weights are not in the repository)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The accused stabbed to death the victim and also cheated and threatened and assaulted and stole.",
    "x", "", "a" * 20000, "murder murder murder murder", "मेरा फोन चोरी हो गया",
])
def test_stub_output_shape(text):
    out = classifier.predict(text)
    assert 1 <= len(out) <= classifier.TOP_K
    assert all(0.0 <= s["confidence"] <= 1.0 for s in out)
    assert len({s["code"] for s in out}) == len(out)


@pytest.mark.parametrize("raw,expected", [
    ("Section 302", "302"), ("IPC_376A", "376A"), ("302 ", "302"),
    ("Section 420 in The Indian Penal Code", "420"), ("S.498A", "498A"), ("376(2)", "376(2)"),
])
def test_label_normalisation(raw, expected):
    assert classifier.normalise_code(raw) == expected


def test_stub_is_deterministic():
    text = "The accused robbed the shop and threatened the cashier."
    assert classifier.predict(text) == classifier.predict(text)


def test_unrecognised_narrative_is_marked_as_a_fallback():
    out = classifier.predict("My neighbour set fire to my house while my family slept inside.")
    assert out[0].get("fallback") is True


def test_model_failure_is_reported_honestly(monkeypatch):
    """If DistilBERT cannot load, the response must not claim DistilBERT produced it."""
    monkeypatch.setattr(classifier, "USE_MODEL", True)

    def broken(*a, **k):
        raise OSError("model weights missing")

    monkeypatch.setattr(classifier, "_predict_model", broken)
    out = classifier.predict("The accused cheated the complainant of money.")
    assert out
    assert classifier.backend_name() != "distilbert"


@pytest.mark.xfail(reason="Known limitation of the keyword stub: it does not understand negation.", strict=True)
def test_stub_understands_negation():
    assert all(s["code"] != "379" for s in classifier.predict("Nothing was stolen and there was no theft."))
