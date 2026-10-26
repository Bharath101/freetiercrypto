#!/usr/bin/env bash
# Build the site locally and serve it at http://localhost:8000/
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q -r requirements.txt
SITE_URL="${SITE_URL:-http://localhost:8000}" .venv/bin/python scripts/build.py
SITE_URL="${SITE_URL:-http://localhost:8000}" .venv/bin/python scripts/check_links.py
cd dist && python3 -m http.server 8000
