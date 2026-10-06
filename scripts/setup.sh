#!/usr/bin/env bash
# One-time setup: backend virtual environment, frontend packages, demo data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# The pinned dependencies need Python 3.10 or newer; macOS's built-in python3 is 3.9.
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "NIVARA needs Python 3.10 or newer (3.12 recommended). Install it, e.g. 'brew install python', then re-run." >&2
  exit 1
fi

cd "$ROOT/backend"
if [ ! -d venv ]; then
  "$PYTHON" -m venv venv
fi
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements-dev.txt
if [ ! -f fir_system.db ]; then
  ./venv/bin/python seed_demo.py > /dev/null
fi

cd "$ROOT/frontend"
npm ci --no-audit --no-fund

echo "Setup done. Start NIVARA with: bash scripts/dev.sh"
