# Backend tests

One command runs everything:

```bash
cd backend
./venv/bin/pip install -r requirements-dev.txt   # once
./venv/bin/python -m pytest
```

Every test runs on its own copy of a freshly seeded temporary database, with synthetic data only. Your `fir_system.db` is never touched.

| File | What it covers |
|---|---|
| `suite/test_security.py` | Authentication, sessions, one-time codes, authorization between roles and records, input handling, HTTP headers, abuse limits |
| `suite/test_workflow.py` | Every case-status transition, transfers, signing rules, audit trail, failure handling |
| `suite/test_decision_logic.py` | Priority scoring, routing and officer allocation against independent reference implementations; classifier interface |
| `suite/test_hardening.py` | Production start-up guard, restricted cases, model provenance, real multi-threaded concurrency |
| `suite/test_legacy_scripts.py` | Runs the two original end-to-end scripts below, each on its own database |

The original scripts still work on their own against `fir_system.db`. Reseed before each one, because they change data as they run:

```bash
python seed_demo.py && python tests/test_accounts.py
python seed_demo.py && python tests/test_cases.py
```

Each check prints PASS or FAIL. The run ends with ALL PASSED and exit code 0, or a count of failures and exit code 1.
