"""
A/B Media Comparison State Model.
"""
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from openreview.models.clip import MediaClip


class ComparisonMode(IntEnum):
    OFF = 0
    REPLACE = 0
    WIPE = 1
    SPLIT = 2
    DIFFERENCE = 3
    OVER = 4
    ADD = 5
    DIFFERENCE_INVERTED = 6
    SEQUENCE = 7


@dataclass
class ComparisonState:
    mode: ComparisonMode = ComparisonMode.OFF
    wipe_position: float = 0.5  # 0.0 to 1.0
    wipe_angle_deg: float = 0.0  # 0.0 = vertical line (left/right split), 90.0 = horizontal line (top/bottom split)
    wipe_center: tuple = (0.5, 0.5)  # Normalized (x, y) center pivot of the wipe control
    diff_boost: float = 1.0
    stack_mix: float = 1.0  # 0.0 to 1.0
    channels_a: tuple = (True, True, True, True)  # R, G, B, A
    primary_clip: Optional[MediaClip] = None
    reference_clip: Optional[MediaClip] = None

    def toggle_wipe(self) -> None:
        """Toggle between Off and Wipe mode (shortcut 'W')."""
        if self.mode == ComparisonMode.WIPE:
            self.mode = ComparisonMode.OFF
        else:
            self.mode = ComparisonMode.WIPE

    def reset_wipe(self) -> None:
        """Reset wipe parameters to default 50% split and vertical orientation."""
        self.wipe_position = 0.5
        self.wipe_angle_deg = 0.0
        self.wipe_center = (0.5, 0.5)
        self.diff_boost = 1.0

    def flip_orientation(self) -> None:
        """Flip wipe orientation between Vertical (0°) and Horizontal (90°)."""
        # If currently near horizontal (within 45° of 90°), flip to vertical (0°); otherwise flip to horizontal (90°)
        norm_angle = self.wipe_angle_deg % 180.0
        if abs(norm_angle - 90.0) < 45.0:
            self.wipe_angle_deg = 0.0
        else:
            self.wipe_angle_deg = 90.0

    def reset(self) -> None:
        """Reset comparison state back to default single-view mode."""
        self.mode = ComparisonMode.OFF
        self.wipe_position = 0.5
        self.wipe_angle_deg = 0.0
        self.wipe_center = (0.5, 0.5)
        self.diff_boost = 1.0
        self.stack_mix = 1.0
        self.channels_a = (True, True, True, True)
        self.primary_clip = None
        self.reference_clip = None
