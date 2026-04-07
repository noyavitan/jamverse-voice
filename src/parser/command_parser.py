"""Convert recognized spoken text into structured commands.

Examples:
  "d minor seven"      -> {type:"chord", value:"Dm7"}
  "a sharp major"      -> {type:"chord", value:"A#"}
  "next bar"           -> {type:"transport", value:"next_bar"}
  "start"              -> {type:"transport", value:"start"}
  "one two three four" -> {type:"count", values:[1,2,3,4]}
"""
from dataclasses import dataclass
from typing import Optional

from ..grammar.styles import all_style_phrases

NOTE_LETTERS = {"a", "b", "c", "d", "e", "f", "g"}

# Single-word number values for count parsing.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}

# Full word→int table for BPM parsing (supports compound numbers).
_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
BPM_TRIGGERS = {"bpm", "tempo", "beats"}


def _words_to_int(tokens: list[str]) -> int | None:
    """Convert a sequence of number words to int.
    Handles: 'ninety', 'one twenty' (=120), 'one hundred twenty', 'two hundred'.
    Returns None if no parseable number found.
    """
    if not tokens:
        return None

    # Filter to just number-like tokens
    nums = [t for t in tokens if t in _UNITS or t in _TENS or t == "hundred"]
    if not nums:
        return None

    total = 0
    current = 0
    saw_hundred = False
    for t in nums:
        if t == "hundred":
            current = max(current, 1) * 100
            saw_hundred = True
        elif t in _TENS:
            current += _TENS[t]
        elif t in _UNITS:
            current += _UNITS[t]
    total = current

    # Spoken shorthand: "one twenty" → 120, "one oh five" → 105.
    # If we got two unit-only tokens like ["one","twenty"], treat as concat.
    if not saw_hundred and len(nums) == 2 and nums[0] in _UNITS:
        a, b = nums
        if a in _UNITS and b in _TENS:
            total = _UNITS[a] * 100 + _TENS[b]
        elif a in _UNITS and b in _UNITS and _UNITS[a] >= 1:
            total = _UNITS[a] * 10 + _UNITS[b]
    return total if total > 0 else None


@dataclass
class Command:
    type: str           # "chord" | "transport" | "count" | "instrument" | "raw"
    value: object       # str | int | list

    def as_osc(self):
        """Return (address_suffix, args) — suffix appended to /stt namespace."""
        if self.type == "chord":
            return "/chord", [str(self.value)]
        if self.type == "transport":
            return "/transport", [str(self.value)]
        if self.type == "count":
            return "/count", list(self.value)
        if self.type == "instrument":
            return "/instrument", [str(self.value)]
        if self.type == "bpm":
            return "/bpm", [int(self.value)]
        if self.type == "style":
            # value = (style_id, instrument_or_empty)
            style, instrument = self.value
            return "/style", [style, instrument or ""]
        return "/raw", [str(self.value)]


def _parse_chord(tokens: list[str]) -> Optional[Command]:
    if not tokens or tokens[0] not in NOTE_LETTERS:
        return None
    root = tokens[0].upper()
    i = 1
    if i < len(tokens) and tokens[i] in ("sharp", "flat"):
        root += "#" if tokens[i] == "sharp" else "b"
        i += 1

    quality = ""
    rest = tokens[i:]
    rest_str = " ".join(rest)

    if rest_str.startswith("minor seven"):
        quality = "m7"
    elif rest_str.startswith("major seven"):
        quality = "maj7"
    elif rest_str.startswith("minor"):
        quality = "m"
    elif rest_str.startswith("major"):
        quality = ""
    elif rest_str.startswith("seven"):
        quality = "7"
    elif rest_str.startswith("diminished"):
        quality = "dim"
    elif rest_str.startswith("augmented"):
        quality = "aug"
    elif rest_str.startswith("sus two"):
        quality = "sus2"
    elif rest_str.startswith("sus four"):
        quality = "sus4"

    return Command(type="chord", value=root + quality)


