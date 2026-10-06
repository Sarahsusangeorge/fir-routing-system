# NIVARA: Remediation Changelog

**Baseline:** `60659ef`, the unmodified GitHub snapshot. Every change below is in git history; run `git log --stat` for exact diffs. Finding IDs refer to [SECURITY_FINDINGS.md](SECURITY_FINDINGS.md); A-numbers refer to [UX_ACCESSIBILITY_REPORT.md](UX_ACCESSIBILITY_REPORT.md).

## Commits in order

| Commit | What changed |
|---|---|
| `7b971d8` | Earlier audit pass: Werkzeug debugger off by default; `BEGIN IMMEDIATE` around officer allocation (race fix); first reports. |
| `5ff7424` | Isolated pytest suite added. **41 tests failed against the code at this point**, recorded in `evidence/01`. `NIVARA_DB_PATH` lets tests use temporary databases. |
| `72ce2e9` | Backend security and integrity fixes (NIV-01, 03–17, 19–21). |
| `a49ccaa` | Frontend integrity, accessibility and usability fixes, plus Vitest tests (NIV-02, NIV-24, A2–A4, A8–A11, A13–A16). |
| `391b79e` | Fixes found in the live UI walkthrough: complainant name withheld from the restricted audit trail (NIV-01), footer contrast (A1), staff sign-in label (A12), configurable API port. |
| `ad16ee9` | Signing no longer marks the case reviewed (NIV-18); WAI-ARIA tabs (A5), field hints (A6), button names (A7); local-only model loading (NIV-22); Vitest upgrade (NIV-23); pinned requirements (NIV-26); evidence files. |
| `5432576` | Audit reports and per-test evidence. |
| `4b03352` | Running on GitHub without a server: Codespaces dev container, `scripts/setup.sh` and `scripts/dev.sh`, CI and Pages workflows, same-origin API mode, prototype notice. |
| (this commit) | Root README, updated backend and test READMEs, rewritten changelog and deployment checklist. |

## Files changed and why

### Backend

- **`app.py`**
  - Security headers and `no-store` caching; 256 KiB body limit; JSON error handlers (NIV-08).
  - Production start-up guard, `production_problems()` (NIV-07).
  - Restricted-case redaction, `is_restricted` and `_redact`, including complainant names in the audit trail (NIV-01); stronger contact masking (NIV-14).
  - Compare-and-set case updates returning 409 (NIV-04).
  - Signing rules, `_can_sign_online` (NIV-09).
  - Duplicate-submission check and complaint rate limit (NIV-10, NIV-19); allocation failure leaves the case unassigned (NIV-10).
  - Type-checked request fields (NIV-13).
  - Model provenance and review flags in the pipeline (NIV-11, NIV-12).
  - `NIVARA_PORT`; debugger never on in production.
- **`auth.py`**
  - Session revocation (token version, revoked tokens, 12-hour absolute lifetime) (NIV-03).
  - One-time codes bound to their purpose, with a guess cap across codes (NIV-05).
  - Console delivery of codes refused in production; explicit secret required in production; secret file created with mode 600 (NIV-07, NIV-20).
  - Phone-change requests answer identically whether or not the number is in use (NIV-06).
  - Dummy password-hash check for unknown usernames (NIV-15).
  - `json_object()` and `text_field()` input helpers (NIV-13).
- **`db.py`**
  - New columns, migrated in place: `token_version`, `login_codes.purpose`, `complaints.model_backend`, `complaints.review_flags`; new `revoked_tokens` table.
  - `Conflict` exception and guarded `review_complaint` (with `mark_reviewed`).
  - `find_recent_duplicate`; token-version bump on password, active-status and phone changes.
  - Database path overridable with `NIVARA_DB_PATH`.
- **`schema_auth.sql`**: the same columns and table for new databases.
- **`scoring.py`**: exact decimal rounding (NIV-16); `review_flags()` (NIV-12). The formula and thresholds are unchanged.
- **`routing.py`**: deterministic tie-break on section code (NIV-17). The rules are unchanged.
- **`classifier.py`**:
  - `predict_with_backend()` reports which classifier actually ran (NIV-11);
  - fallback predictions are marked;
  - explanations come from the same classifier as the predictions;
  - `local_files_only=True` (NIV-22).
- **`admin.py`**: type-checked fields; booleans rejected as capacity.
- **`requirements.txt`**: pinned; plus a new `requirements-dev.txt` for the tools (NIV-26).
- **`.env.example`**: debugger off; `NIVARA_ENV`, `NIVARA_PORT` and `SMS_PROVIDER` documented.
- **`tests/`**:
  - a new `suite/` containing 217 pytest tests;
  - `test_accounts.py` and `test_cases.py` exit non-zero on failure (NIV-21), with three expectations updated for intended behaviour changes (NIV-06, NIV-10, NIV-14).

### Frontend

- **`services/api.ts`**: no demo fallback when a backend is configured (NIV-02); phone-change response updates the CSRF token.
- **`services/http.ts`**: `VITE_API_BASE_URL=/` selects a same-origin API.
- **`services/ocr.ts`**: OCR runs in the browser only (NIV-24).
- **`pages/AnalyzePage.tsx` and `components/AnalysisProgress.tsx`**: progress tied to the real request; focus moves to the result; duplicate and unassigned outcomes are explained (A2).
- **`components/PriorityCard.tsx`, `ModelBadge.tsx` (new), `AnalysisHeader.tsx`, `pages/CasePage.tsx`**: review flags, classifier badge, restricted-case notice, decision-support wording (A13).
- **`components/ComplaintScanner.tsx`**: focus trap and focus return; privacy wording (A3, A16).
- **`components/ExplainabilityViewer.tsx`**: correct semantics and labels for highlighted words (A4).
- **`pages/LoginPage.tsx`**: tabs pattern, `aria-describedby` hints, username field, prototype notice (A5, A6, A12).
- **`pages/FileComplaintPage.tsx`, `pages/MyComplaintsPage.tsx`, `pages/StaffPage.tsx`**: duplicate message, signing copy, per-complaint button names, deactivation confirmation, truthful access copy (A7–A9, A11, A15).
- **`components/Footer.tsx`, `components/RoutingCard.tsx`**: contrast and wording (A1, A10).
- **`vite.config.ts`**: `/api` proxy and Codespaces host allow-list.
- **Tests (new):** `vitest.config.ts`, `services/api.test.ts`, `components/components.test.tsx`.

### Repository

- `.gitignore`: `backend/.jwt_secret*` and SQLite WAL files.
- New: `.devcontainer/`, `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, `scripts/setup.sh`, `scripts/dev.sh`, `CODESPACES.md` and `README.md`.

## Behaviour changes to know about

| Change | Effect |
|---|---|
| Session tokens carry new claims | Everyone must sign in again once after upgrading. |
| Phone-change request for a number already in use | Returns 200 with a generic message and sends no code (previously 409). |
| Identical complaint within 10 minutes from the same person | Returns the existing case (`duplicate: true`) instead of creating a new one. |
| Complaint filing limits | 5 per hour per citizen, 60 per hour per staff account. |
| Officers outside the handling unit | Can no longer read restricted cases' narratives or complainant names. |
| Online signing | Refused after three days or once the case is closed. |
| Priority scores exactly half-way, such as 3.45 | Now round up consistently. This can change the displayed level only for these exact half-way products. |

## Not changed (deliberately)

- The research logic: severity weights, priority thresholds and the formula; routing precedence; allocation ranking; the keyword stub's patterns.
- The IPC section table. Mapping to the BNS and verifying the values needs a legal review, not a code change.
