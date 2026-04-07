"""Engine abstraction — keeps Vosk swappable for whisper.cpp/Moonshine later."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Hypothesis:
    text: str
    is_final: bool


class SpeechEngine(ABC):
    @abstractmethod
    def feed(self, pcm16_mono_16k: bytes) -> Optional[Hypothesis]:
        """Feed a chunk of 16kHz mono int16 PCM. Returns latest hypothesis or None."""
        ...

    @abstractmethod
    def reset(self) -> None:
        ...
