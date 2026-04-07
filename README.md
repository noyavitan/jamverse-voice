# Jamverse STT POC

Real-time, offline, free speech-to-text sidecar for Jamverse. Recognizes
spoken music commands (`Dm7`, `Am`, `start`, `stop`, `next bar`, `1 2 3 4`, …)
and prints them live to the terminal. Designed to forward commands to
Jamverse via OSC without ever clashing with the Unity avatar channel.

## Why this stack

- **Engine: Vosk** (Kaldi). True streaming ASR, ~100–200ms latency on M-series.
  With a fixed grammar of music vocab it locks on hard. Whisper/whisper.cpp
  can't hit the <300ms target — they're chunk-based.
- **Sidecar process, not embedded.** Keeps Whisper-class workloads off
  Jamverse's audio thread, isolates crashes, lets us swap engines without
  recompiling JUCE.
- **OSC transport.** Same protocol family Jamverse already speaks to Unity.

## OSC — no clash with avatars

| Channel | Port | Namespaces |
|---|---|---|
| Jamverse ↔ Unity (avatars) | **9000** | `/session/*` `/input/*` `/{drummer\|bass\|keys}/*` `/calibration/*` |
| STT sidecar → Jamverse     | **9100** | `/stt/*` only |

Different port AND different namespace. Zero overlap by construction.

## Setup

Requires Python 3.11 (Vosk doesn't have wheels for 3.13/3.14 yet).

```bash
./setup.sh           # creates .venv, installs deps, downloads model
```

## Usage

### Headless mode (what Jamverse will launch)
```bash
./run.sh                       # pick a device, start transcribing
./run.sh --list                # list input devices and exit
./run.sh --osc                 # also forward commands over OSC :9100
./run.sh --no-grammar          # disable music vocab biasing
```

### Developer TUI (Textual)
```bash
./run.sh dev                   # multi-pane dev console
./run.sh dev --osc             # TUI with OSC forwarding on at startup
```

Keybindings inside the TUI: `[o]` toggle OSC · `[k]` capture custom keyword
· `[c]` clear OSC log · `[q]` quit

### Custom keywords (any sound, including gibberish)
```bash
./run.sh capture wakeup        # record 4 samples of "wakeup" (or any sound)
./run.sh capture blarghnix     # gibberish works — uses MFCC + DTW pattern matching
./run.sh keywords              # list saved keywords
./run.sh keywords delete wakeup
```
Captured keywords are auto-detected by both headless and TUI modes alongside
the normal grammar. Hits emit `/stt/keyword [name, score]`.

## Output format

```
  … d minor sev               ← live partial (overwrites)
  ✓ d minor seven   →  chord:Dm7
  ✓ next bar        →  transport:next_bar
  ✓ one two three four   →  count:[1, 2, 3, 4]
```

## OSC messages emitted (port 9100)

| Spoken            | Address          | Args            |
|-------------------|------------------|-----------------|
| `D minor seven`   | `/stt/chord`     | `["Dm7"]`       |
| `A sharp major`   | `/stt/chord`     | `["A#"]`        |
| `start` / `stop`  | `/stt/transport` | `["start"]`     |
| `next bar`        | `/stt/transport` | `["next_bar"]`  |
| `one two three`   | `/stt/count`     | `[1, 2, 3]`     |
| `bass` / `drums`  | `/stt/instrument`| `["bass"]`      |
| live partials     | `/stt/partial`   | `[text]`        |
| custom keyword hit| `/stt/keyword`   | `["wakeup", 0.92]` |

## Project layout

```
speech-to-text-poc/
├── main.py                     # entry point with subcommands
├── setup.sh / run.sh / download_model.sh
├── requirements.txt
├── models/                     # Vosk model (gitignored)
├── keywords/                   # user-recorded custom keywords (gitignored)
└── src/
    ├── config.py               # ports, sample rates, model path
    ├── app.py                  # headless orchestrator (what Jamverse launches)
    ├── core/
    │   ├── events.py           # PartialEvent, FinalEvent, OscOutEvent, KeywordHitEvent, ...
    │   └── runner.py           # EngineRunner — owns audio + Vosk + detector + OSC
    ├── audio/device_picker.py  # interactive device + channel selection
    ├── engines/
    │   ├── base.py             # SpeechEngine ABC (swap to Moonshine/whisper.cpp later)
    │   └── vosk_engine.py
    ├── grammar/
    │   ├── music_vocab.py      # chord/transport/number/BPM tokens
    │   └── styles.py           # ~80 musical styles
    ├── parser/command_parser.py # text → structured Command
    ├── keywords/               # custom-keyword detection (any sound, including gibberish)
    │   ├── features.py         # MFCC extraction
    │   ├── store.py            # WAV samples + meta on disk
    │   ├── detector.py         # sliding-window DTW matcher
    │   ├── capture.py          # record-N-samples flow with auto-threshold
    │   └── cli.py              # capture / list / delete subcommands
    ├── output/
    │   ├── terminal.py         # live partial/final printer (headless)
    │   └── osc_sender.py       # /stt/* sender
    └── tui/                    # Textual developer console (dev-only, not shipped)
        ├── app.py              # JamverseVoiceTUI
        ├── widgets.py          # transcript / OSC log / keywords / stats / status bar
        └── modals.py           # capture-keyword modal
```

**Same engine, two front-ends:** `core/runner.py` is the engine; both
`src/app.py` (headless) and `src/tui/app.py` (TUI) consume the same event
stream. Production Jamverse launches headless mode — the TUI never ships.

## Porting to Jamverse later

1. JUCE side: add an OSC receiver bound to `127.0.0.1:9100`, route `/stt/*`
   into a `SttCommandRouter` (mirror of how `SessionReceiver` consumes
   `/session/*` on the Unity side).
2. Launch this sidecar with `juce::ChildProcess` from JUCE startup
   (mirrors how `AIJamAvatars.app` is launched).
3. STT picks its **own** input device — completely independent of Jamverse's
   audio interface, so the user can talk into the MacBook mic while the
   interface is busy with instruments.
```
