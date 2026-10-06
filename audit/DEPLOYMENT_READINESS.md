# NIVARA: Deployment Readiness

**Status: ready for controlled demonstration** with synthetic data. **Not ready** for real complainant data.

## Options that need no server (recommended for a student project)

| Option | Use it for | How |
|---|---|---|
| Your laptop | The review itself | `bash scripts/dev.sh --reset`, then open http://localhost:5173 |
| GitHub Codespaces | A live demo from anywhere; full app with real logins | See [CODESPACES.md](../CODESPACES.md). Make port 5173 public only during the session. |
| GitHub Pages | An always-on shareable link | The in-browser demo, published by `.github/workflows/pages.yml` on every push to `main`. No backend, synthetic data only. |

Every page shows "Student research prototype, not an official police service. Do not report real incidents."

## Checklist if a real server becomes available

| Area | Requirement | Status |
|---|---|---|
| Environment | `NIVARA_ENV=production`; start-up refuses unsafe configuration | Implemented |
| Secrets | `NIVARA_JWT_SECRET` (48+ random characters) set in the environment, never in the repository; SMTP credentials kept the same way | Implemented (enforced); you supply the values |
| HTTPS | Reverse proxy (for example Caddy) with automatic certificates; `NIVARA_COOKIE_SECURE=1`, which also enables HSTS | Not done (no server) |
| Same origin | Serve the built frontend and proxy `/api` on one domain; build with `VITE_API_BASE_URL=/` | Supported |
| App server | gunicorn (not `python app.py`); add `gunicorn` to the requirements | Not done |
| Demo accounts | Change or deactivate them; create the first admin with `create_admin.py` (the guard refuses to start otherwise) | Enforced |
| Database | SQLite on a persistent disk is adequate for one server; file permissions 600; the folder must not be cloud-synced | Not done |
| Backups | Nightly `sqlite3 fir_system.db ".backup ..."` copied off the server; restore tested | **Missing** |
| Migrations | Applied automatically at start-up; an in-place upgrade of a pre-audit database was verified | Implemented |
| Logging and monitoring | Server logs, with codes never printed in production; an uptime check on `/api/health`, which also reports a classifier fallback | Logging implemented; uptime check not set up |
| Rate limiting | Login, codes and complaint filing are limited in the app. A proxy-level limit is recommended. Use Werkzeug `ProxyFix` behind a proxy so per-IP limits see real client addresses. | Partly implemented |
| Frontend CSP | Static hosting should send a Content Security Policy. OCR loads Tesseract assets from a CDN; self-host them first (NIV-25). | **Missing** |
| Dependencies | Pinned; `pip-audit` and `npm audit` run in CI | Implemented |
| Access control | Gate the site to invited users, for example Cloudflare Access | Not done |
| Incident response | Disable an account (ends its sessions immediately); rotate `NIVARA_JWT_SECRET` (ends all sessions); restore from backup | Mechanisms exist; no written procedure |

## Prerequisites for any real-data pilot (beyond code)

1. A working classifier with a reproducible held-out evaluation, or an explicit decision to run as a rule-based baseline.
2. Legal review: map IPC sections to the BNS, verify cognizable and bailable status, and settle the triage policy, including whether to escalate uncertain-but-grave cases.
3. DPDP Act 2023 compliance: consent, purpose limits, retention and deletion, encryption at rest.
4. Ethics approval for any study involving real narratives or officers.
5. A police partner for SMS (TRAI DLT registration), legally valid e-signature (Aadhaar e-Sign or a DSC), and CCTNS integration.
6. An independent security assessment of the deployed environment.
