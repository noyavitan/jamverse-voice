"""Headless mode: interactive device picker → live terminal transcription.
This is what Jamverse will launch as a child process (no TUI).
"""
import sys
import threading
from pathlib import Path

from .audio.device_picker import pick_device, print_devices
from .core.runner import EngineRunner
from .core.events import (
    Event, PartialEvent, FinalEvent, OscOutEvent, KeywordHitEvent, StatusEvent,
)
from .output.terminal import TerminalPrinter

KEYWORDS_DIR = Path(__file__).resolve().parent.parent / "keywords"


def run(use_osc: bool = False, use_grammar: bool = True, list_only: bool = False) -> int:
    if list_only:
        print_devices()
        return 0

    printer = TerminalPrinter()
    printer.info("\n=== Jamverse Voice (headless) ===")

    device = pick_device()
    printer.info(
        f"\nUsing: [{device.device_index}] {device.device_name} "
        f"(channel {device.channel_index + 1}/{device.open_channels} @ {device.samplerate} Hz)"
    )
    printer.info(f"OSC: {'enabled (:9100 /stt/*)' if use_osc else 'disabled (pass --osc to enable)'}")
    if KEYWORDS_DIR.exists() and any(KEYWORDS_DIR.iterdir()):
        printer.info(f"Keywords: loaded from {KEYWORDS_DIR}")
    printer.info("\nSpeak now. Ctrl+C to quit.\n")

    stop = threading.Event()

    def on_event(event: Event) -> None:
        if isinstance(event, PartialEvent):
            printer.partial(event.text)
        elif isinstance(event, FinalEvent):
            cmd_repr = f"{event.command.type}:{event.command.value}" if event.command else ""
            printer.final(event.text, cmd_repr)
        elif isinstance(event, KeywordHitEvent):
            printer.final(f"★ keyword: {event.name}", f"score:{event.score:.2f}")
        elif isinstance(event, OscOutEvent):
            pass  # silent in headless mode (Jamverse receives it on the wire)
        elif isinstance(event, StatusEvent) and event.kind != "info":
            printer.info(f"[{event.kind}] {event.message}")

    runner = EngineRunner(on_event=on_event)
    try:
        runner.start(
            device,
            use_grammar=use_grammar,
            use_osc=use_osc,
            keywords_dir=KEYWORDS_DIR,
        )
        stop.wait()  # blocks until KeyboardInterrupt
    except KeyboardInterrupt:
        printer.info("\nbye.")
    except Exception as e:
        sys.stderr.write(f"\nfatal: {e}\n")
        return 1
    finally:
        runner.stop()
    return 0
