# NIVARA — Project context (read this first)

Last updated: **25 October 2026**. Everything described here is merged into
`main`; there is no outstanding branch. This is the
starting point for any new chat or new team member, whether the work is
continuing development or drafting the journal paper. It says what the
project is, where things stand, what has been decided and why, and which
other documents hold the detail.

## Documents and what each is for

| File | Use it for |
|---|---|
| `docs/PROJECT_CONTEXT.md` (this file) | Orientation, status, decisions, open work |
| `docs/SYSTEM_DESIGN.md` | How the implemented system works: pipeline, allocation formula, workflow, security, data model, API. Source for the paper's methods section |
| `docs/EXPERIMENT_RESULTS.md` | Every result so far and the ones still missing. Source for the paper's results section |
| `README.md` | Short public description and quick start |
| `CODESPACES.md` | Running the app on GitHub with no local install |
| `backend/README.md` | Backend API, demo accounts, auth design |
| `audit/` | The October 2026 security, functional and accessibility audit: eight reports plus `evidence/` and `scripts/` |
| `backend/experiments/allocation_sim.py` | The allocation study behind the results |

## The project

- **Name:** NIVARA (Complaint Intelligence & Resolution).
- **What it is:** a B.Tech CSE capstone at VIT Vellore (batch of 2027). An
  NLP-assisted system that classifies Indian FIR complaint narratives into
  IPC sections, scores priority, routes each complaint to a police unit,
  allocates it to an investigating officer by availability and workload, and
  gives citizens, officers and administrators their own portals.
- **Scope:** everything is delivered in Project-I. There is **no Project-II**.
- **Tracks:** A — model (DistilBERT training and evaluation); B — backend
  (Sarah Susan George); C — frontend. The October audit was carried out by a
  team member and merged as PR #2.
- **Required scope as the team set it:** citizens sign in with mobile number
  + OTP + name, with records surviving a change of number and invisible to
  whoever is later issued an old number; citizens file, track and can sign
  digitally; officers sign in with username + password, see all FIRs across
  stations and who holds each; FIRs are auto-assigned from availability and
  workload metrics.
- **Honest framing** (audit council, and the position to take in the paper):
  present NIVARA as an **accountability-first case workflow with a
  statute-assisted triage layer that a human checks**. The classifier is not
  currently demonstrated — see "Status".

## Repository and environment

- **GitHub:** `Sarahsusangeorge/fir-routing-system`, owned by Sarah.
  Collaborators: postpaidzaki (`ahamedzaki`), Suhani Pasricha
  (`suhanipasricha`).
- **History:** PR #1 `add-auth-portal` (21 Sep, auth, portals, allocation,
  digital signing) and PR #2 `audit-fixes` (6 Oct, security, integrity,
  accessibility and testing) are both merged into `main`.
- **Local copy (Windows):** `C:\Users\sarah\fir-project`.
- **Stack:** Flask 3, Flask-JWT-Extended, Flask-CORS, SQLite; React +
  TypeScript + Vite + Tailwind + Framer Motion; Hugging Face Transformers
  (DistilBERT path, weights absent).

### Running it

```bash
bash scripts/dev.sh --reset     # starts backend and frontend together
```

Or by hand (PowerShell on Windows):

```powershell
cd backend
venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py       # demo accounts, stations, 15 complaints
python app.py             # http://localhost:5000
# second window
cd frontend
npm install
npm run dev               # http://localhost:5173 (use localhost, not 127.0.0.1)
```

`VITE_API_BASE_URL=http://localhost:5000` in `frontend/.env` or `.env.local`;
`VITE_API_BASE_URL=/` selects a same-origin API. With no backend configured
the app runs in demo mode. `FIR_USE_MODEL=1` loads DistilBERT if weights are
present. `NIVARA_PORT` avoids the macOS AirPlay clash on port 5000.

**Demo accounts** (from `seed_demo.py`; public passwords, demo only):
`admin` / `NivaraAdmin2026`; officers `arjun.rao`, `meena.pillai`,
`farhan.ali`, `deepa.menon`, `lakshmi.iyer`, `nikhil.das`, `kavya.nair`
(general duty) / `NivaraOfficer2026`. Citizens sign in with any mobile number
(demo citizen `9000000001`); the code is printed in the backend terminal.
Production mode refuses to start while demo passwords are active.

**Tests**

```bash
cd backend && pytest                 # 257 passed, 1 xfailed (verified 25 Oct 2026)
cd frontend && npx vitest run        # 32 passed (verified 25 Oct 2026)
python experiments/allocation_sim.py --runs 30
```

The expected failure is `test_stub_understands_negation`, documenting a real
limitation of the keyword baseline.

### Practical notes

- The repo uses CRLF on Windows; files copied in from elsewhere can look
  modified with no real change. Compare with
  `git diff --ignore-cr-at-eol --stat`.
- Work on a branch and merge through a pull request.
- Never commit `.env`, `fir_system.db` or `backend/.jwt_secret*`.

## Status (12 October 2026)

**Working and verified**

- Analysis pipeline: classification (keyword baseline live, DistilBERT path
  ready), decimal-exact rule-based priority with review flags, deterministic
  table-driven routing, token attributions, honest classifier provenance.
- Citizen mobile/email code sign-in; staff username + password; revocable
  JWT cookie sessions with CSRF, token versioning and a 12-hour cap;
  purpose-bound one-time codes; layered rate limits.
- Number change with record continuity, recycled-number isolation and
  administrator lost-SIM recovery.
- Filing, tracking, duplicate protection, and online signing inside the BNSS
  three-day window; in-person signature confirmation by officers.
- Seven-status case workflow with guards, compare-and-set concurrency,
  transfers, private case diary and a full audit trail.
