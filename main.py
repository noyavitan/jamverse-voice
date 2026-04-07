"""Entry point with subcommands.

  python main.py                    # headless interactive (what Jamverse launches)
  python main.py --list             # list input devices and exit
  python main.py --osc              # headless + forward OSC
  python main.py dev                # Textual TUI for development
  python main.py dev --osc          # TUI with OSC enabled at startup
  python main.py capture <name>     # record a custom keyword (no TUI)
  python main.py keywords           # list saved keywords
  python main.py keywords delete <name>
"""
import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jamverse-voice", description="Real-time STT sidecar for Jamverse")
    sub = p.add_subparsers(dest="cmd")

    # default (headless) flags also live on the root parser
    p.add_argument("--list", action="store_true", help="list input devices and exit")
    p.add_argument("--osc", action="store_true", help="forward commands over OSC :9100 /stt/*")
    p.add_argument("--no-grammar", action="store_true", help="disable music vocab biasing")

    pd = sub.add_parser("dev", help="launch the Textual developer TUI")
    pd.add_argument("--osc", action="store_true", help="start with OSC forwarding enabled")

    pc = sub.add_parser("capture", help="record a custom keyword")
    pc.add_argument("name", help="keyword name (any word, even gibberish)")

    pk = sub.add_parser("keywords", help="manage saved keywords")
    pk_sub = pk.add_subparsers(dest="kw_cmd")
    pk_sub.add_parser("list", help="list saved keywords")
    pkd = pk_sub.add_parser("delete", help="delete a saved keyword")
    pkd.add_argument("name")

    return p


def main() -> int:
    args = _build_parser().parse_args()

    if args.cmd == "dev":
        from src.audio.device_picker import pick_device
        from src.tui.app import JamverseVoiceTUI
        device = pick_device()
        JamverseVoiceTUI(device, use_osc=args.osc).run()
        return 0

    if args.cmd == "capture":
        from src.keywords.cli import cmd_capture
        return cmd_capture(args.name)

    if args.cmd == "keywords":
        from src.keywords.cli import cmd_list, cmd_delete
        if args.kw_cmd == "delete":
            return cmd_delete(args.name)
        return cmd_list()

    # default: headless mode
    from src.app import run
    return run(use_osc=args.osc, use_grammar=not args.no_grammar, list_only=args.list)


if __name__ == "__main__":
    sys.exit(main())
