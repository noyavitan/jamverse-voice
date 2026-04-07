"""Orchestrator: opens audio device, runs Vosk, prints to terminal, optionally sends OSC."""
import queue
import sys
import numpy as np
import sounddevice as sd
import soxr

from . import config
from .audio.device_picker import pick_device, print_devices
from .engines.vosk_engine import VoskEngine
from .grammar.music_vocab import build_grammar
from .parser.command_parser import parse
from .output.terminal import TerminalPrinter
from .output.osc_sender import OscSender


def run(use_osc: bool = False, use_grammar: bool = True, list_only: bool = False) -> int:
    if list_only:
        print_devices()
        return 0

    printer = TerminalPrinter()
    printer.info("\n=== Jamverse STT POC (Vosk) ===")

    choice = pick_device()
    printer.info(
        f"\nUsing: [{choice.device_index}] {choice.device_name} "
        f"(channel {choice.channel_index + 1}/{choice.open_channels} @ {choice.samplerate} Hz)"
    )

    grammar = build_grammar() if use_grammar else None
    if use_grammar:
        printer.info(f"Grammar: {len(grammar)} tokens (chords + transport + numbers)")

    engine = VoskEngine(config.MODEL_DIR, samplerate=config.TARGET_SAMPLE_RATE, grammar=grammar)

    osc: OscSender | None = None
    if use_osc:
        osc = OscSender()
        printer.info(f"OSC: sending to {osc.endpoint}")
    else:
        printer.info("OSC: disabled (pass --osc to enable)")

    printer.info("\nSpeak now. Ctrl+C to quit.\n")

    audio_q: queue.Queue[np.ndarray] = queue.Queue()
    blocksize = int(choice.samplerate * config.BLOCK_MS / 1000)

    def callback(indata, frames, time_info, status):
        if status:
            # underflow/overflow — print but keep going
            sys.stderr.write(f"[audio] {status}\n")
        # take the chosen channel as a mono float32 view
        mono = indata[:, choice.channel_index].astype(np.float32, copy=False)
        audio_q.put(mono.copy())

    try:
        with sd.InputStream(
            device=choice.device_index,
            channels=choice.open_channels,
            samplerate=choice.samplerate,
            blocksize=blocksize,
            dtype="float32",
            callback=callback,
        ):
            _consume(audio_q, engine, choice.samplerate, printer, osc)
    except KeyboardInterrupt:
        printer.info("\nbye.")
        return 0
    except Exception as e:
        sys.stderr.write(f"\nfatal: {e}\n")
        return 1
    return 0


def _consume(audio_q, engine, src_sr, printer, osc):
    """Pull audio blocks, resample to 16k, feed engine, dispatch results."""
    target_sr = 16000
    resampler = soxr.ResampleStream(
        in_rate=src_sr, out_rate=target_sr, num_channels=1, dtype="float32"
    )
    while True:
        block = audio_q.get()
        if src_sr != target_sr:
            resampled = resampler.resample_chunk(block)
        else:
            resampled = block
        if resampled.size == 0:
            continue
        # float32 [-1,1] -> int16 PCM bytes
        pcm = np.clip(resampled * 32767.0, -32768, 32767).astype(np.int16).tobytes()

        hyp = engine.feed(pcm)
        if hyp is None:
            continue
        if hyp.is_final:
            cmd = parse(hyp.text)
            cmd_repr = f"{cmd.type}:{cmd.value}" if cmd else ""
            printer.final(hyp.text, cmd_repr)
            if osc and cmd:
                osc.send_command(cmd)
        else:
            printer.partial(hyp.text)
            if osc:
                osc.send_partial(hyp.text)
