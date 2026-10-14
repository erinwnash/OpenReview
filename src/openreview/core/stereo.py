"""
Stereo 3D Review Engine for OpenReview.
Provides multi-view file auto-detection (%v, %V, _L/_R, .left./.right.),
multi-view EXR layer mapping, and stereo display transformations:
- Left Eye Only
- Right Eye Only
- Anaglyph Red-Cyan (Dubois / standard matrix)
- Side-by-Side (Split)
- Stereo Difference
"""
from __future__ import annotations

import os
import re
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import numpy as np


class StereoEye(IntEnum):
    LEFT = 0
    RIGHT = 1


class StereoMode(IntEnum):
    OFF = 0
    LEFT_ONLY = 1
    RIGHT_ONLY = 2
    ANAGLYPH = 3
    SIDE_BY_SIDE = 4
    DIFFERENCE = 5


# Tokens identifying left and right eye in filenames
# e.g., shot_1001_L.exr vs shot_1001_R.exr, comp.left.1001.dpx vs comp.right.1001.dpx
STEREO_LEFT_PATTERNS = [
    re.compile(r"([._-])(l|left)([._-])", re.IGNORECASE),
    re.compile(r"([._-])(l|left)$", re.IGNORECASE),
]

STEREO_RIGHT_PATTERNS = [
    re.compile(r"([._-])(r|right)([._-])", re.IGNORECASE),
    re.compile(r"([._-])(r|right)$", re.IGNORECASE),
]


@dataclass
class StereoPair:
    left_path: str
    right_path: str
    is_multiview_exr: bool = False
    source_name: str = ""


def detect_stereo_counterpart(file_path: str) -> Optional[StereoPair]:
    """
    Given a file path, inspect if it is a stereo file (or multi-view EXR)
    and find its corresponding Left / Right counterpart.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    dir_name = os.path.dirname(os.path.abspath(file_path))
    base_name = os.path.basename(file_path)
    stem, ext = os.path.splitext(base_name)

    # 1. Multi-view OpenEXR check
    if ext.lower() == ".exr":
        try:
            from openreview.core.image_io import get_exr_channels
            info = get_exr_channels(file_path)
            views = info.get("views", [])
            if "left" in views or "right" in views or "l" in views or "r" in views:
                return StereoPair(
                    left_path=file_path,
                    right_path=file_path,
                    is_multiview_exr=True,
                    source_name=base_name,
                )
        except Exception:
            pass

    # 2. Token substitution (%v or %V)
    if "%v" in base_name or "%V" in base_name:
        is_upper = "%V" in base_name
        token = "%V" if is_upper else "%v"
        left_tok = "Left" if is_upper else "left"
        right_tok = "Right" if is_upper else "right"
        p_left = os.path.join(dir_name, base_name.replace(token, left_tok))
        p_right = os.path.join(dir_name, base_name.replace(token, right_tok))
        if os.path.exists(p_left) or os.path.exists(p_right):
            return StereoPair(
                left_path=p_left if os.path.exists(p_left) else file_path,
                right_path=p_right if os.path.exists(p_right) else file_path,
                source_name=base_name,
            )

    # 3. Filename regex matching for _L / _R or .left. / .right.
    # Check if current file is Left
    for p in STEREO_LEFT_PATTERNS:
        m = p.search(stem)
        if m:
            if len(m.groups()) == 3:
                sep1, tok, sep2 = m.group(1), m.group(2), m.group(3)
            else:
                sep1, tok, sep2 = m.group(1), m.group(2), ""

            if tok.isupper():
                repl_tokens = ["R" if len(tok) == 1 else "RIGHT", "r" if len(tok) == 1 else "right"]
            elif tok.istitle():
                repl_tokens = ["Right", "right", "RIGHT", "R", "r"]
            else:
                repl_tokens = ["r" if len(tok) == 1 else "right", "R" if len(tok) == 1 else "RIGHT"]

            for r_tok in repl_tokens:
                cand_stem = stem[:m.start()] + f"{sep1}{r_tok}{sep2}" + stem[m.end():]
                cand_path = os.path.join(dir_name, cand_stem + ext)
                if os.path.exists(cand_path):
                    return StereoPair(
                        left_path=file_path,
                        right_path=cand_path,
                        source_name=stem,
                    )

    # Check if current file is Right
    for p in STEREO_RIGHT_PATTERNS:
        m = p.search(stem)
        if m:
            if len(m.groups()) == 3:
                sep1, tok, sep2 = m.group(1), m.group(2), m.group(3)
            else:
                sep1, tok, sep2 = m.group(1), m.group(2), ""

            if tok.isupper():
                repl_tokens = ["L" if len(tok) == 1 else "LEFT", "l" if len(tok) == 1 else "left"]
            elif tok.istitle():
                repl_tokens = ["Left", "left", "LEFT", "L", "l"]
            else:
                repl_tokens = ["l" if len(tok) == 1 else "left", "L" if len(tok) == 1 else "LEFT"]

            for l_tok in repl_tokens:
                cand_stem = stem[:m.start()] + f"{sep1}{l_tok}{sep2}" + stem[m.end():]
                cand_path = os.path.join(dir_name, cand_stem + ext)
                if os.path.exists(cand_path):
                    return StereoPair(
                        left_path=cand_path,
                        right_path=file_path,
                        source_name=stem,
                    )

    return None
