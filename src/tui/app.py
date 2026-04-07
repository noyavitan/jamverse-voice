"""Textual TUI for Jamverse Voice — developer console.

Subscribes to EngineRunner events and renders them in a multi-pane layout.
This is dev-only — production Jamverse launches the headless mode.
"""
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical

from ..audio.device_picker import DeviceChoice
from ..core.events import (
    Event, PartialEvent, FinalEvent, OscOutEvent, KeywordHitEvent,
    LevelEvent, StatusEvent,
)
from ..core.runner import EngineRunner
from ..keywords.store import KeywordStore
from .widgets import TranscriptPanel, OscLogPanel, KeywordsPanel, StatsPanel, StatusBar
from .modals import CaptureKeywordModal


KEYWORDS_DIR = Path(__file__).resolve().parent.parent.parent / "keywords"


class JamverseVoiceTUI(App):
    CSS = """
    Screen { layout: vertical; }

    StatusBar {
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
    }

    #main {
        height: 1fr;
    }

    #left {
        width: 2fr;
        padding: 0 1;
    }

    #right {
        width: 1fr;
        padding: 0 1;
    }

    TranscriptPanel {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    OscLogPanel {
        height: 2fr;
        border: round $warning;
        padding: 0 1;
    }

    KeywordsPanel {
        height: auto;
        min-height: 6;
        border: round $secondary;
        padding: 0 1;
    }

    StatsPanel {
        height: 5;
        border: round $success;
        padding: 0 1;
    }

    Footer { background: $boost; }
    """

    BINDINGS = [
        Binding("o", "toggle_osc", "Toggle OSC"),
        Binding("k", "capture_keyword", "Capture keyword"),
        Binding("c", "clear_log", "Clear OSC log"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, device: DeviceChoice, *, use_osc: bool = False):
        super().__init__()
        self.device = device
        self.initial_osc = use_osc
        self.store = KeywordStore(KEYWORDS_DIR)
        self.runner: EngineRunner | None = None

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield TranscriptPanel(id="transcript")
            with Vertical(id="right"):
                yield OscLogPanel(id="osc")
                yield KeywordsPanel(self.store, id="keywords")
                yield StatsPanel(id="stats")
        from textual.widgets import Footer
        yield Footer()

    def on_mount(self) -> None:
        bar = self.query_one("#status", StatusBar)
        bar.set_device(self.device.device_name)
        bar.set_osc(self.initial_osc)
        bar.set_keywords(len(self.store.names()))

        self.runner = EngineRunner(on_event=self._on_engine_event)
        self.runner.start(
            self.device,
            use_grammar=True,
            use_osc=self.initial_osc,
            keywords_dir=KEYWORDS_DIR,
        )
        self.query_one("#transcript", TranscriptPanel).info(
            f"Listening on {self.device.device_name} — say a chord, transport, BPM, style, or keyword."
        )

    def on_unmount(self) -> None:
        if self.runner is not None:
            self.runner.stop()

    # ---------- engine events (called from worker thread) ----------

    def _on_engine_event(self, event: Event) -> None:
        self.call_from_thread(self._handle_event, event)

    def _handle_event(self, event: Event) -> None:
        if isinstance(event, PartialEvent):
            self.query_one("#transcript", TranscriptPanel).set_partial(event.text)
        elif isinstance(event, FinalEvent):
            self.query_one("#transcript", TranscriptPanel).add_final(event.text, event.command)
        elif isinstance(event, OscOutEvent):
            self.query_one("#osc", OscLogPanel).add(event.address, event.args)
        elif isinstance(event, KeywordHitEvent):
            self.query_one("#transcript", TranscriptPanel).add_keyword(event.name, event.score)
        elif isinstance(event, LevelEvent):
            self.query_one("#stats", StatsPanel).rms_dbfs = event.rms_dbfs
        elif isinstance(event, StatusEvent):
            self.query_one("#transcript", TranscriptPanel).info(event.message, event.kind)

    # ---------- actions ----------

    def action_toggle_osc(self) -> None:
        if self.runner is None:
            return
        enabled = self.runner.toggle_osc()
        self.query_one("#status", StatusBar).set_osc(enabled)

    def action_clear_log(self) -> None:
        self.query_one("#osc", OscLogPanel).clear_log()

    def action_capture_keyword(self) -> None:
        if self.runner is None:
            return
        modal = CaptureKeywordModal(
            self.store, self.device,
            pause_audio_cb=self.runner.pause_audio,
            resume_audio_cb=self.runner.resume_audio,
        )
        self.push_screen(modal, self._on_capture_done)

    def _on_capture_done(self, result) -> None:
        if result and self.runner is not None:
            self.runner.reload_keywords()
            self.query_one("#keywords", KeywordsPanel).reload()
            self.query_one("#status", StatusBar).set_keywords(len(self.store.names()))
            self.query_one("#transcript", TranscriptPanel).info(f"keyword '{result}' ready")
