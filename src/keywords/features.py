"""MFCC feature extraction for keyword matching."""
import numpy as np
from python_speech_features import mfcc


def extract_mfcc(audio_float32: np.ndarray, samplerate: int = 16000) -> np.ndarray:
    """Extract MFCC features. Returns (T, 13) float32 matrix."""
    if len(audio_float32) < int(samplerate * 0.05):
        return np.zeros((0, 13), dtype=np.float32)
    feats = mfcc(
        audio_float32,
        samplerate=samplerate,
        winlen=0.025,
        winstep=0.010,
        numcep=13,
        nfilt=26,
        appendEnergy=True,
    )
    # cepstral mean normalization — robustness to channel/level differences
    if len(feats) > 0:
        feats = feats - feats.mean(axis=0, keepdims=True)
    return feats.astype(np.float32)
