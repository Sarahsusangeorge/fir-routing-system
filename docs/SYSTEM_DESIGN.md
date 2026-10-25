# NIVARA — System design reference

Snapshot of the implemented system as of **12 October 2026**, taken from
`main` at commit `918ebe0` (merge of the October security audit, PR #2).
Written as the technical reference for development and as source material
for the paper's system and methods sections. Every statement describes code
that exists and is covered by the automated tests unless it is marked as a
limitation. When the code changes, update this file.

## 1. Purpose and framing

NIVARA is a decision-support prototype for police complaint triage. A
complaint narrative is classified into Indian Penal Code (IPC) sections,
scored for priority, routed to a police unit and allocated to an
investigating officer by availability and workload. Citizens file and track
complaints, officers investigate them, administrators manage staff and
cases.

The system triages and recommends; an officer decides, and every decision is
attributable and auditable. Following the October audit's review council,
NIVARA is best presented as **an accountability-first case workflow with a
statute-assisted triage layer that a human checks**, not as a validated
classifier: the trained model is not in the repository (Section 12).

## 2. Architecture

See `fig_architecture.png`.

- **Clients:** React + TypeScript single-page app (Vite, Tailwind). Three
  role-specific portals. A demo mode runs with no backend, but only when no
  backend is configured at all.
- **API:** Flask REST service. `auth.py` (identity, sessions, codes, rate
  limits, role checks), `app.py` (complaint and case routes, access rules,
  security headers), `admin.py` (staff management).
- **Decision layer:** pure Python with no Flask or SQL imports, so each rule
  can be tested and presented in isolation: `classifier.py`, `scoring.py`,
  `routing.py`, `workflow.py`.
- **Persistence:** SQLite through `db.py`; the schema is relational and
  portable to PostgreSQL or MySQL by changing the connection helper.
- **Repository extras:** `audit/` (eight audit reports, evidence and
  scripts), `scripts/dev.sh` and `scripts/setup.sh`, `.devcontainer/` for
  GitHub Codespaces, `backend/experiments/` for the allocation study.

## 3. Complaint analysis pipeline

Executed by `process_complaint()` in `app.py`:

1. **Classification** (`classifier.predict_with_backend`). Two paths with the
   same output format:
   - *DistilBERT* (`FIR_USE_MODEL=1`): multi-label
     `DistilBertForSequenceClassification` over 100 IPC labels from the ILSI
     corpus, 256-token input, sigmoid threshold 0.2 from
     `model/threshold.json`, at most 4 sections, `local_files_only=True` so
     nothing is downloaded at run time.
   - *Keyword baseline*: rule patterns covering 22 IPC sections. **This is
     what currently runs**, because the model weights are not in the
     repository.
   The classifier that actually ran is returned, stored per complaint
   (`complaints.model_backend`) and shown in the UI as a badge, so a
   fallback can never pass as a model prediction.
2. **Priority** (`scoring.score_complaint`). Rule-based and deliberately not
   learned: `score = max over predicted sections of (severity_weight ×
   confidence)`, severity weights 1–10 from `ipc_sections`. Maximum, so the
   gravest credible charge sets priority. High ≥ 6.5, Medium ≥ 3.5, else Low.
   Arithmetic uses `Decimal` with half-up rounding, so values exactly on a
   threshold are stable.
3. **Review flags** (`scoring.review_flags`). Plain-language reasons an
   officer should check the triage: the prediction came from the fallback; a
   section has no severity weight; or a grave section was predicted with low
   confidence and so did not reach High. Flags are stored and displayed; the
   score and level are unchanged.
4. **Routing** (`routing.route_complaint`). Table-driven: each rule maps a
   section to a unit with a precedence; lowest precedence wins, ties broken by
   confidence and finally by section code, so routing is deterministic.
   Victim-centric ordering. Default: Local Police Station.
5. **Explainability** (`classifier.explain`). Token attributions from the same
   classifier that produced the predictions, stored with the complaint.
6. **Persistence and allocation.** `db.save_complaint` writes the complaint,
   its sections and a `filed` event in one transaction; `db.allocate` then
   assigns an officer. If allocation fails, the complaint is still saved and
   waits in the unassigned queue — the citizen is never told that filing
   failed when it succeeded.
7. **Duplicate protection.** Identical text from the same user within 10
   minutes returns the existing case with `duplicate: true` instead of
   creating another.

## 4. Identity, authentication and sessions

**Roles:** citizen, officer, admin, enforced per route by `role_required`.

**Citizen sign-in (one-time code).** Mobile number (primary) or email.
Numbers are normalised to E.164. Codes are 6 digits from `secrets`, stored
only as HMAC-SHA256 of `purpose:identifier:code`, valid 10 minutes, 5 wrong
attempts per code and at most 15 wrong guesses per address per 6 hours across
codes. **Codes are bound to their purpose** (sign-in, number change,
signature), so a code issued for one action cannot be used for another. A new
citizen must supply a name; the code is not consumed until the account
exists. Staff addresses never receive codes, and responses are identical
either way.

**Staff sign-in.** Username or email plus password (Werkzeug salted hashes;
≥ 10 characters, mixed case, a digit). A dummy hash is verified for unknown
usernames so timing does not reveal which accounts exist. Staff accounts are
created only by administrators; `create_admin.py` bootstraps the first.

**Sessions.** Signed JWT in an httpOnly cookie with double-submit CSRF on
every state-changing request; 60-minute lifetime with sliding renewal under
30 minutes remaining, and a **12-hour absolute lifetime**. Each user has a
`token_version` that is bumped on password, active-status and phone changes,
and logout adds the token id to `revoked_tokens`; both are checked on every
request, so a copied cookie stops working when the user signs out or the
account is secured. User and role are re-read from the database per request.

**Rate limiting** (`auth_attempts`): 5 failed logins per account and 20 per
IP per 15 minutes; code requests one per minute and 5 per 15 minutes per
identifier **per purpose**, plus 20 per 15 minutes per IP across purposes;
complaint filing 5 per hour per citizen and 60 per hour per staff account.
A phone-change request for a number already in use is rate-limited first and
then answered identically to any other, so nobody can test whether a number
belongs to a complainant.

## 5. Officer allocation

`workflow.rank_officers` decides; `db.allocate` records. Unchanged by the
audit, and evaluated in `EXPERIMENT_RESULTS.md`.

**Inputs per officer** (`db.officer_metrics`, one SQL query): open cases;
weighted load = Σ w(priority) with High 3, Medium 2, Low 1; capacity
(per officer, default 10); availability (available, busy, on_leave); unit;
station; time of last assignment.

**Eligibility tier** t(o, c):

| Tier | Condition |
|---|---|
| 0 | officer's unit = case's unit, officer's station = case's station |
| 1 | officer's unit = case's unit, other station |
| 2 | general duty (no unit), same station |
| 3 | general duty, other station |
| excluded | on leave, deactivated, or a different specialist unit |

**Score** (lower wins): `score = t(o, c) + L(o)/C(o) + b(o)`, where L is
weighted load, C is capacity and b = 0.5 for officers marked busy. Ties go to
the least recently assigned, then the lowest id, so allocation is
deterministic. Fit normally dominates, but an officer far over capacity can
rank below a less specialised colleague with spare capacity.

**Recording.** The chosen officer and the reason (open cases, load as a
percentage of capacity) go into the audit trail. With nobody eligible the
case enters the unassigned queue.

**Rebalancing.** `redistribute_cases` moves an officer's open cases when they
go on leave, are deactivated or change unit; `allocate_unassigned` places
waiting cases when an officer is added or returns, and at start-up.

## 6. Case lifecycle, access rules and concurrency

See `fig_case_lifecycle.png`. Rules live in `workflow.plan_review`.

- **Statuses:** New → Under Review → Registered or Not Registered;
  Registered → Under Investigation or Closed; Under Investigation → Charge
  Sheet Filed or Closed. Not Registered, Charge Sheet Filed and Closed are
  final; only administrators reopen them.
- **Guards:** transitions must be in `TRANSITIONS`; registering a
  citizen-filed complaint requires a signature; Closed and Not Registered
  require a note to the complainant; unit transfers require a reason, keep
  the original unit and trigger re-allocation; only administrators reassign;
  any officer action on a New case moves it to Under Review.
- **Concurrency:** updates are compare-and-set on status and assignee
  (`db.review_complaint` with `expected_status` / `expected_assignee`). A
  stale edit gets HTTP 409 and is asked to reload, so two officers cannot
  silently overwrite each other.
- **Case diary:** private, timestamped entries by the handling officer.
- **Audit trail** (`complaint_events`): every action with actor and time.

**Transparency and privacy.**
- Any officer can read any complaint in the district and see who holds it;
  `?view=mine` gives their own caseload.
- Only the assigned officer or an administrator can act on a case or read its
  diary (`owns_case`).
- **Restricted cases** (`is_restricted`): complaints routed to the Women &
  Child Protection Unit, or predicting a sexual-offence section, show only
  status, unit and holder to other officers. Narrative, complainant,
  explanation tokens, notes, transfer reasons and the complainant's name in
  the audit trail are visible to the handling unit, the assigned officer and
  administrators only (IPC 228A / BNS s.72).
- Contact details of complainants are masked for other officers: country code
  and last two digits only; email as first character plus domain.
- Officer workload is visible to all staff (`GET /api/officers`), the same
  numbers the allocator uses.

## 7. Citizen features

- **Filing** through `POST /api/classify`, optionally naming a station.
- **Tracking** (`GET /api/my/complaints`): status, station, unit and officer
  once reviewed, notes, signature deadline, and a filtered timeline. Model
  predictions and priority are withheld from complainants: they are decision
  support for officers, not legal findings.
- **Signing.** BNSS 2023 s.173 takes electronically given information on
  record once the informant signs within three days; the deadline is computed
  in SQL as `received_at + 3 days`. `_can_sign_online` enforces one rule for
  both endpoints and the UI: within three days, case still open, not already
  signed. Online signing verifies a purpose-bound code sent to the citizen's
  own number plus an explicit declaration, storing method `digital` and the
  evidence; it does **not** mark the case reviewed. An officer confirming an
  in-person signature stores method `in_person`.
- **Changing number:** see Section 8.
- **OCR** of a photographed complaint runs entirely in the browser; the image
  is never uploaded. (Tesseract.js fetches its worker and language data from a
  public CDN on first use — self-hosting them is recommended.)

## 8. Identity continuity across number changes

- The account id, not the phone number, is the identity; complaints reference
  `filed_by`.
- **Self-service:** a signed-in citizen verifies a code sent to the new
  number; `db.change_phone` updates `users.phone`, records the released number
  in `phone_history` and bumps `token_version`.
- **Recycled numbers:** a released number no longer opens the account, so a
  new holder signing in gets a fresh, empty account.
- **Lost SIM:** an administrator re-points the account after in-person
  verification (`PUT /api/admin/users/<id>/phone`), recorded with the reason.
- **Unverified contacts** given at sign-up are stored as `contact_email` /
  `contact_phone` and never serve as sign-in identifiers.

## 9. Data model

See `fig_data_model.png`. Tables: `users` (with `token_version`),
`login_codes` (with `purpose`), `auth_attempts`, `revoked_tokens`,
`phone_history`, `stations`, `ipc_sections`, `routing_rules`, `complaints`
(with `model_backend`, `review_flags`, signature and assignment columns),
`complaint_sections`, `complaint_events`. Integrity rests on database
constraints: `UNIQUE` on phone, email and username; `CHECK` on role and on
staff having a password; foreign keys from events and sections. Multi-step
writes are single transactions. Older databases are upgraded in place at
start-up; `NIVARA_DB_PATH` lets tests use isolated copies.

## 10. API summary

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/health` | anyone | status and active classifier |
| POST | `/api/auth/login` | staff | username or email + password |
| POST | `/api/auth/otp/request`, `/otp/verify` | citizen | code sign-in |
| POST | `/api/auth/phone/change/request`, `/verify` | citizen | move account to a new number |
| GET, POST | `/api/auth/me`, `/api/auth/logout` | signed in | session; logout revokes the token |
| POST | `/api/classify` | citizen, staff | file and analyse a complaint |
| GET | `/api/complaints` | staff | all cases; `view=mine`, `officer`, `unit`, `station`, `scope` |
| GET | `/api/complaints/<id>` | owner, staff | full view for handler/admin; redacted otherwise |
| PATCH | `/api/complaints/<id>` | handler, admin | status, transfer, signature, note, reassign (admin); 409 on stale edits |
| POST | `/api/complaints/<id>/diary` | handler, admin | case diary entry |
| POST | `/api/complaints/<id>/sign/request`, `/sign` | citizen | sign online within the three-day window |
| GET | `/api/my/complaints` | citizen | own complaints and progress |
| GET | `/api/officers` | staff | availability, open cases, capacity, load |
| PATCH | `/api/me/availability` | officer | available / busy / on leave |
| GET | `/api/stats`, `/api/units`, `/api/stations`, `/api/sections` | staff | counts and reference data |
| GET, POST, PATCH | `/api/admin/users[/<id>]` | admin | staff accounts, incl. username, station, capacity, availability and password reset |
| PUT | `/api/admin/users/<id>/phone` | admin | lost-SIM recovery |
| GET, PATCH | `/api/admin/sections[/<code>]` | admin | severity weights and the cognizable/bailable attributes behind them |
| GET, POST | `/api/admin/routing-rules` | admin | which unit handles which section, and in what precedence |
| PATCH, DELETE | `/api/admin/routing-rules/<id>` | admin | change or remove a routing rule |
| GET, POST | `/api/admin/stations` | admin | police stations, with what depends on each |
| PATCH, DELETE | `/api/admin/stations/<code>` | admin | rename a station, or remove an unused one |
| GET, POST | `/api/admin/units` | admin | police units, registered and in use |
| PATCH, DELETE | `/api/admin/units/<name>` | admin | rename a unit (carrying its rules and officers), or remove an unused one |
| GET | `/api/admin/policy-changes` | admin | append-only record of who changed which policy value, and when |

All `/api` responses carry `no-store`; requests are limited to 256 KiB;
errors are JSON with no internals. Security headers: nosniff, frame denial,
CSP, Referrer-Policy, Permissions-Policy, and HSTS over HTTPS.

## 11. Configuration and operations

Environment: `NIVARA_ENV` (`production` refuses to start with a weak or
missing secret, insecure cookies, the debugger on, no delivery channel, or
demo passwords still active), `NIVARA_JWT_SECRET`, `NIVARA_PORT`,
`NIVARA_DB_PATH`, `NIVARA_FRONTEND_ORIGINS`, `NIVARA_COOKIE_SECURE`,
`NIVARA_COOKIE_SAMESITE`, `FLASK_DEBUG`, `FIR_USE_MODEL`, `FIR_EXPLAIN`,
`SMTP_*`, `SMS_PROVIDER` and `TWILIO_*`. Codes are printed to the console
only outside production. The secret file is created with mode 600 and is
git-ignored.

Running: `bash scripts/dev.sh --reset` starts both halves; GitHub Codespaces
is configured in `.devcontainer/`. Dependencies are pinned, with
`requirements-dev.txt` for the tooling.

## 12. Limitations and future work

- **The classifier is not demonstrated.** The DistilBERT weights are absent,
  so the keyword baseline (22 sections) is what runs; there is no reproducible
  accuracy, and the stub fails on negation and on offences without keywords.
  Any F1 claim must wait for the weights and an evaluation run.
- **Legal basis out of date.** Sections are IPC; the BNS replaced it in July
  2024. Cognizable and bailable values are unverified. Mapping needs legal
  review, not a code change.
- **Priority demotes uncertain grave cases.** Severity × confidence lowers
  priority exactly where the model is least sure. Review flags surface this,
  but escalating instead is an open research decision.
- **Data protection.** DPDP Act 2023 measures (encryption at rest, retention
  policy, consent records) are not implemented.
- **Infrastructure.** No HTTPS deployment, WSGI server, backups or
  monitoring; SQLite suits a single-node pilot only.
- **Missing features.** Notifications, attachments, multilingual support,
  CCTNS integration, a legally valid e-signature.
- **Not tested:** Firefox, Safari, Edge, screen readers, OWASP ZAP, Playwright
  end-to-end runs.
- **Allocation evidence is a simulation** on a synthetic workload.

## 13. Editable decision policy (FR9)

Priority and routing read two database tables rather than model weights, so a
jurisdiction can change policy without retraining anything. That is only true
of the running system if the tables can actually be edited, which is what
these endpoints and the administrator's Policy screen are for.

- **Severity weights.** `ipc_sections.severity_weight` on a 1-10 rubric
  (Section 3), with the cognizable and bailable flags and the maximum
  punishment that justify it. Priority is `max(severity x confidence)`, so a
  change here moves the priority of every complaint analysed afterwards.
- **Routing rules.** `routing_rules` maps a section to a unit with a
  precedence; the lowest precedence wins, which is what makes routing
  victim-centric. Rules can be added, repointed, reordered or removed. A unit
  no active officer serves is allowed, because jurisdictions reorganise, but
  the administrator is told at once that cases routed there will wait
  unassigned.
- **Changes apply forward only.** A complaint's priority, routing and the
  reasons for both are stored when it is analysed and are never rewritten by
  a later policy change. Two complaints with identical text can therefore
  differ, and the record of each says why.
- **Stations and units.** Both are reference data allocation reads directly,
  and neither is protected by a foreign key: `users.station`,
  `complaints.station` and `users.unit` hold names as text. Removing either is
  refused while anything still names it, and the refusal reports the counts.
  A station's code is immutable for the same reason. Renaming a unit updates
  the registry, the routing rules and the officers in one transaction, since
  moving only the registry would leave rules routing to a unit that no longer
  exists. Units that predate the registry are listed as in use but
  unregistered, and must be registered before they can be renamed.
- **Every change is attributable.** `policy_changes` is append-only and
  records the administrator, the field, the old value, the new value and the
  time. A change that alters nothing is not recorded. This is the same
  standard the case event log sets (Section 6): a change to how the system
  decides is a decision in its own right.
