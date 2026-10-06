# NIVARA: Executive Security, Reliability and Readiness Report

**Audit date:** 5 October 2026
**Scope:** `fir-routing-system` (Flask API, React/TypeScript frontend, SQLite), audited on a local development machine with synthetic data only
**Baseline:** the unmodified GitHub snapshot (git commit `60659ef`), plus an earlier, narrower audit pass (`7b971d8`)

## Readiness classification

**Ready for controlled demonstration.** It is **not** suitable for a restricted pilot with real complainants yet. The reasons are in "Deployment blockers" below.

NIVARA is not production-ready. Passing tests show only that the behaviours under test work. They do not show that the system is secure in a deployment that has not been built or reviewed.

## What NIVARA is, as implemented

A citizen or an officer submits a complaint narrative. The backend then:

1. predicts Indian Penal Code sections;
2. scores priority as `max(statutory severity × confidence)`;
3. routes the case to a police unit using a victim-centric rule table;
4. allocates the least-loaded suitable officer;
5. tracks the case through a lifecycle that the server enforces, with an audit trail and a case diary.

There are three portals: citizen, officer and administrator.

**The classifier that runs is a keyword stub covering 22 sections.** The DistilBERT fine-tune that the documentation describes cannot run, because its weights are not in the repository. The TF-IDF + Random Forest model, the BiLSTM and the SHAP evaluation are not in the repository at all. No model-accuracy figure can be reproduced from this code.

## Most serious verified vulnerabilities (all fixed, with regression tests)

| ID | Severity | Issue |
|---|---|---|
| NIV-01 | High | Every officer could read the full narrative and the victim's name for sexual-offence and Women & Child Protection cases, in the case list, the case view and the audit trail. IPC s.228A / BNS s.72 restrict disclosure of a sexual-offence victim's identity. |
| NIV-02 | High | When the backend was unreachable, the officer UI showed a **fabricated case number and officer allocation** for a complaint that was never saved, and filled the case queue with synthetic records. |
| NIV-03 | High | Sessions could not be revoked. A stolen token survived logout, a password reset, deactivation followed by reactivation, and phone-number recovery. Sliding renewal kept a session alive indefinitely. |
| NIV-04 | Medium | Two people acting on the same case at once could overwrite a newer or final status, using stale data. This left the audit trail inconsistent. |
| NIV-05 | Medium | One-time codes were not bound to their purpose (a sign-in code could sign a complaint), and guesses were unlimited across freshly requested codes. |
| NIV-06 | Medium | Any signed-in citizen could find out which phone numbers belong to people who have filed police complaints. |
| NIV-07 | Medium | Misconfiguration failed open: one-time codes were printed to logs when SMTP or SMS was not configured, `.env.example` turned the Werkzeug debugger on, and nothing stopped a launch with demo accounts still active. |
| NIV-08 | Medium | There were no security headers, no `no-store` caching on personal data, no limit on request size (bodies of 2 MB or more were parsed), and errors came back as HTML pages. |
| NIV-09 | Medium | Online signing was accepted after the three-day window in BNSS s.173 and on closed cases. |
| NIV-10 | Medium | If allocation failed after a complaint was saved, the user was told "failed, try again", so retrying created a duplicate. Double submissions were not deduplicated. |

The full register has 26 entries: [SECURITY_FINDINGS.md](SECURITY_FINDINGS.md).

## Fixes implemented

- **Sessions:** revocation on the server (a per-user token version plus a list of revoked tokens), and a 12-hour absolute session lifetime.
- **One-time codes:** bound to their purpose, with a cap on wrong guesses per address that requesting a new code does not reset.
- **Restricted cases:** sexual-offence and Women & Child Protection narratives, complainant details and complainant names in the audit trail are visible only to the handling unit, the assigned officer and administrators.
- **Concurrent edits:** case updates are compare-and-set, so a request working from stale data gets HTTP 409 and nothing is overwritten.
- **Filing:**
  - an identical complaint resubmitted by the same person within 10 minutes returns the existing record;
  - complaint filing is rate-limited;
  - an allocation failure leaves the case in the unassigned queue instead of reporting failure.
- **HTTP hardening:** security headers, `no-store`, a 256 KiB request limit, type-checked request fields, and JSON error responses that reveal no internals.
- **Production mode (`NIVARA_ENV=production`):** the server refuses to start with unsafe settings or with demo accounts still on their published passwords, and never prints codes.
- **Decision support:**
  - the classifier that actually produced each prediction is recorded and shown, so a fallback is named as one;
  - unrecognised narratives, and grave offences predicted with low confidence, are flagged "Officer review needed";
  - priority scores are rounded exactly at the thresholds;
  - ties in routing are broken deterministically.
