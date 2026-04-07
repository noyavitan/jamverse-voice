"""Sliding-window DTW keyword detector. Runs inside the engine worker loop.

Approach:
- Pre-compute MFCC templates for each saved keyword sample (cached on reload).
- Maintain a rolling audio buffer of the last ~1.2s.
- Every `hop_ms`, extract MFCCs from the buffer and DTW-match against each
  template at the most-recent end of the window.
- A match below the keyword's threshold fires KeywordHit.
- Per-keyword cooldown prevents double-triggering.
"""
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from fastdtw import fastdtw

from .features import extract_mfcc
from .store import KeywordStore, StoredKeyword


@dataclass
class KeywordHit:
    name: str
    score: float       # 0..1, higher = better
    distance: float    # raw DTW distance


def _dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Length-normalized DTW distance between two MFCC matrices."""
    if len(a) == 0 or len(b) == 0:
        return float("inf")
    distance, _ = fastdtw(a, b, dist=lambda x, y: float(np.linalg.norm(x - y)))
    return distance / (len(a) + len(b))


class KeywordDetector:
    def __init__(self,
                 store: KeywordStore,
                 sample_rate: int = 16000,
                 window_ms: int = 1200,
                 hop_ms: int = 200,
                 cooldown_ms: int = 1200):
        self.store = store
        self.sample_rate = sample_rate
        self.window_samples = int(sample_rate * window_ms / 1000)
        self.hop_samples = int(sample_rate * hop_ms / 1000)
        self.cooldown_s = cooldown_ms / 1000.0

        self._buffer = np.zeros(0, dtype=np.float32)
        self._samples_since_check = 0
        self._last_hit_at: dict[str, float] = {}
        self._keywords: List[Tuple[StoredKeyword, List[np.ndarray]]] = []

        self.reload()

    def reload(self) -> None:
        self._keywords = []
        for kw in self.store.list():
            templates = [extract_mfcc(s, self.sample_rate) for s in kw.samples]
            templates = [t for t in templates if len(t) > 0]
            if templates:
                self._keywords.append((kw, templates))

    def __len__(self) -> int:
        return len(self._keywords)

    def feed(self, audio_float32: np.ndarray) -> Optional[KeywordHit]:
        if not self._keywords:
            return None

        self._buffer = np.concatenate([self._buffer, audio_float32])
        if len(self._buffer) > self.window_samples:
            self._buffer = self._buffer[-self.window_samples:]

        self._samples_since_check += len(audio_float32)
        if self._samples_since_check < self.hop_samples:
            return None
        self._samples_since_check = 0

        if len(self._buffer) < self.window_samples // 2:
            return None

        feats = extract_mfcc(self._buffer, self.sample_rate)
        if len(feats) == 0:
            return None

        now = time.time()
        best: Optional[KeywordHit] = None
        for kw, templates in self._keywords:
            if kw.name in self._last_hit_at and now - self._last_hit_at[kw.name] < self.cooldown_s:
                continue
            min_dist = float("inf")
            for tmpl in templates:
                t_len = len(tmpl)
                if len(feats) < max(8, t_len // 2):
                    continue
                # Compare template against the last t_len frames of the window.
                # Allow small offsets to handle utterances ending slightly before window end.
                for offset in (0, 4, 8):
                    end = len(feats) - offset
                    start = max(0, end - t_len)
                    if end - start < 6:
                        continue
                    sub = feats[start:end]
                    d = _dtw_distance(sub, tmpl)
                    if d < min_dist:
                        min_dist = d
            if min_dist < kw.threshold:
                # similarity score: distance < threshold → score in (0,1]
                score = float(max(0.0, min(1.0, 1.0 - min_dist / max(kw.threshold, 1e-6))))
                if best is None or score > best.score:
                    best = KeywordHit(name=kw.name, score=score, distance=min_dist)

        if best is not None:
            self._last_hit_at[best.name] = now
        return best
