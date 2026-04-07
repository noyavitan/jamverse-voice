"""On-disk storage for user-recorded keyword samples."""
import json
import shutil
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np


@dataclass
class StoredKeyword:
    name: str
    samples: List[np.ndarray] = field(default_factory=list)  # 16k mono float32
    threshold: float = 50.0


class KeywordStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> List[StoredKeyword]:
        out: List[StoredKeyword] = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir():
                continue
            meta_file = d / "meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                continue
            samples = [self._load_wav(f) for f in sorted(d.glob("sample_*.wav"))]
            out.append(StoredKeyword(
                name=d.name,
                samples=samples,
                threshold=float(meta.get("threshold", 50.0)),
            ))
        return out

    def names(self) -> List[str]:
        return [d.name for d in sorted(self.root.iterdir()) if d.is_dir()]

    def save(self, name: str, samples: List[np.ndarray], threshold: float) -> None:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("sample_*.wav"):
            old.unlink()
        for i, s in enumerate(samples):
            self._save_wav(d / f"sample_{i+1:02d}.wav", s)
        (d / "meta.json").write_text(json.dumps({
            "name": name,
            "threshold": float(threshold),
            "num_samples": len(samples),
        }, indent=2))

    def delete(self, name: str) -> bool:
        d = self.root / name
        if d.exists():
            shutil.rmtree(d)
            return True
        return False

    def _save_wav(self, path: Path, audio_float32: np.ndarray) -> None:
        pcm = np.clip(audio_float32 * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm.tobytes())

    def _load_wav(self, path: Path) -> np.ndarray:
        with wave.open(str(path), "rb") as w:
            frames = w.readframes(w.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
