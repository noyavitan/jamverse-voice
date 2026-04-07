"""Entry point. Usage:
  python main.py                # interactive: pick device, transcribe
  python main.py --list         # list input devices and exit
  python main.py --osc          # also forward commands over OSC to 127.0.0.1:9100/stt/*
  python main.py --no-grammar   # disable music vocab biasing (open dictation mode)
"""
import argparse
import sys

from src.app import run


def main() -> int:
    p = argparse.ArgumentParser(description="Jamverse STT POC (Vosk, real-time)")
    p.add_argument("--list", action="store_true", help="list input devices and exit")
    p.add_argument("--osc", action="store_true", help="forward commands to Jamverse via OSC :9100 /stt/*")
    p.add_argument("--no-grammar", action="store_true", help="disable music vocab biasing")
    args = p.parse_args()
    return run(use_osc=args.osc, use_grammar=not args.no_grammar, list_only=args.list)


if __name__ == "__main__":
    sys.exit(main())
