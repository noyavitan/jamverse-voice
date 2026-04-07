"""Event types emitted by EngineRunner. Both headless and TUI consume these."""
from dataclasses import dataclass
from typing import Optional, Union

from ..parser.command_parser import Command


@dataclass
class PartialEvent:
    text: str


@dataclass
class FinalEvent:
    text: str
    command: Optional[Command]


@dataclass
class OscOutEvent:
    address: str        # full address e.g. "/stt/chord"
    args: list


@dataclass
class KeywordHitEvent:
    name: str
    score: float        # 0..1, higher = better match


@dataclass
class LevelEvent:
    rms_dbfs: float     # negative number, 0 = clip


@dataclass
class StatusEvent:
    message: str
    kind: str = "info"  # "info" | "warn" | "error"


Event = Union[PartialEvent, FinalEvent, OscOutEvent, KeywordHitEvent, LevelEvent, StatusEvent]
