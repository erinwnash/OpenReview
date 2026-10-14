"""
VFX Pipeline Version Stepping and Version Detection Engine.
Finds and steps between shot versions (e.g. shot_comp_v001 -> shot_comp_v002)
across image sequences and video files in VFX studio directory structures.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from openreview.core.sequence_parser import detect_image_sequence, SEQUENCE_REGEX
from openreview.core.video_reader import is_video_file

# Version pattern matching e.g. "_v001", ".v02", "-v3", "_V012"
VERSION_TOKEN_REGEX = re.compile(r"([._\-]v)(\d{1,5})", re.IGNORECASE)


def parse_version_token(filename: str) -> Optional[Tuple[str, str, int, int, str]]:
    """
    Finds the rightmost version token in a filename.
    Returns: (prefix_before_token, version_marker, version_int, padding, suffix_after_token)
    Example:
        'shot010_comp_v002.1001.exr' -> ('shot010_comp', '_v', 2, 3, '.1001.exr')
    """
    matches = list(VERSION_TOKEN_REGEX.finditer(filename))
    if not matches:
        return None

    last_match = matches[-1]
    prefix = filename[: last_match.start()]
    marker = last_match.group(1)
    digits = last_match.group(2)
    ver_num = int(digits)
    padding = len(digits)
    suffix = filename[last_match.end() :]

    return prefix, marker, ver_num, padding, suffix


def find_sibling_versions(target_path: str) -> List[Tuple[int, str]]:
    """
    Locates all matching version iterations in the same folder (or sequence folder).
    Returns a sorted list of (version_number, file_path_or_first_frame).
    """
    if not os.path.exists(target_path):
        return []

    parent_dir = os.path.dirname(os.path.abspath(target_path))
    filename = os.path.basename(target_path)

    # 1. Check if target_path is part of an image sequence
    seq_info = detect_image_sequence(target_path)
    is_seq = seq_info is not None and len(seq_info.available_frames) > 0

    if is_seq and seq_info:
        seq_prefix = seq_info.prefix
        token = parse_version_token(seq_prefix)
        if not token:
            return []

        prefix, marker, _, padding, token_suffix = token
        # Regex to match other sequence files in the directory
        escaped_prefix = re.escape(prefix)
        escaped_marker = re.escape(marker[0]) + r"[vV]"
        escaped_suffix = re.escape(token_suffix)
        pattern = re.compile(
            rf"^{escaped_prefix}{escaped_marker}(\d+){escaped_suffix}"
            rf"{re.escape(seq_info.separator)}(\d+){re.escape(seq_info.extension)}$"
        )

        version_first_frames: dict[int, str] = {}
        try:
            entries = sorted(os.listdir(parent_dir))
        except OSError:
            return []

        for entry in entries:
            m = pattern.match(entry)
            if m:
                v_num = int(m.group(1))
                if v_num not in version_first_frames:
                    version_first_frames[v_num] = os.path.join(parent_dir, entry)

        return sorted(version_first_frames.items(), key=lambda x: x[0])

    # 2. Single video or image file
    token = parse_version_token(filename)
    if not token:
        return []

    prefix, marker, _, padding, suffix = token
    escaped_prefix = re.escape(prefix)
    escaped_marker = re.escape(marker[0]) + r"[vV]"
    escaped_suffix = re.escape(suffix)
    pattern = re.compile(rf"^{escaped_prefix}{escaped_marker}(\d+){escaped_suffix}$")

    versions: list[Tuple[int, str]] = []
    try:
        entries = sorted(os.listdir(parent_dir))
    except OSError:
        return []

    for entry in entries:
        m = pattern.match(entry)
        if m:
            v_num = int(m.group(1))
            versions.append((v_num, os.path.join(parent_dir, entry)))

    return sorted(versions, key=lambda x: x[0])


def get_next_version(target_path: str) -> Optional[str]:
    """Return the file path of the next version (e.g. v002 -> v003), or None if at latest."""
    versions = find_sibling_versions(target_path)
    if not versions or len(versions) <= 1:
        return None

    filename = os.path.basename(target_path)
    token = parse_version_token(filename)
    if not token:
        # Check sequence prefix
        seq = detect_image_sequence(target_path)
        if seq:
            token = parse_version_token(seq.prefix)
    if not token:
        return None

    current_v = token[2]
    for v_num, path in versions:
        if v_num > current_v:
            return path

    return None


def get_prev_version(target_path: str) -> Optional[str]:
    """Return the file path of the previous version (e.g. v003 -> v002), or None if at earliest."""
    versions = find_sibling_versions(target_path)
    if not versions or len(versions) <= 1:
        return None

    filename = os.path.basename(target_path)
    token = parse_version_token(filename)
    if not token:
        seq = detect_image_sequence(target_path)
        if seq:
            token = parse_version_token(seq.prefix)
    if not token:
        return None

    current_v = token[2]
    prev_path: Optional[str] = None
    for v_num, path in versions:
        if v_num < current_v:
            prev_path = path
        else:
            break

    return prev_path


def get_version_summary(target_path: str) -> Optional[str]:
    """
    Return a friendly version status string, e.g. 'v002 (2 of 4)'.
    """
    versions = find_sibling_versions(target_path)
    if not versions:
        return None

    filename = os.path.basename(target_path)
    token = parse_version_token(filename)
    if not token:
        seq = detect_image_sequence(target_path)
        if seq:
            token = parse_version_token(seq.prefix)
    if not token:
        return None

    current_v = token[2]
    v_nums = [v[0] for v in versions]
    if current_v in v_nums:
        idx = v_nums.index(current_v) + 1
        pad = token[3]
        return f"v{current_v:0{pad}d} ({idx} of {len(versions)})"

    return f"v{current_v}"
