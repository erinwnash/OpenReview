"""
Media Clip and Editorial Sequence Data Models.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MediaClip:
    id: str
    name: str
    file_path: str
    start_frame: int = 1001
    end_frame: int = 1200
    fps: float = 24.0
    width: int = 1920
    height: int = 1080
    colorspace: str = "ACEScg"
    codec: str = "Uncompressed EXR (Float32)"
    is_active: bool = True
    track_index: int = 0

    @property
    def duration(self) -> int:
        return max(1, self.end_frame - self.start_frame + 1)


@dataclass
class SequenceModel:
    name: str = "OpenReview Sequence"
    start_frame: int = 1001
    end_frame: int = 1200
    fps: float = 24.0
    clips: List[MediaClip] = field(default_factory=list)

    @property
    def duration(self) -> int:
        return max(1, self.end_frame - self.start_frame + 1)
