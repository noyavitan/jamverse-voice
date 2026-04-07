"""Interactive input device + channel picker (CoreAudio via PortAudio)."""
from dataclasses import dataclass
import sounddevice as sd


@dataclass
class DeviceChoice:
    device_index: int
    device_name: str
    channel_index: int   # 0-based; which channel of a multi-channel device to read
    open_channels: int   # how many channels to open the stream with
    samplerate: int


def list_input_devices():
    devices = sd.query_devices()
    inputs = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            inputs.append((i, d))
    return inputs


def print_devices():
    print("\nAvailable input devices:")
    print("-" * 72)
    for i, d in list_input_devices():
        print(f"  [{i:2}] {d['name']}  ({d['max_input_channels']} ch @ {int(d['default_samplerate'])} Hz)")
    print("-" * 72)


def pick_device() -> DeviceChoice:
    inputs = list_input_devices()
    if not inputs:
        raise RuntimeError("No input devices found.")

    print_devices()
    while True:
        raw = input("Pick device index: ").strip()
        try:
            idx = int(raw)
            dev = next((d for i, d in inputs if i == idx), None)
            if dev is None:
                print("Not an input device. Try again.")
                continue
            break
        except ValueError:
            print("Enter a number.")

    max_ch = dev["max_input_channels"]
    if max_ch == 1:
        ch = 0
    else:
        while True:
            raw = input(f"Pick channel (1..{max_ch}): ").strip()
            try:
                ch_one = int(raw)
                if 1 <= ch_one <= max_ch:
                    ch = ch_one - 1
                    break
            except ValueError:
                pass
            print("Invalid channel.")

    sr = int(dev["default_samplerate"])
    return DeviceChoice(
        device_index=idx,
        device_name=dev["name"],
        channel_index=ch,
        open_channels=max_ch,
        samplerate=sr,
    )
