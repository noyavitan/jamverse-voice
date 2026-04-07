"""CLI subcommands for keyword management (no TUI required)."""
from pathlib import Path

from ..audio.device_picker import pick_device
from .store import KeywordStore
from .capture import capture_keyword

KEYWORDS_DIR = Path(__file__).resolve().parent.parent.parent / "keywords"


def _store() -> KeywordStore:
    return KeywordStore(KEYWORDS_DIR)


def cmd_capture(name: str) -> int:
    print(f"\n=== Capture keyword: '{name}' ===")
    print("You'll be prompted to say it 4 times.\n")
    device = pick_device()
    print(f"\nUsing: {device.device_name} (ch {device.channel_index + 1})\n")
    capture_keyword(name, _store(), device, on_status=print)
    return 0


def cmd_list() -> int:
    store = _store()
    kws = store.list()
    if not kws:
        print("No keywords saved yet. Use:  ./run.sh capture <name>")
        return 0
    print(f"\n{len(kws)} keyword(s) at {store.root}:\n")
    for kw in kws:
        total = sum(len(s) for s in kw.samples)
        print(f"  • {kw.name:20} {len(kw.samples)} samples  threshold={kw.threshold:.2f}  ({total / 16000:.2f}s audio)")
    print()
    return 0


def cmd_delete(name: str) -> int:
    if _store().delete(name):
        print(f"Deleted keyword '{name}'")
        return 0
    print(f"No such keyword '{name}'")
    return 1
