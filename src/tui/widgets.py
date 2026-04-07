"""All TUI widgets in one focused module — each is small."""
from datetime import datetime
from typing import Optional

from rich.text import Text
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from ..parser.command_parser import Command


class TranscriptPanel(RichLog):
    """Live transcript: dim partials at bottom, finalized lines accumulate above."""

    def __init__(self, **kw):
        super().__init__(highlight=False, markup=False, wrap=True, auto_scroll=True, **kw)
        self.border_title = "  LIVE TRANSCRIPT  "
        self._last_partial: str = ""

    def set_partial(self, text: str) -> None:
        self._last_partial = text  # rendered as-is on next refresh; we just log it
        self.write(Text(f"  … {text}", style="dim italic"))

    def add_final(self, text: str, command: Optional[Command]) -> None:
        line = Text("  ✓ ", style="bold green")
        line.append(text, style="bold white")
        if command:
            line.append("    ", style="")
            line.append(f"{command.type}", style="cyan")
            line.append(":", style="dim")
            line.append(str(command.value), style="bright_cyan bold")
        self.write(line)

    def add_keyword(self, name: str, score: float) -> None:
        line = Text("  ★ KEYWORD ", style="bold magenta")
        line.append(name, style="bold bright_magenta")
        line.append(f"  ({score:.2f})", style="dim magenta")
        self.write(line)

    def info(self, msg: str, kind: str = "info") -> None:
        styles = {"info": "dim", "warn": "yellow", "error": "bold red"}
        self.write(Text(f"  · {msg}", style=styles.get(kind, "dim")))


class OscLogPanel(RichLog):
    """Wire-level OSC output log with timestamps."""

    def __init__(self, **kw):
        super().__init__(highlight=False, markup=False, wrap=False, auto_scroll=True, **kw)
        self.border_title = "  OSC OUT (:9100)  "
        self.count = 0

    def add(self, address: str, args: list) -> None:
        self.count += 1
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = Text()
        line.append(f"{ts}  ", style="dim")
        line.append(address, style="bold yellow")
        line.append("  ", style="")
        line.append(str(args), style="white")
        self.write(line)

    def clear_log(self) -> None:
        self.clear()
        self.count = 0


class KeywordsPanel(Static):
    """Lists saved custom keywords."""

    def __init__(self, store, **kw):
        super().__init__("", **kw)
        self.border_title = "  KEYWORDS  "
        self.store = store
        self.reload()

    def reload(self) -> None:
        kws = self.store.list()
        if not kws:
            self.update(Text("\n  no keywords yet\n  press [k] to capture", style="dim italic"))
            return
        t = Text()
        t.append("\n")
        for kw in kws:
            t.append("  • ", style="dim")
            t.append(kw.name, style="bold magenta")
            t.append(f"  ({len(kw.samples)} samples)\n", style="dim")
        self.update(t)


class StatsPanel(Static):
    """Input level + status."""

    rms_dbfs: reactive[float] = reactive(-90.0)

    def __init__(self, **kw):
        super().__init__("", **kw)
        self.border_title = "  INPUT  "

    def watch_rms_dbfs(self, value: float) -> None:
        self._render()

    def _render(self) -> None:
        # Simple horizontal level meter
        db = max(-60.0, min(0.0, self.rms_dbfs))
        pct = (db + 60) / 60.0
        width = 20
        filled = int(pct * width)
        bar = "█" * filled + "·" * (width - filled)
        color = "green" if db < -18 else ("yellow" if db < -6 else "bright_red")
        t = Text()
        t.append("\n  ")
        t.append(bar, style=color)
        t.append(f"  {db:6.1f} dBFS\n", style="dim")
        self.update(t)


class StatusBar(Static):
    """Top status bar: device + OSC + recording."""

    def __init__(self, **kw):
        super().__init__("", **kw)
        self._device = "—"
        self._osc = False
        self._kw_count = 0

    def set_device(self, name: str) -> None:
        self._device = name
        self._render()

    def set_osc(self, enabled: bool) -> None:
        self._osc = enabled
        self._render()

    def set_keywords(self, count: int) -> None:
        self._kw_count = count
        self._render()

    def _render(self) -> None:
        t = Text()
        t.append("  ● ", style="bold red blink")
        t.append("Jamverse Voice ", style="bold white")
        t.append(" │ ", style="dim")
        t.append("Device: ", style="dim")
        t.append(self._device, style="bold cyan")
        t.append(" │ ", style="dim")
        t.append("OSC ", style="dim")
        if self._osc:
            t.append("ON :9100", style="bold green")
        else:
            t.append("OFF", style="dim")
        t.append(" │ ", style="dim")
        t.append(f"{self._kw_count} keywords", style="bold magenta")
        self.update(t)
