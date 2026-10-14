"""
SMPTE Timecode Utilities for OpenReview.
Provides frame <-> timecode conversions (HH:MM:SS:FF) for broadcast and film review.
"""
from __future__ import annotations

import math
from typing import Tuple


def frame_to_timecode(
    frame: int,
    fps: float = 24.0,
    start_timecode: str = "00:00:00:00",
) -> str:
    """
    Convert a frame number to SMPTE timecode (HH:MM:SS:FF).
    Supports fractional and integer frame rates (23.976, 24, 25, 29.97, 30, 48, 50, 60).
    """
    if fps <= 0.0:
        fps = 24.0

    # Parse base offset from start_timecode
    base_frame = timecode_to_frame(start_timecode, fps) if start_timecode != "00:00:00:00" else 0
    total_frames = max(0, base_frame + frame)

    rounded_fps = int(round(fps))
    if rounded_fps <= 0:
        rounded_fps = 24

    frames = total_frames % rounded_fps
    total_seconds = total_frames // rounded_fps
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def timecode_to_frame(
    tc: str,
    fps: float = 24.0,
) -> int:
    """
    Convert SMPTE timecode string (HH:MM:SS:FF or HH:MM:SS;FF) to frame count.
    """
    if not tc or not isinstance(tc, str):
        return 0

    if fps <= 0.0:
        fps = 24.0

    rounded_fps = int(round(fps))
    if rounded_fps <= 0:
        rounded_fps = 24

    clean_tc = tc.strip().replace(";", ":")
    parts = clean_tc.split(":")
    if len(parts) != 4:
        return 0

    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        frames = int(parts[3])
    except ValueError:
        return 0

    total_seconds = (hours * 3600) + (minutes * 60) + seconds
    return (total_seconds * rounded_fps) + frames
