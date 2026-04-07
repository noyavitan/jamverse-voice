"""Vosk streaming engine with optional fixed grammar (huge accuracy boost on closed vocab)."""
import json
from pathlib import Path
from typing import Iterable, Optional

from vosk import Model, KaldiRecognizer, SetLogLevel

from .base import SpeechEngine, Hypothesis

SetLogLevel(-1)  # silence vosk's stderr spam


class VoskEngine(SpeechEngine):
    def __init__(self, model_dir: Path, samplerate: int = 16000,
                 grammar: Optional[Iterable[str]] = None):
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Vosk model not found at {model_dir}. Run ./download_model.sh first."
            )
        self._model = Model(str(model_dir))
        if grammar is not None:
            # Vosk wants a JSON array string. Add "[unk]" so OOV words don't crash.
            words = list(grammar) + ["[unk]"]
            self._rec = KaldiRecognizer(self._model, samplerate, json.dumps(words))
        else:
            self._rec = KaldiRecognizer(self._model, samplerate)
        self._rec.SetWords(True)

    def feed(self, pcm16_mono_16k: bytes) -> Optional[Hypothesis]:
        if self._rec.AcceptWaveform(pcm16_mono_16k):
            res = json.loads(self._rec.Result())
            text = res.get("text", "").strip()
            return Hypothesis(text=text, is_final=True) if text else None
        else:
            res = json.loads(self._rec.PartialResult())
            text = res.get("partial", "").strip()
            return Hypothesis(text=text, is_final=False) if text else None

    def reset(self) -> None:
        self._rec.Reset()
