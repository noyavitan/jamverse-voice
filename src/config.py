"""Central config — change ports/paths here, never hardcode elsewhere."""
from pathlib import Path

# Audio
TARGET_SAMPLE_RATE = 16000   # Vosk requires 16kHz mono
BLOCK_MS = 30                # ~30ms audio blocks → ~150ms perceived latency
DTYPE = "int16"

# Vosk model — small English model, ~40MB, real-time on CPU.
# Downloaded by ./download_model.sh
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"

# OSC — DELIBERATELY DIFFERENT from Jamverse's Unity bridge (port 9000).
# Jamverse Unity uses 9000 with /session/*, /input/*, /{drummer|bass|keys}/*, /calibration/*
# STT sidecar uses 9100 with /stt/* — zero namespace overlap, zero port collision.
OSC_HOST = "127.0.0.1"
OSC_PORT = 9100
OSC_NAMESPACE = "/stt"
