#!/usr/bin/env bash
# Fetch the Vosk small English model (~40MB).
set -euo pipefail

cd "$(dirname "$0")/models"

MODEL="vosk-model-small-en-us-0.15"
URL="https://alphacephei.com/vosk/models/${MODEL}.zip"

if [ -d "$MODEL" ]; then
  echo "Model already present: $MODEL"
  exit 0
fi

echo "Downloading $MODEL ..."
curl -L -o "${MODEL}.zip" "$URL"
unzip -q "${MODEL}.zip"
rm "${MODEL}.zip"
echo "Done. Model at: $(pwd)/${MODEL}"
