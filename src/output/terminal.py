"""Live terminal printer — partial hypotheses overwrite the current line,
finalized lines commit and scroll."""
import sys


class TerminalPrinter:
    def __init__(self):
        self._last_partial_len = 0

    def partial(self, text: str) -> None:
        line = f"  … {text}"
        pad = max(0, self._last_partial_len - len(line))
        sys.stdout.write("\r" + line + (" " * pad))
        sys.stdout.flush()
        self._last_partial_len = len(line)

    def final(self, text: str, command_repr: str = "") -> None:
        pad = " " * max(0, self._last_partial_len)
        sys.stdout.write("\r" + pad + "\r")
        suffix = f"   →  {command_repr}" if command_repr else ""
        sys.stdout.write(f"  ✓ {text}{suffix}\n")
        sys.stdout.flush()
        self._last_partial_len = 0

    def info(self, text: str) -> None:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
