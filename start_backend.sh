#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi

[ -f .env ] && export $(grep -v '^#' .env | xargs)

exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
