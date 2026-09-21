# Backend tests

Two suites that exercise the API end to end through Flask's test client. No
server needs to be running; each rebuilds nothing, so seed the demo database
first.

```bash
cd backend
python seed_demo.py           # fresh database with demo accounts and complaints
python tests/test_accounts.py # sign-in, phone changes, digital signing, allocation, transparency
python seed_demo.py           # reseed: the suites change data as they run
python tests/test_cases.py    # case workflow, transfers, reassignment, staff changes
```

Each check prints PASS or FAIL and the run ends with ALL PASSED or a count of
failures, so a non-zero failure count is easy to spot in a demo or a viva.
