"""Modal screens for the TUI."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..audio.device_picker import DeviceChoice
from ..keywords.capture import capture_keyword
from ..keywords.store import KeywordStore


class CaptureKeywordModal(ModalScreen[str | None]):
    """Two-step modal: ask for name → record samples → save."""

    CSS = """
    CaptureKeywordModal {
        align: center middle;
    }
    #capture-box {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #capture-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #capture-status {
        height: auto;
        min-height: 8;
        background: $panel;
        padding: 1;
        margin: 1 0;
    }
    #capture-name {
        margin-bottom: 1;
    }
    Horizontal { height: auto; align: center middle; }
    Button { margin: 0 1; }
    """

    def __init__(self, store: KeywordStore, device: DeviceChoice,
                 pause_audio_cb, resume_audio_cb):
        super().__init__()
        self.store = store
        self.device = device
        self.pause_audio = pause_audio_cb
        self.resume_audio = resume_audio_cb
        self.phase = "name"  # "name" | "recording" | "done"
        self.keyword_name = ""

    def compose(self) -> ComposeResult:
        with Container(id="capture-box"):
            yield Label("★ Capture keyword", id="capture-title")
            yield Label("Name (any word, even gibberish):")
            yield Input(placeholder="e.g. wakeup, blarghnix, kapow", id="capture-name")
            yield Static("", id="capture-status")
            with Container():
                yield Button("Start", id="capture-start", variant="primary")
                yield Button("Cancel", id="capture-cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._begin_capture()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "capture-cancel":
            self.dismiss(None)
        elif event.button.id == "capture-start":
            self._begin_capture()

    def _begin_capture(self) -> None:
        if self.phase != "name":
            return
        name_input = self.query_one("#capture-name", Input)
        name = name_input.value.strip().lower().replace(" ", "_")
        if not name:
            self._set_status("⚠ enter a name first")
            return
        self.keyword_name = name
        self.phase = "recording"
        name_input.disabled = True
        self.query_one("#capture-start", Button).disabled = True
        self._set_status(f"Pausing audio and capturing '{name}'…")
        self.pause_audio()
        # Run capture on a worker thread so the UI stays responsive
        self.run_worker(self._do_capture, thread=True, exclusive=True)

    def _do_capture(self) -> None:
        try:
            capture_keyword(
                self.keyword_name, self.store, self.device,
                on_status=lambda msg: self.app.call_from_thread(self._set_status, msg),
            )
            self.app.call_from_thread(self._finish, self.keyword_name)
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"⚠ error: {e}")
            self.app.call_from_thread(self._finish, None)

    def _set_status(self, msg: str) -> None:
        existing = self.query_one("#capture-status", Static).renderable
        text = (str(existing) + "\n" if existing else "") + msg
        # Keep last ~10 lines
        lines = text.splitlines()[-10:]
        self.query_one("#capture-status", Static).update("\n".join(lines))

    def _finish(self, result) -> None:
        self.resume_audio()
        self.dismiss(result)
