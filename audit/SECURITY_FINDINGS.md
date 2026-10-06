# NIVARA: Security and Integrity Findings Register

**Audit date:** 5 October 2026 (baseline commit `60659ef`)

## Conventions

- **Severity** follows likely impact for this deployment context: police complaints, including victims of sexual offences.
- **Status values:**
  - **Fixed**: remediated, with a regression test that failed before the fix and passes after it.
  - **Mitigated**: partly addressed.
  - **Open**: not fixed.
  - **Not a vulnerability**: a scanner flag checked and found safe.
- **Tests** are under `backend/tests/suite/` (pytest) or `frontend/src/**/*.test.ts(x)` (Vitest). How to run them is in [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md).
- The **verification** for every Fixed item is the final run in [evidence/07](evidence/07_final_verification_run.txt): 216 passed, 0 failed.
- Items marked **verified in the live UI** were also seen in the running application in the browser.

---

## Verified vulnerabilities and defects

### NIV-01: Sexual-offence narratives and victim identity exposed to every officer
- **Severity:** High. **Status:** Fixed.
- **Component:** `GET /api/complaints`, `GET /api/complaints/<id>`, and the audit-trail events (`app.py`).
- **Evidence and reproduction:**
  1. A citizen files "The accused sexually assaulted the complainant…". It is routed to the Women & Child Protection Unit.
  2. A Cyber Cell officer opens the case list or the case.
  3. The full narrative and the complainant's name are shown.
  4. In the live UI, the activity log also showed "Filed — *complainant name*" after the narrative had been redacted.
- **Impact:** Identity and account of sexual-offence victims disclosed to all district officers. Disclosure is restricted by IPC s.228A / BNS s.72. The backend's behaviour also contradicted the staff page, which promised unit scoping.
- **Root cause:** The "transparency view" hid contact details only. There was no concept of a restricted case.
- **Remediation:** A case is restricted if it is routed to the Women & Child Protection Unit or a sexual-offence section is predicted (354, 375, 376, 376(2), 509, 366, 366A). Only the handling unit, the assigned officer and administrators see:
  - the narrative;
  - the complainant;
  - the explanation tokens;
  - notes and transfer reasons;
  - complainant names in the audit trail.

  Everyone else sees who holds the case and its status.
- **Regression tests:**
  - `test_security.py::test_sexual_offence_narrative_is_not_disclosed_outside_the_handling_unit`
  - `test_hardening.py::test_redacted_audit_trail_does_not_name_the_complainant`
  - `test_hardening.py::test_handling_unit_can_read_restricted_case`
  - `test_hardening.py::test_admin_can_read_restricted_case`
- **Verification:** Pass. Also verified in the live UI.
- **Residual risk:**
  - Section codes and titles remain visible, and they reveal the type of offence.
  - Restriction depends on the prediction. A sexual offence the classifier misses is not restricted.
  - Duty officers (general duty) cannot read restricted cases unless the case is allocated to them.

### NIV-02: Frontend fabricates a filed case or a queue when the backend is unreachable
- **Severity:** High (decision integrity). **Status:** Fixed.
- **Component:** `frontend/src/services/api.ts` (`classifyComplaint`, `fetchCases`).
- **Evidence:** In live mode, a network error fell through to the demo classifier. The officer saw a case number, priority and officer allocation for a complaint never sent to the server. The case list silently showed 18 synthetic cases.
- **Impact:** Officers could act on non-existent records, and a complaint could be believed filed when it was not.
- **Root cause:** Demo-mode fallback was applied whenever the backend could not be reached, not only when no backend was configured.
- **Remediation:** When a backend is configured, errors propagate with a clear message ("Nothing was saved; your text is still here"). Demo data is used only when no backend is configured.
- **Regression tests:** `frontend/src/services/api.test.ts`. Both integrity tests fail against the original `api.ts` and pass now.
- **Residual risk:** If a production build is made without `VITE_API_BASE_URL`, the app runs as an explicit demo. Pages say "Demo mode", but deployment must set the variable.

### NIV-03: Sessions could not be revoked
- **Severity:** High. **Status:** Fixed.
- **Component:** `auth.py`, `db.py`.
- **Evidence and reproduction:**
  1. Copy the session cookie.
  2. Sign out, or have an administrator reset the password or re-point the phone number.
  3. Replay the copied cookie: `/api/auth/me` still returned 200.

  Each sliding renewal issued a fresh 60-minute token, with no absolute limit.
