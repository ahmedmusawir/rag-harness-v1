#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi

[ -f .env ] && export $(grep -v '^#' .env | xargs)
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

exec .venv/bin/streamlit run src/streamlit/app.py --server.port 8501
