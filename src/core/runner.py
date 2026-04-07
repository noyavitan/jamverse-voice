"""Engine runner: owns audio stream, Vosk, keyword detector, OSC sender.

Emits Events via a callback. Used by both headless mode and the TUI.
The callback may be invoked from a worker thread — consumers must marshal
to their own UI thread if needed (e.g. Textual's call_from_thread).
"""
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soxr

from .. import config
from ..audio.device_picker import DeviceChoice
from ..engines.vosk_engine import VoskEngine
from ..grammar.music_vocab import build_grammar
from ..parser.command_parser import parse
from ..output.osc_sender import OscSender
from .events import (
    Event, PartialEvent, FinalEvent, OscOutEvent, KeywordHitEvent,
    LevelEvent, StatusEvent,
)

EventCallback = Callable[[Event], None]


class EngineRunner:
    def __init__(self, on_event: EventCallback):
        self.on_event = on_event
        self.device: Optional[DeviceChoice] = None

        self._stop = threading.Event()
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self._stream: Optional[sd.InputStream] = None
        self._worker: Optional[threading.Thread] = None

        self._engine: Optional[VoskEngine] = None
        self._osc: Optional[OscSender] = None
        self._detector = None  # type: ignore  # KeywordDetector — lazy import to avoid hard dep
        self._osc_enabled = False
        self._use_grammar = True
        self._keywords_dir: Optional[Path] = None

    # -------- public API --------

    def start(self, device: DeviceChoice, *, use_grammar: bool = True,
              use_osc: bool = False, keywords_dir: Optional[Path] = None) -> None:
        self.device = device
        self._use_grammar = use_grammar
        self._keywords_dir = keywords_dir
        self._osc_enabled = use_osc

        grammar = build_grammar() if use_grammar else None
        self._engine = VoskEngine(config.MODEL_DIR,
                                  samplerate=config.TARGET_SAMPLE_RATE,
                                  grammar=grammar)
        if use_osc:
            self._osc = OscSender()

        if keywords_dir is not None:
            from ..keywords.store import KeywordStore
            from ..keywords.detector import KeywordDetector
            store = KeywordStore(keywords_dir)
            self._detector = KeywordDetector(store)

        self._start_audio()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._emit(StatusEvent("engine started"))

    def stop(self) -> None:
        self._stop.set()
        self._stop_audio()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
        self._emit(StatusEvent("engine stopped"))

    def toggle_osc(self) -> bool:
        if self._osc is None:
            self._osc = OscSender()
        self._osc_enabled = not self._osc_enabled
        self._emit(StatusEvent(f"OSC {'enabled' if self._osc_enabled else 'disabled'}"))
        return self._osc_enabled

    @property
    def osc_enabled(self) -> bool:
        return self._osc_enabled

    @property
    def has_keywords(self) -> bool:
        return self._detector is not None and len(self._detector) > 0

    def reload_keywords(self) -> None:
        if self._detector is not None:
            self._detector.reload()
            self._emit(StatusEvent(f"reloaded {len(self._detector)} keywords"))

    def pause_audio(self) -> None:
        """Stop the audio stream so something else (e.g. capture flow) can use it."""
        self._stop_audio()

    def resume_audio(self) -> None:
        if self.device is not None:
            self._start_audio()

    # -------- internals --------

    def _emit(self, event: Event) -> None:
        try:
            self.on_event(event)
        except Exception:
            pass  # never let UI errors kill the engine

    def _start_audio(self) -> None:
        assert self.device is not None
        blocksize = int(self.device.samplerate * config.BLOCK_MS / 1000)
        self._stream = sd.InputStream(
            device=self.device.device_index,
            channels=self.device.open_channels,
            samplerate=self.device.samplerate,
            blocksize=blocksize,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()

    def _stop_audio(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self._emit(StatusEvent(str(status), kind="warn"))
        ch = self.device.channel_index  # type: ignore
        mono = indata[:, ch].astype(np.float32, copy=False).copy()
        try:
            self._queue.put_nowait(mono)
        except queue.Full:
            pass  # drop on overflow

    def _worker_loop(self) -> None:
        assert self.device is not None
        target_sr = config.TARGET_SAMPLE_RATE
        src_sr = self.device.samplerate
        resampler = None
        if src_sr != target_sr:
            resampler = soxr.ResampleStream(
                in_rate=src_sr, out_rate=target_sr, num_channels=1, dtype="float32"
            )

        level_decim = 0
        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            resampled = resampler.resample_chunk(block) if resampler is not None else block
            if resampled.size == 0:
                continue

            # Level meter — emit every ~5 blocks (~150ms) to avoid flooding
            level_decim += 1
            if level_decim >= 5:
                level_decim = 0
                rms = float(np.sqrt(np.mean(resampled * resampled) + 1e-12))
                dbfs = 20.0 * np.log10(rms + 1e-9)
                self._emit(LevelEvent(rms_dbfs=dbfs))

            # Vosk
            pcm = np.clip(resampled * 32767.0, -32768, 32767).astype(np.int16).tobytes()
            assert self._engine is not None
            hyp = self._engine.feed(pcm)
            if hyp is not None:
                if hyp.is_final:
                    cmd = parse(hyp.text)
                    self._emit(FinalEvent(hyp.text, cmd))
                    if self._osc_enabled and self._osc and cmd:
                        self._send_osc_command(cmd)
                else:
                    self._emit(PartialEvent(hyp.text))

            # Keyword detector
            if self._detector is not None:
                hit = self._detector.feed(resampled)
                if hit is not None:
                    self._emit(KeywordHitEvent(hit.name, hit.score))
                    if self._osc_enabled and self._osc:
                        self._send_osc_keyword(hit.name, hit.score)

    def _send_osc_command(self, cmd) -> None:
        suffix, args = cmd.as_osc()
        addr = config.OSC_NAMESPACE + suffix
        try:
            self._osc._client.send_message(addr, args)  # type: ignore
            self._emit(OscOutEvent(addr, args))
        except Exception as e:
            self._emit(StatusEvent(f"OSC error: {e}", kind="error"))

    def _send_osc_keyword(self, name: str, score: float) -> None:
        addr = config.OSC_NAMESPACE + "/keyword"
        args = [name, float(score)]
        try:
            self._osc._client.send_message(addr, args)  # type: ignore
            self._emit(OscOutEvent(addr, args))
        except Exception as e:
            self._emit(StatusEvent(f"OSC error: {e}", kind="error"))