- **Frontend integrity:** no fabricated data in live mode, and the progress display is tied to the real request.
- **Accessibility:** WCAG fixes for contrast, focus management, tab semantics, field descriptions and control names. Detail: [UX_ACCESSIBILITY_REPORT.md](UX_ACCESSIBILITY_REPORT.md).

## Evidence

| Check | Result |
|---|---|
| Backend tests (pytest; this includes the project's original 55 + 59 end-to-end checks) | **216 passed, 1 expected failure (a documented stub limitation), 0 failed** |
| The same suite before any fix | 41 failed, 157 passed ([evidence/01](evidence/01_baseline_pytest_before_fixes.txt)) |
| Frontend tests (Vitest + Testing Library) | 14 passed |
| TypeScript check and production build | 0 errors; build succeeds |
| axe-core WCAG 2.2 AA scan, live app: sign-in, case list, case detail, new complaint and staff pages | one violation found (footer contrast), fixed; 0 after the fix |
| Bandit | 19 flags triaged: 1 real one (Hub download fallback) fixed; the rest false positives (see the findings register) |
| pip-audit and npm audit | 0 known vulnerabilities, after upgrading Vitest |
| Secret scan (git history and production bundle) | no secrets found |
| Latency, local dev server, 8 concurrent clients | read endpoints p95 of 10–28 ms; filing pipeline about 2 ms (keyword stub only) |

All commands and their raw output are in [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) and in [`evidence/`](evidence/).

## Outstanding risks

1. **The research claim is not demonstrated.** The predictor is a keyword stub with no measured accuracy. It mishandles negation ("nothing was stolen" is still predicted as theft) and gives a placeholder section to offences it has no keyword for, such as arson. Those cases are now flagged, not hidden.
2. **The legal basis is outdated and unverified.** The system is built on the IPC, which the BNS replaced on 1 July 2024. The cognizable and bailable values are unverified against the First Schedule. Some sections the seed file calls "definitional" (299, 300, 375) carry high weights, contradicting its own rubric.
3. **The priority formula demotes uncertainty.** A grave offence predicted with low confidence still scores Medium; the new flag only tells the officer to look. Whether to escalate such cases automatically is a research decision for the team (see [COUNCIL_VERDICT.md](COUNCIL_VERDICT.md)).
4. **Data protection is not implemented.**
   - No encryption at rest.
   - No retention or deletion policy.
   - No consent records, as the DPDP Act 2023 would require.
   - The project folder is on an iCloud-synced Desktop, so the database and the JWT secret sync to the cloud.
5. **No production infrastructure:** no HTTPS deployment, no WSGI server, no backups, no monitoring or alerting, and no real SMS (sending to Indian numbers requires TRAI DLT registration). SQLite is adequate only for a single-node pilot.
6. **Features missing compared with the brief:**
   - administrator management of routing rules, units and stations;
   - role and permission management (roles are fixed);
   - a cross-case audit-log viewer;
   - an admin screen for identity recovery (the API exists);
   - notifications to citizens;
   - evidence attachments;
   - languages other than English;
   - CCTNS integration;
   - a legally valid e-signature: the OTP declaration is not Aadhaar e-Sign.

## Deployment blockers (before any real complainant data)

- An actual classifier, with reproducible held-out evaluation, or an explicit, documented decision to run as a rule-based baseline.
- A legal review of the section table (IPC → BNS mapping, cognizable and bailable status) and of the triage policy.
- A DPDP Act 2023 assessment, encryption at rest, a retention policy, and ethics approval for any study that involves real narratives or officers.
- HTTPS behind a reverse proxy, a production WSGI server, secrets managed outside the repository, backups, and monitoring, as listed in [DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md).
- An independent security assessment of the deployed environment.

## Limitations of this audit

- The full research paper draft was not available. Only the literature review and research-gap chapters were found, so the requirements were taken from the brief.
- Model behaviour could not be tested beyond the stub, because the DistilBERT weights are missing. The metrics the paper describes (macro-F1, micro-F1, Jaccard) are therefore **BLOCKED**.
- Testing was done in Chromium only (the built-in browser pane). Firefox, Safari and Edge were not tested.
- No OWASP ZAP scan was run, and no Playwright end-to-end suite was written. Browser workflows were exercised by hand in the live app.
- The result screen of the officer analysis page could not be confirmed visually at the end, because the browser pane was hidden and stopped rendering frames. The stored record was verified instead.
- The performance numbers are from a local development server and are not production guarantees.