- **Impact:** A stolen token stays valid after logout or a password reset. Recovering a lost SIM does not evict whoever holds the old session.
- **Root cause:** The JWTs were stateless, with no check against a server-side record.
- **Remediation:**
  - Each user has a `token_version`, bumped on a password change, an active-status change, or a phone change.
  - Logged-out token IDs go in a `revoked_tokens` table.
  - An `auth_time` claim enforces a 12-hour absolute lifetime.
  - All three are checked by `token_in_blocklist_loader`.
- **Regression tests:**
  - `test_logout_revokes_the_session_token`
  - `test_password_reset_revokes_existing_sessions`
  - `test_admin_phone_recovery_revokes_existing_sessions`
  - `test_session_has_an_absolute_lifetime`
  - `test_revoked_session_gets_a_clear_message`
- **Residual risk:** Tokens issued before the upgrade lack the new claims and are rejected, so everyone must sign in again once. This is the intended effect.

### NIV-04: Stale concurrent updates overwrite newer case state
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `PATCH /api/complaints/<id>`, `db.review_complaint`.
- **Evidence:** The officer reads a case at "New". An administrator then sets it to "Not Registered", a final status. The officer's request, still based on "New", sets it to "Registered", and the update succeeded. Under a real two-thread race, the audit chain recorded two transitions out of the same state.
- **Root cause:** The update validated against data read earlier and wrote without checking that the row was unchanged.
- **Remediation:** Compare-and-set: the update only applies if `status` and `assigned_to` still match what was read. Otherwise it returns 409 and asks the user to reload.
- **Regression tests:**
  - `test_workflow.py::test_stale_update_cannot_overwrite_a_newer_status`
  - `test_hardening.py::test_concurrent_status_changes_keep_a_consistent_audit_chain` (real threads)

### NIV-05: One-time codes not bound to their purpose; unlimited guesses across codes
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `auth.py` (`issue_code`, `check_code`, `/otp/verify`), the `login_codes` table.
- **Evidence:**
  - A sign-in code was accepted to sign a complaint.
  - The limit of 5 attempts applied per code, and requesting a fresh code reset it.
  - Verified in the live UI: the earlier sign-in code was refused as a signature.
- **Remediation:**
  - A `purpose` column, and the purpose included in the HMAC.
  - At most 15 wrong guesses per address in 6 hours across all codes, cleared on success.
- **Regression tests:**
  - `test_sign_in_code_cannot_be_used_to_sign_a_complaint`
  - `test_otp_verification_failures_are_capped_across_codes`
  - plus the existing single-use, expiry and attempt-lock tests
- **Residual risk:** An attacker can lock a citizen out for up to 6 hours by deliberately entering wrong codes for that citizen's number (denial of service). This is the accepted trade-off.

### NIV-06: Enumeration of complainants' phone numbers
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `POST /api/auth/phone/change/request`.
- **Evidence:** It returned 409 "already registered" for numbers in use, and the existence check ran before rate limiting.
- **Impact:** Any citizen account could test whether a given person has filed police complaints.
- **Remediation:** Rate limit first, then give the same reply in both cases. No code is sent to a number in use, and verifying it fails with the generic error.
- **Regression test:** `test_number_change_does_not_reveal_registered_numbers`. The original suite's check was updated to expect the new behaviour.

### NIV-07: Production configuration fails open
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `auth.py`, `app.py`, `.env.example`.
- **Evidence:**
  - With no SMTP or SMS configured, one-time codes were printed to stdout, and therefore to logs, in any environment.
  - The JWT secret was silently auto-generated.
  - `.env.example` set `FLASK_DEBUG=1`, which exposes the Werkzeug debugger and allows code execution.
  - Demo accounts with published passwords could go live.
- **Remediation:** With `NIVARA_ENV=production`:
  - console delivery of codes raises an error and the API returns 502;
  - a missing secret stops start-up;
  - `production_problems()` refuses to start with a short secret, `NIVARA_COOKIE_SECURE` unset, the debugger on, no delivery channel, or demo credentials still active.

  `.env.example` now sets the debugger off.
- **Regression tests:**
  - `test_production_never_prints_codes`
  - `test_production_requires_an_explicit_jwt_secret`
  - `test_production_refuses_demo_credentials_and_unsafe_settings`
  - `test_production_configuration_with_everything_set_has_no_problems`

