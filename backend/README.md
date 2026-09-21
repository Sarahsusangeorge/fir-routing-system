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
python seed_demo.py      # creates the database, demo accounts and 15 demo complaints
python app.py            # starts on http://localhost:5000
```

No database server is needed. SQLite is built into Python, and everything,
including user accounts, lives in `fir_system.db`.

Then, in a second terminal, start the frontend against this API:

```bash
cd frontend
# Windows (PowerShell):  $env:VITE_API_BASE_URL="http://localhost:5000"; npm run dev
# Mac / Linux:
VITE_API_BASE_URL=http://localhost:5000 npm run dev
```

Open **http://localhost:5173** (not 127.0.0.1; see "Sign-in doesn't stick"
below).

### Demo accounts

`seed_demo.py` prints these. Their passwords are public, so never run it
against a real deployment.

| Role | Sign in with |
|---|---|
| Administrator | `admin` / `NivaraAdmin2026` |
| Duty officer (general duty, PS-CENTRAL) | `kavya.nair` / `NivaraOfficer2026` |
| Local Police Station officer | `arjun.rao` / `NivaraOfficer2026` |
| Economic Offences Wing officer | `farhan.ali` / `NivaraOfficer2026` |
| Citizen | Any mobile number or email. The sign-in code is printed in the backend terminal. |

Every demo officer is listed when `seed_demo.py` runs, with their unit,
station and password. Staff can sign in with their username or their email.

For a real first administrator instead, run `python create_admin.py`.

Check it works:

```bash
curl http://localhost:5000/api/health
```

If SQLite ever gets into a bad state, delete `fir_system.db` and re-run
`seed_demo.py`. It rebuilds from `schema.sql` and `seed.sql` in seconds.

---

## API

Frozen contract. Do not change any field name without announcing it.

Revision 2 added authentication. Existing field names are unchanged; the
classify response gained `status` and `source`.

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/health` | Anyone | Backend status and active classifier |
| POST | `/api/auth/login` | Staff | Password sign-in with `username` (or `email`) |
| POST | `/api/auth/otp/request` | Citizen | Send a 6-digit code to a mobile number or email (`channel`: `sms` or `email`) |
| POST | `/api/auth/otp/verify` | Citizen | Verify the code (creates the account on first use; needs `name`) |
| POST | `/api/auth/phone/change/request` | Citizen | Send a code to a new mobile number |
| POST | `/api/auth/phone/change/verify` | Citizen | Move the account to that number |
| GET | `/api/auth/me` | Signed in | Current user and CSRF token |
| POST | `/api/auth/logout` | Signed in | End the session |
| POST | `/api/classify` | Citizen, staff | Classify, score, route and store a complaint |
| GET | `/api/complaints` | Staff | Every case in the district; `?view=mine`, `?officer=`, `?unit=`, `?station=`, `?scope=open\|closed\|all` |
| GET | `/api/complaints/<id>` | Owner, staff | One case. The assigned officer and admins get the diary and can act; other officers get a read-only view with contact details masked |
| PATCH | `/api/complaints/<id>` | Assigned officer, admin | Status, transfer, signature, note; `assigned_to` (admin) reassigns |
| POST | `/api/complaints/<id>/diary` | Assigned officer, admin | Add a case diary entry |
| POST | `/api/complaints/<id>/sign/request` | Citizen | Send a code to sign the complaint online |
| POST | `/api/complaints/<id>/sign` | Citizen | Sign it (`code` + `declaration: true`) |
| GET | `/api/my/complaints` | Citizen | The citizen's own complaints and their progress |
| GET | `/api/officers` | Staff | Every officer's availability, open cases, capacity and load |
| PATCH | `/api/me/availability` | Officer | Set `available`, `busy` or `on_leave` |
| GET | `/api/stats` | Staff | Counts by priority, unit and status |
| GET | `/api/units` / `/api/stations` | Staff | Units and police stations |
| GET | `/api/sections` | Staff | IPC reference table |
| GET/POST | `/api/admin/users` | Admin | List or create staff (username, unit, station, capacity) |
| PATCH | `/api/admin/users/<id>` | Admin | Deactivate, reactivate, change unit, station, availability, capacity or password |
| PUT | `/api/admin/users/<id>/phone` | Admin | Re-point a citizen account to a new number after station verification |

Without a session, protected routes return 401 with
`{"error": "...", "code": "AUTH_REQUIRED"}`. With the wrong role they
return 403.

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

A citizen calling `/api/classify` gets a reduced response instead: reference
number, status, and the unit once an officer has reviewed it. Section
predictions and priority are an officer's working material, not a legal
determination, so they are never shown to complainants.

---

## Authentication

**Roles.** Citizens file and track their own complaints. Officers review the
queue; an officer with a unit sees only that unit's complaints, and one
without a unit (a duty officer) sees all. Administrators can do everything
an officer can, plus manage staff accounts.

