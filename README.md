# NIVARA: FIR Categorization and Intelligent Routing (research prototype)

> **Student research prototype, not an official police service.** Use synthetic data only. In an emergency, call 112.

NIVARA is a decision-support prototype for police complaint triage. A complaint narrative goes through four steps:

1. **Classify:** suggest applicable IPC sections.
2. **Prioritise:** compute `max(statutory severity × confidence)`, with "Officer review needed" flags when the triage is uncertain.
3. **Route:** pick a police unit from a victim-centric rule table.
4. **Allocate:** assign the least-loaded suitable officer.

The case then moves through a lifecycle the server enforces, with an audit trail and a case diary. There are three portals: citizen, officer and administrator. An officer always makes the decision; NIVARA does not determine guilt or legal outcomes.

**Current limitations** (details in [audit/EXECUTIVE_SECURITY_REPORT.md](audit/EXECUTIVE_SECURITY_REPORT.md)):

- **The classifier.** What runs is a keyword baseline covering 22 IPC sections. The DistilBERT path needs model weights that are not in this repository.
- **The law.** Sections are IPC; the BNS mapping (in force since July 2024) is not done yet.

## Quick start

**On GitHub, with no server or install:** see [CODESPACES.md](CODESPACES.md). It covers both the full app in Codespaces and the always-on demo site on GitHub Pages.

**On your own machine** (Python 3.10 or newer, 3.12 recommended; Node 22+):

```bash
bash scripts/dev.sh --reset
```

Open http://localhost:5173. Demo staff accounts are listed in [backend/README.md](backend/README.md). For the citizen account, sign in with mobile `9000000001`; the 6-digit code is printed in the terminal.

## Tests

```bash
cd backend && ./venv/bin/python -m pytest
```

```bash
cd frontend && npm test && npm run build
```

The backend suite is 217 tests. It includes the original end-to-end scripts, and runs on isolated temporary databases. The frontend suite is 15 tests. Both run automatically on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Flask API: `app.py` (routes and pipeline), `auth.py`, `admin.py`, `db.py`, `scoring.py`, `routing.py`, `workflow.py`, `classifier.py`, SQL schema and seed data |
| `frontend/` | React + TypeScript app (Vite, Tailwind) |
| `scripts/` | `setup.sh` (install) and `dev.sh` (run the API and web together) |
| `audit/` | Security, functional and accessibility audit reports, plus raw evidence |
| `.devcontainer/`, `.github/` | GitHub Codespaces configuration; CI and Pages workflows |

## Security model in brief

- **Citizens** sign in with a one-time code. **Staff** use admin-issued passwords.
- **Sessions:** HttpOnly cookies with CSRF protection, revocable on the server, with a 12-hour maximum.
- **Case access:** officers can act only on cases allocated to them. Sexual-offence and Women & Child Protection cases are readable only by that unit, the assigned officer and administrators.
- **Production mode** (`NIVARA_ENV=production`) refuses to start with unsafe settings or demo passwords still active.

See [backend/README.md](backend/README.md) for the API and configuration.