### NIV-08: Missing HTTP hardening
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `app.py`.
- **Evidence:**
  - No `X-Content-Type-Options`, frame protection, CSP, or `Referrer-Policy`.
  - No `Cache-Control` on case data.
  - No request body limit: a 2 MB body was parsed before being rejected.
  - Unhandled errors returned Flask's HTML error page.
- **Remediation:**
  - Security headers on every response (`default-src 'none'; frame-ancestors 'none'` for this JSON API).
  - `Cache-Control: no-store` on `/api/`.
  - HSTS when cookies are marked Secure.
  - `MAX_CONTENT_LENGTH` of 256 KiB.
  - JSON handlers for all HTTP errors and unexpected exceptions; the details are logged on the server only.
- **Regression tests:**
  - `test_security_headers_are_set`
  - `test_personal_data_responses_are_not_cached`
  - `test_oversized_request_body_is_refused`
  - `test_unexpected_server_error_hides_internals`
  - `test_unknown_route_and_method_return_json`
- **Residual risk:** The frontend's static hosting needs its own CSP. Vite's dev server sends none. See [DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md).

### NIV-09: Online signing outside the BNSS s.173 window
- **Severity:** Medium (legal workflow integrity). **Status:** Fixed.
- **Component:** `/api/complaints/<id>/sign/request`, `/sign`, and `citizen_view`.
- **Evidence:** Signing was accepted 4 days after filing, and after the case was closed. The citizen page showed "the signing window closed" right next to a working "Sign online" button.
- **Remediation:** A single `_can_sign_online()` rule enforces the three-day window, an open status, and that the case is not already signed. It drives both endpoints and the `can_sign_digitally` flag.
- **Regression tests:**
  - `test_digital_signature_is_refused_after_the_three_day_window`
  - `test_closed_complaint_cannot_be_signed_online`
  - `test_online_signature_happy_path`

### NIV-10: A filing reported as failed was actually saved; double submits created duplicates
- **Severity:** Medium. **Status:** Fixed.
- **Component:** `process_complaint`, `/api/classify`.
- **Evidence:**
  - If `db.allocate` raised after `save_complaint` had committed, the API returned 500 "Classification failed. Please try again", and the complaint persisted.
  - Submitting the same text twice created two cases.
- **Remediation:**
  - An allocation failure is logged and the case is left in the unassigned queue.
  - An identical text from the same user within 10 minutes returns the existing case, marked `duplicate`. Verified in the live UI.
  - A classifier failure still stores nothing.
- **Regression tests:**
  - `test_allocation_failure_does_not_report_a_filed_complaint_as_failed`
  - `test_classifier_failure_stores_nothing`
  - `test_accidental_double_submission_creates_one_complaint`

### NIV-11: Model provenance misreported on fallback
- **Severity:** Medium (decision integrity). **Status:** Fixed.
- **Component:** `classifier.py`, `app.py`.
- **Evidence:** With `FIR_USE_MODEL=1` and the model failing to load, the stub produced every prediction while the API reported `model_backend: "distilbert"`.
- **Remediation:**
  - `predict_with_backend()` returns the name of the classifier that actually ran ("keyword-stub (DistilBERT unavailable)" on fallback).
  - The name is stored with each case (`complaints.model_backend`).
  - It is shown in the UI, and on `/api/health`.
  - Explanations come from the same classifier as the predictions.
- **Regression tests:** `test_model_failure_is_reported_honestly`, `test_health_reports_a_failed_model`, `test_backend_and_flags_are_stored_with_the_case`.

### NIV-12: Uncertain triage passed silently as routine
- **Severity:** Medium (decision support). **Status:** Mitigated.
- **Component:** `scoring.py`, `classifier.py`, `PriorityCard`.
- **Evidence:**
  - A narrative with no recognised keyword, for example arson, returned a placeholder "323 Voluntarily causing hurt" at Low 0.8, indistinguishable from a real prediction.
  - A rape prediction at 36% confidence scores Medium.