**Sign-in.** Citizens get a 6-digit code on their mobile number or email
(10-minute expiry, 5 attempts, one request a minute per purpose). They have
no password to forget, and it fits people who file rarely. Staff use a
username and password; accounts are created only by an administrator, and a
staff address cannot sign in with a code.

**Changing a mobile number.** The account, not the number, is the identity.
A signed-in citizen verifies the new number with a code and keeps every
complaint; the old number is released into `phone_history` and no longer
opens the account, so whoever is issued it next gets a new, empty one. A
citizen who has lost the old SIM cannot do this themselves, so an
administrator can re-point the account after verifying identity at the
station (`PUT /api/admin/users/<id>/phone`), which is recorded with the
reason and the administrator's id.

**Signing a complaint.** The complainant can sign at the station, which the
officer confirms, or online: they re-enter a code sent to their own number
and tick the declaration, and the method and evidence are stored against the
complaint. Aadhaar e-Sign or a DSC would give the signature statutory
weight in production; the flow is the same.

**Sessions.** A signed JWT in an httpOnly cookie, so page scripts cannot
read it. Tokens last 60 minutes and are renewed automatically while the
user is active. Every POST/PATCH must carry the CSRF token in an
`X-CSRF-TOKEN` header. The role is re-read from the database on every
request, so deactivating an account takes effect on the user's next
action.

**Protections.** Passwords are stored as salted hashes (Werkzeug) and must
be 10+ characters with mixed case and a number. After 5 failed sign-ins for
an email (or 20 from one IP) in 15 minutes, sign-in is blocked for that
email or IP. A wrong email and a wrong password get the same message, so
the response doesn't reveal which accounts exist.

**Who can see and do what.** Any officer can read any case in the district
and see which officer holds it — the transparency the portal is for. Only
the officer a case is allocated to, or an administrator, can change it or
write in its diary, and complainant contact details are masked for everyone
else.

**Allocation.** New cases are allocated automatically (`workflow.rank_officers`):
officers on leave are skipped, and the rest are ranked by fit (their unit at
the case's station first, then their unit elsewhere, then general duty),
then by weighted workload against their own capacity, with a penalty for
officers marked busy. Case weight follows priority (High 3, Medium 2,
Low 1), so three low-priority cases do not count the same as three murders.
Ties go to whoever was assigned a case least recently. The reason is written
into the audit trail, and `/api/officers` shows the same numbers to
everyone. Cases move automatically when an officer goes on leave, is
deactivated or changes unit, and waiting cases are picked up when an officer
is added.

**Review workflow.** `New` → `Under Review` → `Registered` or `Not Registered`,
then `Under Investigation` → `Charge Sheet Filed` or `Closed`.
A citizen complaint can only be registered once it has been signed, online
or at the station. Under BNSS s.173, information given
electronically is taken on record once signed within three days, and the
UI shows that deadline. Changing the unit requires a reason, and "Not
Registered" requires a note to the complainant. Every action is written
to `complaint_events`. Closed complaints can only be reopened by an
administrator.

**Configuration.** Copy `.env.example` to `.env`. Without `SMTP_HOST`,
sign-in codes are printed to this terminal instead of emailed, which is
what you want for the demo.

### Sign-in doesn't stick

Open the frontend at `http://localhost:5173`, matching the API's
`localhost:5000`. If one uses `localhost` and the other `127.0.0.1`, the
browser treats them as different sites and won't send the session cookie.
If you serve the frontend from another address, add it to
`NIVARA_FRONTEND_ORIGINS`.

### Existing databases

An older `fir_system.db` is upgraded in place on startup: new tables and
columns are added, and complaints are kept. Accounts live in their own
tables and survive `init_db(force=True)`.

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
| `auth.py` | Sign-in, sessions, CSRF, role checks, number changes |
| `workflow.py` | Case statuses, transitions and officer allocation (pure functions) |
| `tests/` | Two end-to-end suites over the API |
| `admin.py` | Staff account management |
| `create_admin.py` | Creates the first administrator |
| `schema.sql` | Complaint and reference tables |
| `schema_auth.sql` | User, sign-in code and rate-limit tables |
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
decide. An officer confirms or overrides, with a recorded reason. Wrong
routing costs a transfer, not a miscarriage of justice.

**Why email codes for citizens and passwords for staff?** Citizens file
rarely and forget passwords, and a code proves they control the contact
address the police will use. Staff sign in daily to sensitive data, so
they get individually issued, administrator-controlled accounts.

**Why cookies rather than storing the token in localStorage?** Any script
on the page can read localStorage, so one XSS bug would leak every session.
An httpOnly cookie is invisible to scripts, and the CSRF header stops other
sites from using it.

**Why doesn't the citizen see the predicted IPC sections?** They are
decision support for an officer, not a legal finding. Showing a
complainant an unreviewed prediction would read as a determination the
system is explicitly designed not to make.

**Why SQLite?** Prototype at TRL 3. It removes installation and credential
failure modes from the demo. The schema is portable to MySQL for
deployment; only `db.get_connection()` changes.
