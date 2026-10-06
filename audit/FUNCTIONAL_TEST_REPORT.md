# NIVARA: Functional Test Report

**Run date:** 5 October 2026. Apple M4, Python 3.14.5, Node 26.0.0. Synthetic data only.

## Totals (measured)

| Suite | Executed | Passed | Failed | Expected failure | Blocked |
|---|---|---|---|---|---|
| Backend pytest (`backend/tests/suite`) | 217 | 216 | 0 | 1 | 0 |
| ↳ of which, the project's original end-to-end scripts | 2 tests wrapping 114 checks (55 + 59) | 2 | 0 | | |
| Frontend Vitest (`frontend/src/**/*.test.ts(x)`) | 14 | 14 | 0 | | |
| Manual browser walkthrough (live API + UI, Chromium) | 24 steps | 23 | 0 | | 1 |
| **Total automated** | **231** | **230** | **0** | **1** | **0** |

Per-test results: [evidence/08](evidence/08_backend_test_results.txt) (backend) and [evidence/09](evidence/09_frontend_test_results.txt) (frontend).

The same backend suite run against the unmodified code gave **41 failed, 157 passed** ([evidence/01](evidence/01_baseline_pytest_before_fixes.txt)). Those 41 failures were the verified defects. Code coverage was **not measured**: no coverage tool was run, and no percentage is claimed.

## Feature inventory compared with the brief

| Feature | Status | Notes |
|---|---|---|
| Citizen OTP sign-in (SMS or email) | Implemented and verified | Console delivery in development. Twilio and SMTP paths exist but were **not** tested against real providers. |
| Citizen registration (name on first sign-in) | Implemented and verified | |
| Complaint submission, validation, receipt number | Implemented and verified | Live UI and API. |
| Prevention of duplicate submissions | Implemented and verified (added by the audit) | |
| Complaint tracking, own records only | Implemented and verified | |
| Notifications and case updates to citizens | **Missing** | Updates appear only on the "My complaints" page; no SMS or email when status changes. |
| Online signing (BNSS s.173, three days) | Implemented and verified | OTP declaration. **Not** Aadhaar e-Sign or a DSC, so it has no statutory signature weight. |
| Photo OCR of a written complaint | Implemented, unverified | Runs in the browser with Tesseract.js. Not exercised: it needs a camera or file upload in the pane. |
| Evidence attachments | **Missing** | |
| Officer case access by permission | Implemented and verified | Assigned officer or admin may act; others read only. Restricted cases are redacted (added by the audit). |
| Statute prediction and confidence | **Partial** | The keyword stub (22 sections) runs. DistilBERT is **blocked** (no weights). TF-IDF + Random Forest and BiLSTM are **missing**. |
| Priority score with explanation | Implemented and verified | Includes review flags (added by the audit). |
| Unit routing and officer allocation | Implemented and verified | Checked against independent oracles. |
| Case diary, lifecycle, transfer, reassignment | Implemented and verified | |
| Officer availability, workload, capacity | Implemented and verified | |
| Runtime explanation: integrated gradients | **Blocked** | The code exists; it needs the model weights. The stub returns its matched keywords instead. |
| SHAP offline evaluation | **Missing** | |
| Admin: staff creation, activation, deactivation | Implemented and verified | |
| Admin: role and permission management | **Missing** | Roles are fixed (citizen, officer, admin), and the role cannot be changed after creation. |
| Admin: officer reassignment | Implemented and verified | |
| Admin: unit, station, routing and priority configuration | **Missing** | Configuration exists only as seed SQL; there is no API or UI. |
| Admin: identity recovery (re-point phone) | Partial | API implemented and verified; no admin UI. |
| Admin: editing capacity, availability, station | Partial | API implemented and verified; the staff UI only toggles active status. |
| Admin: audit-trail review and monitoring | Partial | Per-case activity only; no cross-case audit view or operational monitoring. |
| Multilingual input | **Missing** | Out of scope by request. |
| CCTNS integration | **Missing** | |

## Case lifecycle: transition table (derived from `workflow.TRANSITIONS`)

