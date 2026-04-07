"""Standalone capture flow — records N samples of a spoken keyword and saves them.

Used by both the CLI (`./run.sh capture <name>`) and the TUI capture modal.
Opens its own short-lived audio stream; the caller must ensure no other
stream is using the device at the same time.
"""
import time
from typing import Callable, List, Optional

import numpy as np
import sounddevice as sd
import soxr

from ..audio.device_picker import DeviceChoice
from .features import extract_mfcc
from .detector import _dtw_distance
from .store import KeywordStore

StatusFn = Callable[[str], None]


def _trim_silence(audio: np.ndarray, sr: int = 16000,
                  threshold_dbfs: float = -42.0,
                  frame_ms: int = 20) -> np.ndarray:
    if len(audio) == 0:
        return audio
    frame_len = int(sr * frame_ms / 1000)
    n_frames = len(audio) // frame_len
    if n_frames == 0:
        return audio
    frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    voiced = db > threshold_dbfs
    if not voiced.any():
        return audio
    start = int(np.argmax(voiced))
    end = len(voiced) - int(np.argmax(voiced[::-1]))
    pad = 2
    s = max(0, start - pad)
    e = min(len(voiced), end + pad)
    return audio[s * frame_len : e * frame_len]


def _record_one(device: DeviceChoice, seconds: float) -> np.ndarray:
    """Record `seconds` from device, return mono float32 at 16k."""
    src_sr = device.samplerate
    n = int(seconds * src_sr)
    audio = sd.rec(
        n,
        samplerate=src_sr,
        channels=device.open_channels,
        dtype="float32",
        device=device.device_index,
    )
    sd.wait()
    mono = audio[:, device.channel_index].copy()
    if src_sr != 16000:
        mono = soxr.resample(mono, src_sr, 16000)
    return mono.astype(np.float32)


def capture_keyword(name: str,
                    store: KeywordStore,
                    device: DeviceChoice,
                    *,
                    num_samples: int = 4,
                    sample_seconds: float = 1.5,
                    on_status: Optional[StatusFn] = None) -> float:
    """Record num_samples utterances, compute auto-threshold, save. Returns threshold."""
    say = on_status or (lambda s: None)

    samples: List[np.ndarray] = []
    for i in range(num_samples):
        say(f"Sample {i + 1}/{num_samples} — get ready…")
        time.sleep(0.5)
        for c in (3, 2, 1):
            say(f"  {c}")
            time.sleep(0.4)
        say(f"  ● recording — say '{name}'")
        raw = _record_one(device, sample_seconds)
        trimmed = _trim_silence(raw)
        if len(trimmed) < 1600:  # <100ms voiced — likely missed
            say("  ⚠ very short — re-record this sample")
            i -= 1
            continue
        samples.append(trimmed)
        say(f"  ✓ captured ({len(trimmed) / 16000:.2f}s)")

    say("Computing threshold from sample self-similarity…")
    feats = [extract_mfcc(s) for s in samples]
    distances = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            d = _dtw_distance(feats[i], feats[j])
            distances.append(d)

    if distances:
        avg = float(np.mean(distances))
        std = float(np.std(distances))
        # threshold = self-similarity ceiling + a margin → matches must be at
        # least as similar as samples are to each other (with some headroom)
        threshold = avg + max(std * 1.5, avg * 0.25)
    else:
        threshold = 50.0

    store.save(name, samples, threshold)
    say(f"Saved keyword '{name}' (threshold={threshold:.2f}, {len(samples)} samples)")
    return threshold
