#!/usr/bin/env bash
# Convenience launcher: activates venv and runs main.py with any args passed through.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "No .venv found. Run: ./setup.sh"
  exit 1
fi

source .venv/bin/activate
python main.py "$@"
