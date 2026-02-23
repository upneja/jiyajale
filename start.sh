#!/bin/bash
# start.sh — Start Jiyajale (backend + frontend)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Backend
source "$DIR/.venv/bin/activate"
echo "Starting backend on http://localhost:8000..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
echo "Starting frontend on http://localhost:3001..."
cd "$DIR/frontend"
npm run dev -- --host --port 3001 &
FRONTEND_PID=$!

# Wait for both to be ready
sleep 3
echo ""
echo "========================================"
echo "  Jiyajale is running!"
echo "  Open http://localhost:3001"
echo "  Press Ctrl+C to stop"
echo "========================================"

# Open in browser
open http://localhost:3001 2>/dev/null || true

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
