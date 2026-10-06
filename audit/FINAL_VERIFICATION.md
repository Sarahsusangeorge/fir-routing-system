# NIVARA: Final Verification Summary (5 October 2026)

Raw output: [evidence/07_final_verification_run.txt](evidence/07_final_verification_run.txt). Readiness: **ready for controlled demonstration** (see [EXECUTIVE_SECURITY_REPORT.md](EXECUTIVE_SECURITY_REPORT.md)).

| Check | Status | Evidence |
|---|---|---|
| Backend tests: 216 passed, 1 expected failure, 0 failed (includes the original 114 checks) | PASS | evidence/07, 08 |
| **Fresh clone from git: `scripts/setup.sh`, all tests, production build, Pages build, `scripts/dev.sh` end to end (sign-in, filing)** | **PASS** | evidence/10 |
| Frontend tests: 15 passed (14 at the first run; 1 added for the same-origin API mode) | PASS | evidence/09, 10 |
| TypeScript check and production build | PASS | evidence/07 |
| Backend import and `/api/health` | PASS | evidence/07 |
| Production start-up guard refuses unsafe configuration | PASS | evidence/07; `test_hardening.py` |
| Migration: fresh database, and in-place upgrade of a pre-audit database (data kept, login works) | PASS | evidence/07 |
| axe-core WCAG 2.2 AA scan, 5 pages | PASS (after fixing the footer contrast) | UX_ACCESSIBILITY_REPORT.md |
| Bandit, Ruff | PASS (findings triaged) | evidence/03, 04 |
| pip-audit, npm audit | PASS (0 known vulnerabilities) | evidence/05 |
| Secret scan (git history and bundle) | PASS | evidence/06 |
| Latency (local dev server) | PASS: read endpoints p95 ≤ 28 ms; list query 7 ms at 3,000 cases | evidence/02 |
| Frontend lint | PASS with 4 low warnings | evidence/07 |
| Model accuracy (F1, Jaccard) | BLOCKED: no weights and no labelled test set | |
| Real SMS and email delivery | BLOCKED: no provider credentials; DLT registration needed | |
| Firefox, Safari, Edge; screen readers | NOT TESTED | |
| OWASP ZAP, Playwright end-to-end | NOT TESTED | |
| Backup and restore | NOT APPLICABLE: no backup mechanism exists | |
| HTTPS, WSGI, monitoring | NOT APPLICABLE: no deployment exists | |

## Commands

```bash
cd backend && /opt/homebrew/bin/python3.14 -m venv venv && ./venv/bin/pip install -r requirements-dev.txt
./venv/bin/python -m pytest
```

```bash
cd backend && rm -f fir_system.db && ./venv/bin/python seed_demo.py && NIVARA_PORT=5001 ./venv/bin/python app.py
```

```bash
cd frontend && npm ci && npm test && npm run build
```

```bash
cd frontend && VITE_API_BASE_URL=http://localhost:5001 npx vite --host localhost
```

```bash
backend/venv/bin/python audit/scripts/perf_check.py
```
