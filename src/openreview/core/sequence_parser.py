"""
Image Sequence Auto-Detection and Gap-Tolerant Sequence Reader.
Parses file path patterns (e.g. shot.1001.exr, comp_0050.png, v001.####.dpx)
and detects full sequence frame ranges and missing frame gaps.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Sequence
import numpy as np
from PIL import Image

from openreview.core.reader import MediaReader

# Regex matching: (prefix)(separator)(frame_digits)(separator)(extension)
# e.g., "shot_010.1001.exr", "render_v001_0042.png", "test.0001.tif"
SEQUENCE_REGEX = re.compile(r"^(.*?)([\._\-])(\d+)(\.[a-zA-Z0-9]+)$")


def format_frame_ranges(frames: Sequence[int] | Set[int]) -> str:
    """Format frame numbers into compact range notation, e.g. '1-10, 20-30, 45'."""
    if not frames:
        return ""
    sorted_frames = sorted(set(frames))
    ranges: List[str] = []
    start = sorted_frames[0]
    prev = sorted_frames[0]

    for f in sorted_frames[1:]:
        if f == prev + 1:
            prev = f
        else:
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{prev}")
            start = f
            prev = f

    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{prev}")

    return ", ".join(ranges)


@dataclass
class SequenceInfo:
    directory: str
    prefix: str
    separator: str
    padding: int
    extension: str
    start_frame: int
    end_frame: int
    available_frames: Set[int]
    missing_frames: Set[int]

    @property
    def pattern(self) -> str:
        """Return pattern in printf format, e.g. /path/to/shot.%04d.exr"""
        fmt = f"%0{self.padding}d"
        return os.path.join(self.directory, f"{self.prefix}{self.separator}{fmt}{self.extension}")

    @property
    def hash_pattern(self) -> str:
        """Return pattern in hash format, e.g. /path/to/shot.####.exr"""
        hashes = "#" * self.padding
        return os.path.join(self.directory, f"{self.prefix}{self.separator}{hashes}{self.extension}")

    def frame_path(self, frame: int) -> str:
        formatted = f"{frame:0{self.padding}d}"
        return os.path.join(self.directory, f"{self.prefix}{self.separator}{formatted}{self.extension}")


_SEQUENCE_CACHE: dict[str, SequenceInfo] = {}


def clear_sequence_cache() -> None:
    """Clear cached sequence detection results."""
    _SEQUENCE_CACHE.clear()


def detect_image_sequence(target_path: str) -> Optional[SequenceInfo]:
    """
    Given a file path or directory, auto-detect the matching image sequence.
    Detects min and max frames, missing frame gaps, and naming pattern.
    Utilizes os.scandir for ultra-fast directory traversal and caches findings.
    """
    if not target_path or not os.path.exists(target_path):
        return None

    norm_target = os.path.normpath(os.path.abspath(target_path))
    if norm_target in _SEQUENCE_CACHE:
        return _SEQUENCE_CACHE[norm_target]

    if os.path.isdir(target_path):
        directory = target_path
        sample_file = None
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    if entry.is_file() and SEQUENCE_REGEX.match(entry.name):
                        sample_file = entry.name
                        break
        except Exception:
            return None
        if not sample_file:
            return None
    else:
        directory = os.path.dirname(norm_target)
        sample_file = os.path.basename(norm_target)

    match = SEQUENCE_REGEX.match(sample_file)
    if not match:
        # Single standalone file (not a numbered sequence)
        return None

    prefix, sep, digits_str, ext = match.groups()
    padding = len(digits_str)

    # Scan directory for all matching files using fast scandir
    escaped_prefix = re.escape(prefix)
    escaped_sep = re.escape(sep)
    escaped_ext = re.escape(ext)
    file_pattern_regex = re.compile(rf"^{escaped_prefix}{escaped_sep}(\d+){escaped_ext}$", re.IGNORECASE)

    matched_frames: Set[int] = set()

    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_file():
                    m = file_pattern_regex.match(entry.name)
                    if m:
                        matched_frames.add(int(m.group(1)))
    except Exception:
        return None

    if not matched_frames:
        return None

    start_frame = min(matched_frames)
    end_frame = max(matched_frames)

    full_range = set(range(start_frame, end_frame + 1))
    missing_frames = full_range - matched_frames

    seq_info = SequenceInfo(
        directory=directory,
        prefix=prefix,
        separator=sep,
        padding=padding,
        extension=ext,
        start_frame=start_frame,
        end_frame=end_frame,
        available_frames=matched_frames,
        missing_frames=missing_frames,
    )

    # Cache for target path and sample frame paths
    _SEQUENCE_CACHE[norm_target] = seq_info
    for f in list(matched_frames)[:100]:
        fp = os.path.normpath(seq_info.frame_path(f))
        _SEQUENCE_CACHE[fp] = seq_info

    return seq_info


class DiskSequenceReader(MediaReader):
    """
    Gap-tolerant image sequence reader.
    Loads uncompressed frames into Float32 RGBA buffers.
    If a frame is missing in a sequence gap, holds the closest previous frame.
    """

    def __init__(self, sequence_info: SequenceInfo, active_layer: Optional[str] = None):
        self.seq = sequence_info
        self.active_layer = active_layer
        self._last_valid_frame_data: Optional[np.ndarray] = None
        self._cached_width = 1920
        self._cached_height = 1080

    def set_layer(self, layer: Optional[str]) -> None:
        if self.active_layer != layer:
            self.active_layer = layer
            self._last_valid_frame_data = None

    def read_frame(self, frame: int) -> Optional[np.ndarray]:
        path = self.seq.frame_path(frame)

        if os.path.exists(path):
            from openreview.core.image_io import read_image_file
            arr = read_image_file(path, layer=self.active_layer)
            if arr is not None:
                self._last_valid_frame_data = arr
                self._cached_height, self._cached_width = arr.shape[:2]
                return arr

        # Gap-handling: if missing, hold previous valid frame or read closest available frame
        if self._last_valid_frame_data is not None:
            return self._last_valid_frame_data

        if self.seq.available_frames:
            prev_frames = [f for f in self.seq.available_frames if f < frame]
            target_f = prev_frames[-1] if prev_frames else self.seq.available_frames[0]
            target_path = self.seq.frame_path(target_f)
            if os.path.exists(target_path):
                from openreview.core.image_io import read_image_file
                arr = read_image_file(target_path, layer=self.active_layer)
                if arr is not None:
                    self._last_valid_frame_data = arr
                    self._cached_height, self._cached_width = arr.shape[:2]
                    return arr

        # Fallback empty black frame with resolution
        black = np.zeros((self._cached_height, self._cached_width, 4), dtype=np.float32)
        black[:, :, 3] = 1.0
        return black
