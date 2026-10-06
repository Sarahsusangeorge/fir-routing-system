#!/usr/bin/env bash
# Start the full NIVARA app (API + web) for a demo, in Codespaces or locally.
#   bash scripts/dev.sh           start with the existing demo data
#   bash scripts/dev.sh --reset   wipe and reseed the synthetic demo data first
# Open port 5173. Citizen sign-in codes are printed in this terminal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$ROOT/backend/venv" ] && [ -d "$ROOT/frontend/node_modules" ] || bash "$ROOT/scripts/setup.sh"

cd "$ROOT/backend"
if [ "${1:-}" = "--reset" ] || [ ! -f fir_system.db ]; then
  rm -f fir_system.db fir_system.db-wal fir_system.db-shm
  ./venv/bin/python seed_demo.py | tail -1
fi

NIVARA_PORT=5001 ./venv/bin/python app.py &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT INT TERM

cd "$ROOT/frontend"
echo
echo "NIVARA is starting. Open the web app on port 5173."
echo "Demo staff logins are listed in backend/README.md; citizen codes appear below."
echo
VITE_API_BASE_URL=/ npx vite --port 5173 --strictPort