- **Remediation:** Without changing the score formula, `review_flags()` marks these cases "Officer review needed", with plain reasons. It covers:
  - fallback predictions;
  - unmapped sections;
  - severity ≥ 9 offences that are not High.

  Flags are stored and displayed. Verified in the live UI and in the stored record (case #17, the arson narrative).
- **Regression tests:**
  - `test_low_confidence_serious_offence_is_flagged_for_review`
  - `test_unmapped_section_is_flagged_for_review`
  - `test_unrecognised_narrative_is_marked_as_a_fallback`
  - `components.test.tsx` (PriorityCard)
- **Residual risk:** The score still drops as confidence drops. Escalating uncertain grave cases automatically is a research-design change left to the team.

### NIV-13: Non-object JSON or wrongly typed fields crash endpoints
- **Severity:** Low. **Status:** Fixed.
- **Evidence:**
  - `[1,2]`, `"x"` or `42` posted to `/api/classify`, `/api/auth/login` or `/api/auth/otp/request` returned 500 (`AttributeError`).
  - A `complaint_text` that was a number, object, list or boolean also returned 500.
- **Remediation:** `json_object()` and `text_field()` helpers on every endpoint; a wrongly typed field gives a 400 with a message.
- **Regression tests:** `test_non_object_json_is_a_client_error` (9 cases), `test_wrongly_typed_fields_are_a_client_error` (4 cases), `test_responses_are_json_for_client_errors`.

### NIV-14: Weak masking of contact details
- **Severity:** Low. **Status:** Fixed.
- **Evidence:** The phone number was masked as `+91900000****`, revealing 8 of its 12 characters.
- **Remediation:** Only the country code and the last two digits are shown; email shows its first character and the domain.
- **Regression test:** `test_read_only_view_masks_contact_and_hides_diary`. The original suite's check was updated.

### NIV-15: Login timing could reveal whether a username exists
- **Severity:** Low. **Status:** Mitigated (not measured).
- **Evidence:** The code computed a password hash only for existing users, so responses for unknown usernames were faster.
- **Remediation:** A dummy hash is now checked when the user is unknown. Response timing was not statistically measured.

### NIV-16: Priority rounding inconsistent at exact half values
- **Severity:** Low. **Status:** Fixed.
- **Evidence:** 5.0 × 0.69 = 3.45 exactly, but binary floating point gives 3.4499999999999997, which rounds to 3.4 (Low). Meanwhile 10 × 0.645 rounds up to 6.5 (High). The priority level at a threshold depended on floating-point artefacts.
- **Remediation:** The product is computed in decimal and rounded half-up. The formula and thresholds are unchanged.
- **Regression tests:** `test_exact_half_way_scores_round_the_same_way`, and `test_scoring_matches_oracle_on_every_seeded_section` (100 sections × 4 confidences against an independent oracle).

### NIV-17: Routing ties depended on database row order
- **Severity:** Low. **Status:** Fixed.
- **Remediation:** A final tie-break on section code. The precedence rules are unchanged.
- **Regression tests:** `test_routing_ties_do_not_depend_on_rule_order`, and `test_routing_matches_oracle_for_every_pair_of_seeded_sections` (more than 500 pairs).

### NIV-18: Signing online marked the citizen as the case's reviewer
- **Severity:** Low. **Status:** Fixed (found in the live UI walkthrough).
- **Evidence:** After the citizen signed, `reviewed_by` was set to the citizen. The citizen's page then showed "Handled by …" before any officer had reviewed the case.
- **Remediation:** `review_complaint(…, mark_reviewed=False)` for signing.
- **Regression test:** `test_signing_does_not_count_as_an_officer_review`.

### NIV-19: No limit on complaint submissions
- **Severity:** Low. **Status:** Fixed.
- **Remediation:** Per hour: 5 complaints per citizen account, 60 per staff account. Duplicates don't count toward the limit. The error message points to the police station and to 112.
- **Regression test:** `test_citizen_complaint_submissions_are_rate_limited`.
- **Residual risk:** The limit is per account. A determined spammer can create many citizen accounts if they control many phone numbers.

### NIV-20: JWT secret handling
- **Severity:** Low. **Status:** Mitigated.
- **Evidence:**
  - `backend/.jwt_secret` was created with mode 644, readable by other local users.
  - The earlier audit's distribution zip (`fir-routing-system-audited.zip`) contained `backend/.jwt_secret`.
  - The project folder syncs to iCloud, which produced a conflict copy, `.jwt_secret 2`.
- **Remediation:**
  - New secret files are created with mode 600, and the existing ones were changed to 600.
  - `.gitignore` covers `backend/.jwt_secret*`.
  - Production requires `NIVARA_JWT_SECRET`.
- **Residual risk:** Delete the stray `.jwt_secret 2`, and don't distribute zips of the working folder. Move real deployments off the synced Desktop.

### NIV-21: The original test scripts exited 0 on failure
- **Severity:** Low (process). **Status:** Fixed.
- **Remediation:** They now call `sys.exit(1)` on failure and run inside pytest (`test_legacy_scripts.py`) against isolated databases.

### NIV-22: The model loader could silently download from the Hugging Face Hub
- **Severity:** Low. **Status:** Fixed. Found by Bandit as B615.
- **Remediation:** `from_pretrained(..., local_files_only=True)`.

### NIV-23: Vitest 3 dev-dependency advisory (introduced during this audit)
- **Severity:** Low. **Status:** Fixed.
- **Evidence:** npm audit reported 2 moderate advisories (GHSA "Path Traversal via @vitest/mocker redirect mock").
- **Remediation:** Upgraded to `vitest@5.0.3`; `npm audit` now reports 0.

### NIV-24: Frontend posted complaint photos to a non-existent `/api/scan`
- **Severity:** Informational. **Status:** Fixed.
- **Remediation:** Text extraction (OCR) is explicitly done in the browser only; the photo never leaves the device. The UI copy says so.

### NIV-25: OCR engine assets loaded from a third-party CDN at runtime
- **Severity:** Informational. **Status:** Open.
- **Detail:** Tesseract.js fetches its worker, its WebAssembly core and the English language data from a public CDN when OCR first runs. This is a supply-chain dependency, and the frontend's CSP would have to allow it.
- **Recommendation:** Self-host the Tesseract assets.

### NIV-26: Unpinned dependencies
- **Severity:** Informational. **Status:** Fixed.
- **Remediation:** `backend/requirements.txt` is pinned to the tested versions, with `requirements-dev.txt` for the tools. The frontend lockfile was already present.

---

## Scanner flags reviewed and found not vulnerable

| Tool / rule | Count | Where | Assessment |
|---|---|---|---|
| Bandit B608 (SQL built from strings) | 14 | `db.py` | Interpolation is only `?` placeholder lists, or column names from fixed allow-lists (`review_complaint`, `update_user`, the `_COMPLAINT_COLUMNS` migration). Values are always bound parameters. SQL-injection payloads in filters are covered by `test_query_filters_are_not_injectable`. |
| Bandit B310 (`urlopen`) | 1 | `auth.py` Twilio call | A fixed `https://api.twilio.com` URL. The only variable part is the account SID from server configuration; no user input. |
| Bandit B105 (hardcoded password) | 2 | `db.py`, `seed_demo.py` | One is a SQL type string. The other is the demo password, which is intentionally published for local demos; production start-up refuses while it is active. |
| Ruff S603 (subprocess) | 1 | test runner | It runs the project's own scripts with fixed arguments. |

## Verified as not vulnerable (attack tests that pass)

- **Unauthenticated access:** all 21 protected endpoints return 401.
- **Forged tokens:** forged, `alg=none` and expired JWTs are rejected.
- **Login:** identical responses for an unknown user and a wrong password; lockout after 5 failures; citizens cannot use the password route.
- **Login CSRF:** blocked by the JSON content-type requirement plus restricted CORS.
- **CSRF:** a missing `X-CSRF-TOKEN` on a state-changing request is refused.
- **CORS:** arbitrary origins are not reflected.
- **Horizontal access:** a citizen cannot read or sign another citizen's complaint.
- **Vertical access:**
  - citizens cannot use staff endpoints;
  - officers cannot use admin endpoints, act on cases allocated to someone else, or reassign cases;
  - the role cannot be changed through the staff update endpoint.
- **Mass assignment:** client-supplied priority, routing, owner, assignee or status in `/api/classify` is ignored.
- **Data shown to citizens:** citizens never receive model predictions, priority or routing.
- **Passwords:** stored as scrypt hashes.
- **OTP:** stored only as an HMAC; single-use; expires; resending is rate-limited; staff addresses never receive codes.
- **Browser storage:** in the live app, the session cookie is HttpOnly (only the CSRF cookie is visible to scripts), and nothing is kept in `localStorage` or `sessionStorage`.

## Not tested

- OWASP ZAP or other dynamic scanning.
- TLS configuration (there is no HTTPS deployment).
- Container or host hardening (no containers).
- Response-timing side channels (not measured).
- Abuse at internet scale.
- Model-specific attacks such as prompt or text manipulation to game priority. The keyword stub is trivially gameable by adding trigger words. A real model would need its own adversarial evaluation.
