#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Start the ZEXR Deal Hub development stack (API on :8000, web on :3000).
# Run from the repository root.
# ---------------------------------------------------------------------------
set -euo pipefail

command -v node >/dev/null || { echo "Node.js is required."; exit 1; }
command -v python3 >/dev/null || { echo "Python is required."; exit 1; }

echo "[1/5] Preparing the backend virtual environment..."
[ -d backend/.venv ] || python3 -m venv backend/.venv
# shellcheck disable=SC1091
source backend/.venv/bin/activate

echo "[2/5] Installing Python dependencies..."
pip install --quiet -r backend/requirements-dev.txt
[ -f backend/.env ] || { cp backend/.env.example backend/.env; echo "      Created backend/.env"; }

echo "[3/5] Applying database schema and seeding demo content..."
( cd backend && python -m alembic upgrade head && python -m app.db.seed )

echo "[4/5] Installing frontend dependencies..."
( cd frontend
  [ -d node_modules ] || npm install
  [ -f .env.local ] || cp .env.example .env.local
)

echo "[5/5] Starting servers..."
( cd backend && uvicorn app.main:app --reload --port 8000 ) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

( cd frontend && npm run dev )

echo "API -> http://localhost:8000 (docs at /docs)   Web -> http://localhost:3000"