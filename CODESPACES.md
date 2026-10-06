# Running NIVARA on GitHub (no server needed)

NIVARA is a student research prototype, not an official police service. Use made-up data only.

## Full app in GitHub Codespaces (for live demos)

1. On the repository page, choose **Code → Codespaces → Create codespace on main**.
   Setup runs automatically the first time (a few minutes).
2. In the terminal, run:

   ```bash
   bash scripts/dev.sh
   ```

   Add `--reset` to start from fresh demo data.
3. Open the **Ports** tab and click the globe icon for port **5173**.
   The app opens in a new tab.
4. Sign in:
   - **Staff:** the demo usernames and passwords in `backend/README.md` (for example `admin`).
   - **Citizen:** mobile `9000000001`. The 6-digit code appears in the terminal.
5. To let a reviewer open it from their own device, right-click port 5173 and choose **Port Visibility → Public**.
   Set it back to Private afterwards.
6. Stop the codespace when you finish (**Codespaces → Stop**), so you don't use up your free hours.
   Data stays until you delete the codespace.

The browser only ever talks to port 5173. The web server forwards `/api` to the backend inside the codespace, so logins work without any cross-site cookie setup.

## Shareable demo link on GitHub Pages (always on)

1. In **Settings → Pages**, set **Source** to **GitHub Actions**.
2. Every push to `main` publishes the demo to `https://<your-username>.github.io/<repo-name>/`.

This version runs entirely in the browser with synthetic cases and a role picker. It has no real logins, backend or saved data, and every page says "Demo mode".

## Automatic checks

Every push runs the backend and frontend tests, the production build and dependency audits (`.github/workflows/ci.yml`). Results appear under the **Actions** tab.