| From \ To | New | Under Review | Registered | Not Registered | Under Investigation | Charge Sheet Filed | Closed |
|---|---|---|---|---|---|---|---|
| New | | officer | officer¹ | officer² | ✗ | ✗ | ✗ |
| Under Review | ✗ | | officer¹ | officer² | ✗ | ✗ | ✗ |
| Registered | ✗ | ✗ | ✗ | | officer | ✗ | officer² |
| Not Registered (final) | ✗ | ✗ | ✗ | | ✗ | ✗ | ✗ |
| Under Investigation | ✗ | ✗ | ✗ | ✗ | | officer | officer² |
| Charge Sheet Filed (final) | ✗ | ✗ | ✗ | ✗ | ✗ | | ✗ |
| Closed (final) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | |

- ¹ A citizen-filed complaint also needs a confirmed signature.
- ² A note to the complainant is required.
- An administrator may move a case to any status, including reopening a final one.
- **Every one of the 42 ordered pairs** was exercised through the HTTP API as the assigned officer (`test_workflow.py::test_officer_transitions[*]`). All valid transitions returned 200. All invalid ones returned 400 and left the stored status unchanged.
- A repeated transition is rejected without writing anything.
- A stale concurrent transition is rejected with 409.
- Real two-thread races keep the audit chain consistent.

## Test catalogue by area

| ID / file | Area | Expected | Actual | Status |
|---|---|---|---|---|
| SEC-AUTHN (`test_security.py`, 24 tests) | No session, forged / `alg=none` / expired token | 401 | 401 | PASS |
| SEC-LOGIN (5 tests) | Generic error, lockout, citizen kept off the password route, hashing, login CSRF | as stated | as stated | PASS |
| SEC-OTP (8 tests) | Hash-only storage, single use, attempt lock, expiry, resend limit, staff exclusion, cap across codes, purpose binding | as stated | as stated | PASS (2 failed before the fix) |
| SEC-SESSION (6 tests) | Logout, password reset, phone recovery, deactivation, absolute lifetime, CSRF header | as stated | as stated | PASS (4 failed before the fix) |
| SEC-AUTHZ (18 tests) | Cross-citizen access, citizen → staff, officer → admin, non-assigned officer, reassignment, masking, restricted cases, role change, mass assignment | 403 / 404 / ignored | as stated | PASS (2 failed before the fix) |
| SEC-INPUT (26 tests) | SQL-injection filters, non-object JSON, wrong types, malformed JSON, 2 MB body, length bounds, Unicode / RTL / NUL characters, unknown route and method, 500 without internals, CORS | 4xx JSON / handled | as stated | PASS (15 failed before the fix) |
| SEC-HTTP (3 tests) | Headers, `no-store`, HttpOnly + SameSite cookie | as stated | as stated | PASS (2 failed before the fix) |
| SEC-ABUSE (3 tests) | Number enumeration, complaint rate limit, double-submit | as stated | as stated | PASS (3 failed before the fix) |
| DEC-PRIORITY (`test_decision_logic.py`, 17 tests) | Boundaries 3.44 / 3.45 / 3.5 / 6.44 / 6.45 / 6.5, max not mean, empty and unmapped sections, oracle × 400, basis matches score, review flags | oracle match | as stated | PASS (6 failed before the fix) |
| DEC-ROUTING (4 tests) | Victim-centric precedence, fallback, oracle over more than 500 pairs, tie determinism | oracle match | as stated | PASS (1 failed before the fix) |
| DEC-ALLOC (12 tests) | Station and unit tiers, load, busy, leave, inactive, tie on last assignment, capacity, nobody eligible, everyone over capacity | oracle match | as stated | PASS |
| DEC-CLASSIFIER (15 tests + 1 expected failure below) | Output shape and bounds for six inputs (including empty, 20k characters, Hindi), label normalisation, determinism, fallback flag, honest provenance | as stated | as stated | PASS (2 failed before the fix) |
| DEC-CLASSIFIER-NEG | Negation ("nothing was stolen") | not theft | predicted theft | **XFAIL**: known limitation of the stub, documented |
| WF-TRANSITIONS (`test_workflow.py`, 42 + 6 tests) | Transition table, admin reopen, repeat, unknown status, note required, signature before registration | as stated | as stated | PASS |
| WF-OPS (9 tests) | Audit actor, transfer reason and unit, leave redistribution, unassigned queue pickup, stale update 409, signing window, signing a closed case, signing happy path, signing does not mark the case reviewed | as stated | as stated | PASS (3 failed before the fix; the last was added after the live walkthrough found NIV-18) |
| WF-FAILURE (2 tests) | Allocation failure (no false error, no duplicate), classifier failure (nothing stored) | as stated | as stated | PASS (1 failed before the fix) |
| HARD (`test_hardening.py`, 14 tests) | Production guard ×4, revoked-session message, JSON 400/413, restricted-case readers, provenance, health on model failure, **12 concurrent filings balanced 6 / 6 with no double allocation**, concurrent audit chain | as stated | as stated | PASS |
| LEGACY (`test_legacy_scripts.py`) | The original `test_accounts.py` (55 checks) and `test_cases.py` (59 checks) | ALL PASSED, exit 0 | as stated | PASS |
| FE-API (`api.test.ts`, 5 tests) | Live mode never fabricates a case or a queue; server messages pass through; demo only without a backend; UTC timestamps | as stated | as stated | PASS (2 fail against the original code) |
| FE-UI (`components.test.tsx`, 9 tests) | Review flags shown as text, level badges, model badge, explanation tokens and labels | as stated | as stated | PASS |

