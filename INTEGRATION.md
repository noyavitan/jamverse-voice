# Jamverse Voice — Integration Contract

This document is the **stable API** between the `jamverse-voice` sidecar
and the JUCE host application. Treat it as a versioned interface — changes
require bumping the protocol version below and updating both sides.

**Protocol version:** `1`

---

## 1. Architecture overview

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│         Jamverse (JUCE)      │         │   Jamverse Voice (sidecar)   │
│                              │         │                              │
│  juce::ChildProcess ────────────────▶  │  python main.py --osc        │
│                              │         │  ├─ PortAudio (own device)   │
│  juce::OSCReceiver           │         │  ├─ Vosk streaming ASR       │
│  ├─ bind 127.0.0.1:9100      │ ◀──OSC──┤  ├─ Custom keyword detector  │
│  └─ route /stt/* to          │         │  └─ python-osc UDP client    │
│     SttCommandRouter         │         │                              │
└──────────────────────────────┘         └──────────────────────────────┘
```

Two processes, one machine, localhost UDP. The sidecar opens its **own**
audio input device — it does not share Jamverse's audio interface. This is
deliberate: the user can speak into the MacBook mic while their UAD/Apollo
runs the band.

---

## 2. The single process Jamverse launches

**Command:**
```
python main.py --osc
```

(In a packaged build this becomes a PyInstaller-bundled binary at
`Jamverse.app/Contents/Resources/JamverseVoice/jamverse-voice --osc`.)

That's it. **One process, one command.** No TUI, no sub-processes, no
network listeners on the sidecar side. The sidecar:

1. Starts up, loads the Vosk model from `models/vosk-model-small-en-us-0.15/`
2. Loads any saved custom keywords from `keywords/`
3. Picks an audio input — for now, the user picks interactively at first
   launch. **Production note:** add `--device <index>` flag (see §6) so
   Jamverse can persist the user's choice and pass it on subsequent launches.
4. Streams `/stt/*` messages over UDP to `127.0.0.1:9100` until killed.
5. Exits cleanly on SIGINT/SIGTERM.

The Textual TUI is **dev-only** — Jamverse never launches it.

---

## 3. OSC contract

### Endpoint
- **Host:** `127.0.0.1`
- **Port:** `9100`  *(Unity avatar bridge uses 9000 — never collide)*
- **Namespace:** `/stt/*`  *(Unity uses `/session/*`, `/input/*`, `/{drummer|bass|keys}/*`, `/calibration/*` — no overlap)*
- **Transport:** UDP, no handshake

### Messages — JUCE → nothing
The sidecar **only sends**, never receives. There is no command channel
*to* the sidecar. Configuration happens at process launch (CLI flags) or
by restarting the sidecar.

### Messages — Sidecar → Jamverse

| Address | Args (typed) | When | Notes |
|---|---|---|---|
| `/stt/chord` | `[string chord]` | finalized chord recognized | e.g. `"Dm7"`, `"A#"`, `"Cmaj7"` |
| `/stt/transport` | `[string action]` | finalized transport word | one of: `start`, `stop`, `play`, `pause`, `record`, `loop`, `unloop`, `next`, `previous`, `next_bar`, `previous_bar`, `faster`, `slower`, `louder`, `quieter`, `mute`, `unmute` |
| `/stt/bpm` | `[int bpm]` | finalized tempo phrase | clamped to 20–300 |
| `/stt/style` | `[string style_id, string instrument_or_empty]` | finalized style phrase | style is snake_case (`bossa_nova`, `punk_rock`, `dnb`, ...). Instrument is `"drums"`/`"bass"`/`"keys"` or `""` if not specified |
| `/stt/instrument` | `[string instrument]` | bare instrument name | one of `drums`, `bass`, `keys` |
| `/stt/count` | `[int, int, ...]` | counted-in numbers | e.g. `[1, 2, 3, 4]` |
| `/stt/keyword` | `[string name, float score]` | custom keyword detected | `score` in `[0,1]`, higher = more confident |
| `/stt/partial` | `[string text]` | live partial hypothesis | high frequency, optional — only emitted in OSC mode if explicitly enabled |
| `/stt/raw` | `[string text]` | finalized text that didn't match any structured parser | fallback for debugging |

### Schema invariants
- Every address starts with `/stt/`
- All `string` args are UTF-8, lowercase except chord names
- All `int` args are 32-bit signed
- All `float` args are 32-bit
- Argument count and type are stable per address — never overloaded
- New fields are added by introducing a new address, never by appending args

---

## 4. JUCE-side integration

### 4.1 Add an OSC receiver

Mirror of how `Source/Unity/UnityBridge.h` and `Assets/_Core/Scripts/Networking/SessionReceiver.cs` pair up on the Unity side.

**`Source/Voice/SttCommandRouter.h`**
```cpp
#pragma once
#include <juce_osc/juce_osc.h>

class SttCommandRouter : private juce::OSCReceiver,
                         private juce::OSCReceiver::Listener<juce::OSCReceiver::RealtimeCallback>
{
public:
    SttCommandRouter();
    ~SttCommandRouter() override;

    bool start();   // bind 127.0.0.1:9100
    void stop();

private:
    void oscMessageReceived (const juce::OSCMessage& msg) override;

    void handleChord     (const juce::String& chord);
    void handleTransport (const juce::String& action);
    void handleBpm       (int bpm);
    void handleStyle     (const juce::String& styleId, const juce::String& instrument);
    void handleInstrument(const juce::String& instrument);
    void handleCount     (const juce::Array<int>& numbers);
    void handleKeyword   (const juce::String& name, float score);
};
```

**`Source/Voice/SttCommandRouter.cpp`**
```cpp
SttCommandRouter::SttCommandRouter()  { addListener (this); }
SttCommandRouter::~SttCommandRouter() { stop(); }

bool SttCommandRouter::start()
{
    return connect (9100);  // listens on 127.0.0.1 by default
}

void SttCommandRouter::stop() { disconnect(); }

void SttCommandRouter::oscMessageReceived (const juce::OSCMessage& msg)
{
    const auto addr = msg.getAddressPattern().toString();

    if (addr == "/stt/chord" && msg.size() == 1 && msg[0].isString())
        handleChord (msg[0].getString());

    else if (addr == "/stt/transport" && msg.size() == 1 && msg[0].isString())
        handleTransport (msg[0].getString());

    else if (addr == "/stt/bpm" && msg.size() == 1 && msg[0].isInt32())
        handleBpm (msg[0].getInt32());

    else if (addr == "/stt/style" && msg.size() == 2 && msg[0].isString() && msg[1].isString())
        handleStyle (msg[0].getString(), msg[1].getString());

    else if (addr == "/stt/instrument" && msg.size() == 1 && msg[0].isString())
        handleInstrument (msg[0].getString());

    else if (addr == "/stt/count")
    {
        juce::Array<int> nums;
        for (int i = 0; i < msg.size(); ++i)
            if (msg[i].isInt32()) nums.add (msg[i].getInt32());
        handleCount (nums);
    }
    else if (addr == "/stt/keyword" && msg.size() == 2 && msg[0].isString() && msg[1].isFloat32())
        handleKeyword (msg[0].getString(), msg[1].getFloat32());
}
```

**Important:** `RealtimeCallback` means `oscMessageReceived` is called from
the OSC thread. Do NOT touch APVTS or audio state from inside these
handlers — marshal to the message thread (`juce::MessageManager::callAsync`)
or push to a lock-free SPSC queue if you need audio-thread access (mirror
how `UnityBridgeStateMachine` does it for the outbound direction).

### 4.2 Launch the sidecar as a child process

Mirror of how `AIJamAvatars.app` is launched from `quick_build_test.sh`.

**`Source/Voice/VoiceSidecarLauncher.h`**
```cpp
class VoiceSidecarLauncher
{
public:
    bool launch();    // returns true if started
    void stop();      // SIGTERM, then SIGKILL after 2s
    bool isRunning() const;

private:
    juce::ChildProcess process_;
    juce::File resolveSidecarBinary() const;
};
```

**`launch()` core logic:**
```cpp
bool VoiceSidecarLauncher::launch()
{
    auto bin = resolveSidecarBinary();
    if (! bin.existsAsFile()) return false;

    juce::StringArray args { bin.getFullPathName(), "--osc" };
    // Future: persist & pass last-used device
    // args.add ("--device"); args.add (juce::String (savedDeviceIndex));

    return process_.start (args, juce::ChildProcess::wantStdOut | juce::ChildProcess::wantStdErr);
}

juce::File VoiceSidecarLauncher::resolveSidecarBinary() const
{
    // In bundled .app:
    //   Jamverse.app/Contents/Resources/JamverseVoice/jamverse-voice
    auto bundleResources = juce::File::getSpecialLocation (juce::File::currentExecutableFile)
                              .getParentDirectory().getParentDirectory()
                              .getChildFile ("Resources/JamverseVoice/jamverse-voice");
    if (bundleResources.existsAsFile()) return bundleResources;

    // Dev fallback: ~/Development/speech-to-text-poc/.venv/bin/python with main.py
    return juce::File ("/Users/noy/Development/speech-to-text-poc/run.sh");
}
```

### 4.3 Lifecycle

| Event | Action |
|---|---|
| Jamverse launches | `VoiceSidecarLauncher::launch()` then `SttCommandRouter::start()` |
| Jamverse quits | `SttCommandRouter::stop()` then `VoiceSidecarLauncher::stop()` |
| Sidecar crashes | Detect via `process_.isRunning() == false`, optionally auto-restart with backoff (3 attempts then give up + log) |
| User toggles voice off | `stop()` both — sidecar cleanly exits within 1s |

**Crash isolation guarantee:** the sidecar dying never affects Jamverse
audio. The OSC receiver simply stops getting messages.

---

## 5. Distribution / packaging

Use PyInstaller to freeze the sidecar into a single binary:

```bash
cd ~/Development/speech-to-text-poc
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --name jamverse-voice \
  --add-data "models/vosk-model-small-en-us-0.15:models/vosk-model-small-en-us-0.15" \
  --hidden-import=vosk \
  main.py
```

Produces `dist/jamverse-voice` (~80MB with the Vosk model embedded).

Drop into `Jamverse.app/Contents/Resources/JamverseVoice/` from
`quick_build_test.sh` (mirror of how `AIJamAvatars.app` gets force-synced
into the bundle).

**Code signing:** the binary needs to be signed and have microphone
permission entitlements (`com.apple.security.device.audio-input`) — same
treatment as the Unity sub-app.

---

## 6. Recommended additions before production wiring

These are **not implemented yet** — adding them is the natural next step
once the JUCE side starts integrating. They keep the contract from
needing changes once Jamverse depends on it.

| Flag | Purpose |
|---|---|
| `--device <index>` | non-interactive device selection (Jamverse persists user's choice) |
| `--channel <n>` | for multi-channel interfaces |
| `--port <n>` | override OSC port (default 9100) |
| `--no-grammar` | already exists |
| `--keywords-dir <path>` | override keyword storage location (Jamverse points it at `~/Library/Application Support/Jamverse/voice-keywords/`) |
| `--log-file <path>` | structured log output for Jamverse to tail/display |

When these land, Jamverse's `VoiceSidecarLauncher::launch()` will pass them
based on user settings — no interactive prompt needed.

---

## 7. Versioning

This contract is **v1**. Breaking changes (renaming an address, changing
arg types, removing a message) require **v2** and a transition plan.
Additive changes (new address, new optional value) stay on v1.

To check the running sidecar version (future): `python main.py --version`
will print `jamverse-voice 1.0.0` — Jamverse can verify compatibility on
launch.
