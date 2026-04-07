#!/usr/bin/env bash
# One-shot setup: create venv, install deps, download model.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating .venv with python3.11 ..."
  python3.11 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

./download_model.sh
echo
echo "Setup complete. Run with: ./run.sh"
