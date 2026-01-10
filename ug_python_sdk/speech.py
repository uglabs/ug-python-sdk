from typing import Self

from pydantic import BaseModel

from .configs import AudioConfig
from .types import Base64


class SubtitleUnit(BaseModel):
    text: str
    start_time_sec: float
    duration_sec: float

    @classmethod
    def from_end_time(cls, text: str, start_time_sec: float, end_time_sec: float) -> Self:
        return cls(
            text=text,
            start_time_sec=start_time_sec,
            duration_sec=end_time_sec - start_time_sec,
        )

    @property
    def end_time_sec(self) -> float:
        return self.start_time_sec + self.duration_sec


class SpeechUnit(BaseModel):
    audio: Base64
    duration_sec: float
    # Only guaranteed to be present on the first unit in a stream.
    audio_config: AudioConfig | None = None
    subtitles: list[SubtitleUnit] | None = None
    # TODO: Add visemes when supported.


class TranscriptionUnit(BaseModel):
    text: str
    duration_sec: float
