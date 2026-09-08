"""
FIR/Complaint Categorization & Intelligent Routing System
Backend API (Track B).

Routes are deliberately thin: they validate input, call the pipeline, and
shape the response to the frozen contract. All decision logic lives in
scoring.py and routing.py so it can be tested and presented separately.

Run:
    python app.py
"""

import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

import classifier
import db
import routing as routing_engine
import scoring

app = Flask(__name__)
CORS(app)

MAX_INPUT_CHARS = 20000
MIN_INPUT_CHARS = 15


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_complaint(text):
    """
    Full pipeline: classify -> score -> route -> persist.
    Returns the response body defined by the API contract.
    """
    raw_sections = classifier.predict(text)
    codes = [s["code"] for s in raw_sections]

    reference = db.get_sections_by_code(codes)
    severity_lookup = {c: reference[c]["severity_weight"] for c in reference}
    titles = {c: reference[c]["title"] for c in reference}

    sections = [
        {
            "code": s["code"],
            "title": titles.get(s["code"], "Unmapped section"),
            "confidence": round(float(s["confidence"]), 4),
        }
        for s in raw_sections
    ]

    priority = scoring.score_complaint(sections, severity_lookup)
    priority["basis"] = scoring.explain_score(priority, severity_lookup, sections)

    rules = db.get_routing_rules(codes)
    route = routing_engine.route_complaint(sections, rules, titles)

    complaint_id, received_at = db.save_complaint(text, sections, priority, route)

    return {
        "complaint_id": complaint_id,
        "received_at": received_at,
        "sections": sections,
        "priority": priority,
        "routing": route,
        "explanation": classifier.explain(text, raw_sections),
        "model_backend": classifier.backend_name(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_backend": classifier.backend_name(),
        "sections_loaded": len(db.get_sections_by_code(
            [r["code"] for r in _all_section_codes()]
        )),
    })


def _all_section_codes():
    conn = db.get_connection()
    rows = conn.execute("SELECT code FROM ipc_sections").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route("/api/classify", methods=["POST"])
def classify():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("complaint_text") or "").strip()

    if not text:
        return jsonify({"error": "complaint_text is required"}), 400
    if len(text) < MIN_INPUT_CHARS:
        return jsonify({
            "error": f"complaint_text must be at least {MIN_INPUT_CHARS} characters"
        }), 400
    if len(text) > MAX_INPUT_CHARS:
        return jsonify({
            "error": f"complaint_text exceeds {MAX_INPUT_CHARS} characters"
        }), 400

    try:
        return jsonify(process_complaint(text)), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Classification failed. Please try again."}), 500


@app.route("/api/complaints", methods=["GET"])
def complaints():
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50
    return jsonify({"complaints": db.list_complaints(limit)}), 200


@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify(db.get_stats()), 200


@app.route("/api/sections", methods=["GET"])
def sections():
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM ipc_sections ORDER BY severity_weight DESC"
    ).fetchall()
    conn.close()
    return jsonify({"sections": [dict(r) for r in rows]}), 200


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Endpoint not found"}), 404


if __name__ == "__main__":
    created = db.init_db()
    print(f"Database {'created' if created else 'already present'} at {db.DB_PATH}")
    print(f"Classifier backend: {classifier.backend_name()}")
    print("Listening on http://localhost:5000")
    app.run(debug=True, port=5000)