The original test scripts needed three expectation changes, each caused by an intended security fix (NIV-06, NIV-14 and NIV-10). The diffs are commented in the test files.

## Manual browser walkthrough (live API on :5001, UI on :5173, Chromium)

| # | Step | Result |
|---|---|---|
| 1 | Sign-in page renders; axe scan | 1 contrast violation (footer) → fixed; re-scan 0 |
| 2 | Cyber Cell officer signs in with username | PASS (after relabelling the field "Username or official email") |
| 3 | Officer opens a Women & Child Protection case (#15) | Narrative and victim name withheld, holder shown; the audit trail **leaked the complainant's name** → fixed (NIV-01) |
| 4 | Case page axe scan after the fix | 0 violations |
| 5 | Mobile 375 px: case list | No horizontal overflow, no touch targets under 24 px, cards readable |
| 6 | Session cookie readable by scripts? | No: only `csrf_access_token` is visible; local and session storage empty |
| 7 | Sign out through the mobile menu | PASS |
| 8 | Citizen requests a code, signs in | PASS |
| 9 | Empty complaint submitted | Validation message announced (`role="alert"`) |
| 10 | Synthetic complaint filed | Reference #16 shown only after the server confirmed it |
| 11 | Same text filed again | "We already have this complaint", same #16 |
| 12 | My complaints | Five identical "Sign online instead" buttons with no context → accessible names added |
| 13 | Sign with the earlier **sign-in** code | Refused ("incorrect or has expired"): purpose binding works |
| 14 | Sign with the signature code | "Signed online", but showed "Handled by …" before any officer review → fixed (NIV-18) |
| 15 | Sign-in tabs with arrow keys | Selection, focus and `aria-labelledby` follow |
| 16 | Admin sign-in; staff page axe scan | 0 violations |
| 17 | Admin case list axe scan | 0 violations |
| 18 | New-complaint page axe scan | 0 violations |
| 19 | Officer analyses an arson narrative (no keyword) | Server stored the case with the placeholder section, **review flag set**, classifier `keyword-stub` |
| 20 | Result screen visible after analysis | **BLOCKED**: the browser pane was hidden, so animation frames stopped and the exit transition never completed. The stored record was verified instead. Re-check in a visible browser. |
| 21–24 | Desktop layout of the cases, case, file and staff pages | PASS |

## Not tested or blocked

- **Model accuracy** (macro-F1, micro-F1, precision, recall, Jaccard, rare labels): **BLOCKED**. There are no model weights and no held-out labelled test set in the repository.
- **Real SMS and email delivery:** blocked. No provider credentials; India also requires TRAI DLT registration.
- **Firefox, Safari, Edge:** not tested. Only Chromium (the built-in pane) was available.
- **Viewports:** 768 px (tablet) and 1920 px were not explicitly tested. 375 px and the pane's desktop width (about 800–1200 px) were.
- **Network interruption mid-submission in a real browser:** covered by the frontend unit test with a rejected `fetch`, not by a live network cut.
- **Backup and restore:** not tested; there is no backup procedure to test.
- **Playwright end-to-end automation and OWASP ZAP:** not set up. The browser workflows above were exercised by hand.
