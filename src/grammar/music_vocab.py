"""Builds the spoken-word vocabulary Vosk locks onto.

We feed Vosk *spoken* tokens (the words a human actually says).
The parser layer converts these back into structured commands like 'Dm7'.
"""
from .styles import all_style_tokens

NOTES_SPOKEN = ["a", "b", "c", "d", "e", "f", "g"]
ACCIDENTALS = ["sharp", "flat"]
QUALITIES = ["major", "minor", "minor seven", "major seven", "seven",
             "diminished", "augmented", "sus two", "sus four"]

TRANSPORT = [
    "start", "stop", "play", "pause", "record",
    "next", "previous", "bar", "next bar", "previous bar",
    "loop", "unloop", "tempo", "faster", "slower",
    "louder", "quieter", "mute", "unmute",
    "drums", "bass", "keys", "drummer",
]

NUMBERS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred",
]

# BPM trigger words
BPM_WORDS = ["bpm", "tempo", "beats"]


def build_grammar() -> list[str]:
    """Flat list of single-word tokens Vosk will recognize."""
    words: set[str] = set()
    words.update(NOTES_SPOKEN)
    words.update(ACCIDENTALS)
    # split multi-word qualities into single tokens
    for q in QUALITIES:
        for w in q.split():
            words.add(w)
    for t in TRANSPORT:
        for w in t.split():
            words.add(w)
    words.update(NUMBERS)
    words.update(BPM_WORDS)
    words.update(all_style_tokens())
    # filler we want to allow without breaking decoding
    words.update(["the", "to", "at", "in", "on", "and", "now", "go"])
    return sorted(words)
