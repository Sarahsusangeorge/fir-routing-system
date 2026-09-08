# Backend — FIR Categorization & Intelligent Routing

Track B. Flask API, priority scoring, routing engine, SQLite persistence.

---

## Run it

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
python seed_demo.py      # creates the database and loads 15 demo complaints
python app.py            # starts on http://localhost:5000
```

Check it works:

```bash
curl http://localhost:5000/api/health
```

If SQLite ever gets into a bad state, delete `fir_system.db` and re-run
`seed_demo.py`. It rebuilds from `schema.sql` and `seed.sql` in seconds.

---

## API

Frozen contract. Do not change any field name without announcing it.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/classify` | Classify, score, route and store a complaint |
| GET | `/api/complaints?limit=50` | Complaint history, highest priority first |
| GET | `/api/stats` | Counts by priority and by unit |
| GET | `/api/sections` | IPC reference table |
| GET | `/api/health` | Backend status and active classifier |

### POST /api/classify

Request:
```json
{ "complaint_text": "The accused fraudulently induced..." }
```

Response 200:
```json
{
  "complaint_id": 16,
  "received_at": "2026-09-08 19:04:11",
  "sections": [
    { "code": "420", "title": "Cheating and dishonestly inducing delivery of property", "confidence": 0.9 }
  ],
  "priority": {
    "level": "Medium",
    "score": 5.4,
    "driver": "420",
    "basis": "Driven by Section 420: severity 6 x confidence 0.90 = 5.4"
  },
  "routing": {
    "unit": "Economic Offences Wing",
    "reason": "Section 420 (Cheating...) is handled by Economic Offences Wing.",
    "matched_section": "420"
  },
  "explanation": [ { "token": "fraudulently", "weight": 0.9 } ],
  "model_backend": "keyword-stub"
}
```

Errors return `{"error": "..."}` with status 400 (bad input) or 500
(pipeline failure). The API never returns a stack trace.

---

## Switching from stub to the real model

The API ships with a keyword-matching stub so the pipeline works before
Track A delivers. Swapping in DistilBERT changes nothing downstream —
that is the payoff for freezing the contract first.

1. Get from Track A a folder containing `model.save_pretrained(...)` and
   `tokenizer.save_pretrained(...)` output, plus `label_set.json`.
2. Put it at `backend/model/`.
3. `pip install torch transformers`
4. Set the environment variable and restart:

```bash
# Windows
set FIR_USE_MODEL=1
# Mac / Linux
export FIR_USE_MODEL=1

python app.py
```

`GET /api/health` will report `"model_backend": "distilbert"`.

If the model fails to load, `classifier.py` falls back to the stub and
prints a warning rather than crashing. On demo day that is the difference
between a degraded demo and no demo.

Track A should also tune `THRESHOLD` in `classifier.py` on the dev set.
0.35 is a starting guess; 0.5 is usually wrong for imbalanced multi-label.

---

## Files

| File | Contains |
|---|---|
| `app.py` | Flask routes and the pipeline |
| `scoring.py` | Priority scoring — pure functions, no Flask |
| `routing.py` | Routing engine — pure functions, no Flask |
| `classifier.py` | Stub and DistilBERT backends behind `predict()` |
| `db.py` | Connections and queries |
| `schema.sql` | Table definitions |
| `seed.sql` | 28 IPC sections and routing rules |
| `seed_demo.py` | Loads demo complaints |

`scoring.py` and `routing.py` deliberately import nothing from Flask or
the database, so they can be tested standalone and shown on a slide
without web plumbing around them.

---

## Before the review

- [ ] Trim `seed.sql` to exactly the sections in Track A's `label_set.json`
- [ ] Verify cognizable/bailable status against the CrPC First Schedule
      for the sections you plan to demo (324 and 506 have state amendments)
- [ ] Cold start: reboot, run only the commands above, confirm it comes up
- [ ] Architecture diagram says SQLite, not PostgreSQL or MySQL

## Design decisions to be able to defend

**Why is priority rule-based rather than learned?** No labelled priority
data exists, so a learned scorer would be inventing its own target. Police
triage must also be auditable — an officer can be shown exactly why a
complaint was marked High.

**Why max rather than mean across sections?** A complaint citing both
murder and trespass is a murder complaint. The mean would score it 5.5 and
route it Medium, which is precisely the failure a triage system cannot
make.

**Why is routing a table rather than a model?** Jurisdictions organise
specialised units differently. Routing policy has to be configurable by an
administrator without retraining anything.

**What if the classifier is wrong?** The system triages, it does not
decide. An officer confirms or overrides. Wrong routing costs a transfer,
not a miscarriage of justice.

**Why SQLite?** Prototype at TRL 3. It removes installation and credential
failure modes from the demo. The schema is portable to MySQL for
deployment; only `db.get_connection()` changes.