- Workload-, capacity-, availability- and station-aware allocation with
  rebalancing and an unassigned queue.
- Transparency with privacy: all officers read all cases; only the handler
  acts; restricted handling of sexual-offence and Women & Child cases;
  contact masking; published officer workload.
- Security hardening: headers, body limits, production start-up guard, safe
  secret handling, no code printing in production.
- Accessibility: WAI-ARIA tabs, focus management, truthful copy, 0 axe
  violations on scanned pages.
- Editable decision policy (FR9): administrators can change severity weights
  and routing rules from the Policy screen, with an append-only record of who
  changed what. Changes apply to complaints analysed afterwards and never
  rewrite a stored result.
- Staff administration covers username, station, capacity and password reset;
  officers set their own availability.
- No third-party requests at runtime: the Tesseract OCR assets and the Inter
  font are served from the application's own origin.
- CI runs both suites, the type-check, the lint, the production build and a
  blocking check for high-severity Bandit findings on every push.
- Station and unit administration, with reference checks: neither can be
  removed while officers, complaints or routing rules still name it, and
  renaming a unit carries its rules and officers with it.
- Tests: 257 backend + 32 frontend, with audit evidence.

**Open work — development**

- **Model weights are missing** (Track A); the keyword baseline is what runs.
- **s.155(4) is not implemented.** A case containing at least one cognizable
  offence is cognizable in its entirety; the system treats cognizability as a
  per-section attribute. The maximum operator means this rarely changes a
  priority level, but an interface reporting cognizability per section would
  state it incorrectly. Fix it alongside the IPC-to-BNS mapping.
- Notifications and attachments are unbuilt. Both are larger than the rest of
  this list: notifications need a delivery channel and citizen preferences,
  and attachments in a police system are evidence, needing storage, type and
  size limits, and access rules that follow restricted-case redaction.
- Pre-existing lint debt: `ruff check backend` reports about 59 findings and
  Bandit reports 19 medium ones, all inherited and all accepted by the
  October audit (0 high severity). CI reports them without failing the build;
  a new high-severity finding does fail it.
- Optional, from the audit council: make triage urgency-first (escalate
  uncertain-but-grave cases) rather than demoting them.

**Open work — report and paper**

- The Project-I report is out of date: it describes a single officer queue
  with no stations, allocation, citizen portal, digital signing or the audit
  work, and still defers the portal to "Project-II"; its figures predate the
  current system. The literature review, problem statement and dataset
  sections remain usable. It is generated from `build.js` in the report build
  kit.
- The journal paper needs the Track A results and the target journal's author
  guidelines (including its policy on AI-assisted writing) before drafting.

## Decisions and their reasons

| Decision | Reason |
|---|---|
| Relational database (SQLite now, PostgreSQL/MySQL later), not MongoDB | The data is relational; integrity rules (one account per number, valid roles) and multi-step transactions are enforced by the database; SQLite needs no server for demos |
| Priority is rule-based, not learned | No labelled priority data; triage must be explainable; tunable per jurisdiction |
| Maximum, not mean, over sections | The gravest credible charge should set priority |
| Decimal arithmetic for scoring | Float error changed the level at exact thresholds |
| Routing is table-driven with victim-centric precedence and a deterministic tie-break | Jurisdictions organise units differently; the same complaint must route the same way |
| Citizens sign in with codes, staff with passwords | Citizens file rarely; a code proves control of the contact number. Staff access sensitive data daily on issued accounts |
| Codes bound to their purpose | A sign-in code must not be usable to sign a complaint |
| Account id, not phone number, is the identity | Records follow the person; recycled numbers start empty |
| Sessions in httpOnly cookies, with revocation | A script-readable token would be exposed by any XSS bug; revocation closes stolen or stale sessions |
| Officers read everything, act only on their own cases | The team's transparency requirement, without letting anyone change another officer's case |
| Restricted access for sexual-offence and Women & Child cases | Victim identity protection (IPC 228A / BNS s.72) outweighs full narrative transparency |
| Complainant contact masked for non-handlers | Contact details are personal data, not needed for transparency |
| Model predictions hidden from citizens | Decision support for officers, not a legal determination |
| Allocation: fit tier + load/capacity + busy penalty | Keeps cases local and with specialists while protecting officers from overload; every term is inspectable and ablated |
| Digital signing by code + declaration | Satisfies the signing step for a prototype; a statutory e-signature is future work |
| Decision logic in pure modules | Testable and explainable independently of Flask and SQL |
| Classifier provenance stored per case | A fallback prediction must never pass as a model prediction |
| Policy changes apply forward only, never retroactively | A complaint's priority and routing are part of its record; rewriting them would destroy the audit trail and surprise the complainant |
| A routing rule may name a unit no officer serves | Jurisdictions reorganise, and blocking it would make the table harder to edit than reality allows; the administrator is warned that cases will wait |
| OCR and font assets served from our own origin | Third-party code executing in a police system, and a third party learning when someone opened it, are both avoidable |
| Cognizable and bailable are jurisdiction-configurable, not constants | s.506 is non-cognizable in the First Schedule but cognizable and non-bailable in Uttar Pradesh by a 1989 notification under s.10 of the Criminal Law Amendment Act 1932, upheld by the Allahabad HC Full Bench and approved by the Supreme Court. A single national table would be wrong somewhere by construction |

## How to work on this project

- For development, start from `docs/SYSTEM_DESIGN.md` and the code; the
  repository is the source of truth.
- For the paper, take methods from `docs/SYSTEM_DESIGN.md` and results only
  from `docs/EXPERIMENT_RESULTS.md`. State no accuracy figures until Track A
  supplies them; describe the allocation study as a simulation on a synthetic
  workload, with its trade-offs and limitations.
- Keep these three documents current when behaviour changes: they are what
  the next person, or the next chat, reads first.