def _parse_transport(tokens: list[str]) -> Optional[Command]:
    joined = " ".join(tokens)
    mapping = {
        "start": "start", "stop": "stop", "play": "play", "pause": "pause",
        "record": "record", "loop": "loop", "unloop": "unloop",
        "next bar": "next_bar", "previous bar": "previous_bar",
        "next": "next", "previous": "previous",
        "faster": "faster", "slower": "slower",
        "louder": "louder", "quieter": "quieter",
        "mute": "mute", "unmute": "unmute",
    }
    # longest-match wins
    for phrase in sorted(mapping, key=len, reverse=True):
        if phrase in joined:
            return Command(type="transport", value=mapping[phrase])
    return None


def _parse_instrument(tokens: list[str]) -> Optional[Command]:
    for t in tokens:
        if t in ("drums", "drummer"):
            return Command(type="instrument", value="drums")
        if t == "bass":
            return Command(type="instrument", value="bass")
        if t == "keys":
            return Command(type="instrument", value="keys")
    return None


_STYLE_PHRASES = all_style_phrases()  # cached, longest-first
_INSTRUMENTS = {"drums": "drums", "drummer": "drums", "bass": "bass", "keys": "keys"}


def _parse_style(tokens: list[str]) -> Optional[Command]:
    """Detect a style phrase, optionally with an instrument target.

    Examples:
      'drums bossa nova'        -> style:(bossa_nova, drums)
      'play keys punk rock'     -> style:(punk_rock, keys)
      'bass funk'               -> style:(funk, bass)
      'bossa nova'              -> style:(bossa_nova, None)
      'drum and bass'           -> style:(dnb, None)
    """
    if not tokens:
        return None
    joined = " " + " ".join(tokens) + " "

    # Greedy longest-match across known style phrases.
    matched_style: Optional[str] = None
    matched_phrase: Optional[str] = None
    for spoken, canonical_id in _STYLE_PHRASES:
        needle = " " + spoken + " "
        if needle in joined:
            matched_style = canonical_id
            matched_phrase = spoken
            break
    if matched_style is None:
        return None

    # Find instrument target (anywhere in the utterance) — but only if it's
    # NOT inside the matched style phrase (avoids 'drum and bass' triggering bass).
    style_tokens = set(matched_phrase.split())
    instrument: Optional[str] = None
    for t in tokens:
        if t in _INSTRUMENTS and t not in style_tokens:
            instrument = _INSTRUMENTS[t]
            break

    return Command(type="style", value=(matched_style, instrument))


def _parse_bpm(tokens: list[str]) -> Optional[Command]:
    """Detect 'bpm 120' / 'tempo ninety five' / '120 bpm'."""
    if not any(t in BPM_TRIGGERS for t in tokens):
        return None
    # Take all number-ish tokens around the trigger word.
    num_tokens = [t for t in tokens if t in _UNITS or t in _TENS or t == "hundred"]
    value = _words_to_int(num_tokens)
    if value is None:
        return None
    # Sanity clamp — typical musical BPM range
    if 20 <= value <= 300:
        return Command(type="bpm", value=value)
    return None


def _parse_count(tokens: list[str]) -> Optional[Command]:
    nums = [NUMBER_WORDS[t] for t in tokens if t in NUMBER_WORDS]
    if len(nums) >= 2:
        return Command(type="count", value=nums)
    return None


def parse(text: str) -> Optional[Command]:
    if not text:
        return None
    tokens = text.lower().split()

    # Order matters: bpm + style first (most specific — need trigger words / phrases),
    # then chord, transport, instrument, count.
    for parser in (_parse_bpm, _parse_style, _parse_chord,
                   _parse_transport, _parse_instrument, _parse_count):
        cmd = parser(tokens)
        if cmd is not None:
            return cmd
    return Command(type="raw", value=text)
