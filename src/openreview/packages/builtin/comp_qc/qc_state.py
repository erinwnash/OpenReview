"""
Reactive Data Model and State Management for xtra QC Utils (Comp QC Toolset).
"""
from __future__ import annotations

from enum import IntEnum
from typing import Optional, Tuple, Dict
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor


def apply_soft_clip(image: np.ndarray, knee_start: float = 1.0) -> np.ndarray:
    """Smoothly compress highlight values exceeding knee_start towards 1.0 using tanh soft-knee.

    Parameters
    ----------
    image : np.ndarray
        Floating-point image array (values can exceed 1.0).
    knee_start : float
        Threshold below which values remain 100% untouched. Values above knee_start
        are smoothly compressed using tanh, asymptotically approaching 1.0.
        If knee_start >= 0.999 (default 1.0), the image is untouched.

    Returns
    -------
    np.ndarray
        Array with softclip applied.
    """
    if image is None or knee_start >= 0.999:
        return image.copy() if image is not None else None

    knee = max(0.001, min(0.999, float(knee_start)))
    headroom = 1.0 - knee
    out = np.array(image, dtype=np.float32, copy=True)
    mask = out > knee
    if np.any(mask):
        out[mask] = knee + headroom * np.tanh((out[mask] - knee) / headroom)
    return out


class QcMode(IntEnum):
    OFF = 0
    LOG_COLORSPACE = 1
    NAN_INF_PIXELS = 2
    HIGHPASS_COMP = 3
    HIGHPASS_PLATE = 4
    CLIPPING_PIXELS = 5
    NEGATIVE_VALUES = 6
    GRAIN_CHECK = 7
    COMP_DIFF_PLATE = 8
    SATURATION_BOOST = 9
    CLAMPED_ALPHA = 10

    # Semantic aliases for xtra QC Utils UI
    BLACK_LEVELS = 1
    NAN_INF = 2
    HIGHPASS = 3
    NEGATIVE_PIXELS = 6
    DIFFERENCE = 8


class HslMode(IntEnum):
    OFF = 0
    FULL_HSL = 1
    LIGHTNESS = 2
    SATURATION = 3
    HUE = 4
    LUMINANCE = 2
    HSL = 1


class CompQCState(QObject):
    """Observable reactive state holder for all xtra QC Utils parameters."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # 1. Source Plate
        self._source_plate_path: Optional[str] = None
        self._source_prefetch_progress: float = 0.0
        self._source_item_id: Optional[str] = None

        # 2. QC Real-time Color Sliders
        self._qc_gamma: float = 1.0
        self._qc_gain: float = 1.0
        self._qc_softclip: float = 1.0
        self._qc_sat_multiplier: float = 1.0
        self._qc_hue_rotation: float = 0.0

        # 3. HSL Colorspace / Grain Inspection / Highpass
        self._hsl_mode: HslMode = HslMode.OFF
        self._blur_radius: float = 3.0
        self._hipass_value: float = 3.0
        self._grain_boost: float = 5.0
        self._grain_boost_raw: float = 50.0
        self._edge_threshold: float = 0.0
        self._qc_mode: QcMode = QcMode.OFF
        self._compare_against_plate: bool = False
        self._compare_plates: bool = False

        # 4. Matte Check
        self._matte_path: Optional[str] = None
        self._matte_prefetch_progress: float = 0.0
        self._matte_item_id: Optional[str] = None
        self._enable_red: bool = True
        self._enable_green: bool = True
        self._enable_blue: bool = True
        self._enable_alpha: bool = True
        self._expr_red: str = ""
        self._expr_green: str = ""
        self._expr_blue: str = ""
        self._expr_alpha: str = ""
        self._overlay_matte_enabled: bool = False
        self._matte_is_premult: bool = True
        self._alpha_overlay_enabled: bool = False
        self._clamp_alpha: bool = False
        self._overlay_color: QColor = QColor(255, 0, 128)  # Default magenta as in mockup
        self._mix_overlay: float = 1.0
        self._greycheck_enabled: bool = False
        self._checkerboard_enabled: bool = False
        self._grey_value: float = 0.5
        self._grid_scale: float = 32.0
        self._checker_contrast: float = 0.2

        # Backward compatibility properties
        self._clipping_threshold: float = 50.0
        self._negative_over_comp: bool = False
        self._saturation_boost: float = 4.0
        self._highpass_radius: float = 5.0
        self._clamp_plate_values: bool = False
        self._check_clamped_alpha: bool = False
        self._alpha_mask_enabled: bool = False
        self._alpha_mask_color: QColor = QColor(220, 35, 35, 128)
        self._alpha_mask_opacity: float = 0.5
        self._alpha_mask_invert: bool = False
        self._flop_comp: bool = False
        self._grain_blur_radius: float = 3.0
        self._grain_compare_mode: int = 0
        self._spline_overlay_enabled: bool = False
        self._spline_stroke_color: QColor = QColor(0, 255, 204, 230)
        self._spline_stroke_width: float = 2.0
        self._spline_fill_opacity: float = 0.0

    # -------------------------------------------------------------------------
    # Source Plate Properties
    # -------------------------------------------------------------------------
    @property
    def source_plate_path(self) -> Optional[str]:
        return self._source_plate_path

    @source_plate_path.setter
    def source_plate_path(self, val: Optional[str]) -> None:
        if self._source_plate_path != val:
            self._source_plate_path = val
            self.changed.emit()

    @property
    def source_prefetch_progress(self) -> float:
        return self._source_prefetch_progress

    @source_prefetch_progress.setter
    def source_prefetch_progress(self, val: float) -> None:
        clamped = max(0.0, min(1.0, float(val)))
        if abs(self._source_prefetch_progress - clamped) > 0.001:
            self._source_prefetch_progress = clamped
            self.changed.emit()

    @property
    def source_item_id(self) -> Optional[str]:
        return self._source_item_id

    @source_item_id.setter
    def source_item_id(self, val: Optional[str]) -> None:
        if self._source_item_id != val:
            self._source_item_id = val
            self.changed.emit()

    # -------------------------------------------------------------------------
    # QC Color Sliders
    # -------------------------------------------------------------------------
    @property
    def qc_gamma(self) -> float:
        return self._qc_gamma

    @qc_gamma.setter
    def qc_gamma(self, val: float) -> None:
        v = max(0.05, float(val))
        if abs(self._qc_gamma - v) > 0.001:
            self._qc_gamma = v
            self.changed.emit()

    @property
    def qc_gain(self) -> float:
        return self._qc_gain

    @qc_gain.setter
    def qc_gain(self, val: float) -> None:
        v = max(0.0, float(val))
        if abs(self._qc_gain - v) > 0.001:
            self._qc_gain = v
            self.changed.emit()

    @property
    def qc_softclip(self) -> float:
        return self._qc_softclip

    @qc_softclip.setter
    def qc_softclip(self, val: float) -> None:
        v = max(0.0, min(1.0, float(val)))
        if abs(self._qc_softclip - v) > 0.001:
            self._qc_softclip = v
            self.changed.emit()

    @property
    def qc_sat_multiplier(self) -> float:
        return self._qc_sat_multiplier

    @qc_sat_multiplier.setter
    def qc_sat_multiplier(self, val: float) -> None:
        v = max(0.0, float(val))
        if abs(self._qc_sat_multiplier - v) > 0.001:
            self._qc_sat_multiplier = v
            self.changed.emit()

    @property
    def qc_hue_rotation(self) -> float:
        return self._qc_hue_rotation

    @qc_hue_rotation.setter
    def qc_hue_rotation(self, val: float) -> None:
        v = max(-180.0, min(180.0, float(val)))
        if abs(self._qc_hue_rotation - v) > 0.01:
            self._qc_hue_rotation = v
            self.changed.emit()

    @property
    def hue_rotation(self) -> float:
        return self._qc_hue_rotation

    @hue_rotation.setter
    def hue_rotation(self, val: float) -> None:
        self.qc_hue_rotation = val

    # -------------------------------------------------------------------------
    # HSL Colorspace / Grain / Highpass
    # -------------------------------------------------------------------------
    @property
    def hsl_mode(self) -> HslMode:
        return self._hsl_mode

    @hsl_mode.setter
    def hsl_mode(self, val: int | HslMode) -> None:
        new_val = HslMode(val)
        if self._hsl_mode != new_val:
            self._hsl_mode = new_val
            self.changed.emit()

    @property
    def blur_radius(self) -> float:
        return self._blur_radius

    @blur_radius.setter
    def blur_radius(self, val: float) -> None:
        v = max(0.0, float(val))
        if abs(self._blur_radius - v) > 0.01:
            self._blur_radius = v
            self._hipass_value = v
            self._highpass_radius = v
            self._grain_blur_radius = v
            self.changed.emit()

    @property
    def hipass_value(self) -> float:
        return self._hipass_value

    @hipass_value.setter
    def hipass_value(self, val: float) -> None:
        v = max(0.0, min(10.0, float(val)))
        if abs(self._hipass_value - v) > 0.01:
            self._hipass_value = v
            self._blur_radius = v
            self._highpass_radius = v
            self._grain_blur_radius = v
            self.changed.emit()

    @property
    def grain_boost(self) -> float:
        return self._grain_boost

    @grain_boost.setter
    def grain_boost(self, val: float) -> None:
        v = max(0.0, float(val))
        if abs(self._grain_boost - v) > 0.01:
            self._grain_boost = v
            self._grain_boost_raw = v * 10.0
            self.changed.emit()

    @property
    def grain_boost_raw(self) -> float:
        return self._grain_boost_raw

    @grain_boost_raw.setter
    def grain_boost_raw(self, val: float) -> None:
        raw = max(0.0, min(100.0, float(val)))
        if abs(self._grain_boost_raw - raw) > 0.01:
            self._grain_boost_raw = raw
            self._grain_boost = raw / 10.0
            self.changed.emit()

    @property
    def edge_threshold(self) -> float:
        return self._edge_threshold

    @edge_threshold.setter
    def edge_threshold(self, val: float) -> None:
        v = max(0.0, min(1.0, float(val)))
        if abs(self._edge_threshold - v) > 0.001:
            self._edge_threshold = v
            self.changed.emit()

    @property
    def qc_mode(self) -> QcMode:
        return self._qc_mode

    @qc_mode.setter
    def qc_mode(self, val: int | QcMode) -> None:
        new_val = QcMode(val)
        if self._qc_mode != new_val:
            self._qc_mode = new_val
            self.changed.emit()

    @property
    def compare_against_plate(self) -> bool:
        return self._compare_against_plate

    @compare_against_plate.setter
    def compare_against_plate(self, val: bool) -> None:
        b = bool(val)
        if self._compare_against_plate != b or self._compare_plates != b:
            self._compare_against_plate = b
            self._compare_plates = b
            self.changed.emit()

    @property
    def compare_plates(self) -> bool:
        return self._compare_plates

    @compare_plates.setter
    def compare_plates(self, val: bool) -> None:
        self.compare_against_plate = val

    # -------------------------------------------------------------------------
    # Matte Check Properties
    # -------------------------------------------------------------------------
    @property
    def matte_path(self) -> Optional[str]:
        return self._matte_path

    @matte_path.setter
    def matte_path(self, val: Optional[str]) -> None:
        if self._matte_path != val:
            self._matte_path = val
            self.changed.emit()

    @property
    def matte_prefetch_progress(self) -> float:
        return self._matte_prefetch_progress

    @matte_prefetch_progress.setter
    def matte_prefetch_progress(self, val: float) -> None:
        clamped = max(0.0, min(1.0, float(val)))
        if abs(self._matte_prefetch_progress - clamped) > 0.001:
            self._matte_prefetch_progress = clamped
            self.changed.emit()

    @property
    def enable_red(self) -> bool:
        return self._enable_red

    @enable_red.setter
    def enable_red(self, val: bool) -> None:
        if self._enable_red != bool(val):
            self._enable_red = bool(val)
            self.changed.emit()

    @property
    def enable_green(self) -> bool:
        return self._enable_green

    @enable_green.setter
    def enable_green(self, val: bool) -> None:
        if self._enable_green != bool(val):
            self._enable_green = bool(val)
            self.changed.emit()

    @property
    def enable_blue(self) -> bool:
        return self._enable_blue

    @enable_blue.setter
    def enable_blue(self, val: bool) -> None:
        if self._enable_blue != bool(val):
            self._enable_blue = bool(val)
            self.changed.emit()

    @property
    def enable_alpha(self) -> bool:
        return self._enable_alpha

    @enable_alpha.setter
    def enable_alpha(self, val: bool) -> None:
        if self._enable_alpha != bool(val):
            self._enable_alpha = bool(val)
            self.changed.emit()

    @property
    def expr_red(self) -> str:
        return self._expr_red

    @expr_red.setter
    def expr_red(self, val: str) -> None:
        if self._expr_red != val:
            self._expr_red = val
            self.changed.emit()

    @property
    def expr_green(self) -> str:
        return self._expr_green

    @expr_green.setter
    def expr_green(self, val: str) -> None:
        if self._expr_green != val:
            self._expr_green = val
            self.changed.emit()

    @property
    def expr_blue(self) -> str:
        return self._expr_blue

    @expr_blue.setter
    def expr_blue(self, val: str) -> None:
        if self._expr_blue != val:
            self._expr_blue = val
            self.changed.emit()

    @property
    def expr_alpha(self) -> str:
        return self._expr_alpha

    @expr_alpha.setter
    def expr_alpha(self, val: str) -> None:
        if self._expr_alpha != val:
            self._expr_alpha = val
            self.changed.emit()

    @property
    def alpha_overlay_enabled(self) -> bool:
        return self._alpha_overlay_enabled

    @alpha_overlay_enabled.setter
    def alpha_overlay_enabled(self, val: bool) -> None:
        b = bool(val)
        if self._alpha_overlay_enabled != b:
            self._alpha_overlay_enabled = b
            self._alpha_mask_enabled = b
            self.changed.emit()

    @property
    def clamp_alpha(self) -> bool:
        return self._clamp_alpha

    @clamp_alpha.setter
    def clamp_alpha(self, val: bool) -> None:
        b = bool(val)
        if self._clamp_alpha != b:
            self._clamp_alpha = b
            self.changed.emit()

    @property
    def overlay_color(self) -> QColor:
        return self._overlay_color

    @overlay_color.setter
    def overlay_color(self, val: QColor) -> None:
        if self._overlay_color != val:
            self._overlay_color = val
            self._alpha_mask_color = val
            self.changed.emit()

    @property
    def matte_item_id(self) -> Optional[str]:
        return self._matte_item_id

    @matte_item_id.setter
    def matte_item_id(self, val: Optional[str]) -> None:
        if self._matte_item_id != val:
            self._matte_item_id = val
            self.changed.emit()

    @property
    def overlay_matte_enabled(self) -> bool:
        return self._overlay_matte_enabled

    @overlay_matte_enabled.setter
    def overlay_matte_enabled(self, val: bool) -> None:
        b = bool(val)
        if self._overlay_matte_enabled != b:
            self._overlay_matte_enabled = b
            self.changed.emit()

    @property
    def matte_is_premult(self) -> bool:
        return self._matte_is_premult

    @matte_is_premult.setter
    def matte_is_premult(self, val: bool) -> None:
        b = bool(val)
        if self._matte_is_premult != b:
            self._matte_is_premult = b
            self.changed.emit()

    @property
    def greycheck_enabled(self) -> bool:
        return self._greycheck_enabled

    @greycheck_enabled.setter
    def greycheck_enabled(self, val: bool) -> None:
        b = bool(val)
        if self._greycheck_enabled != b:
            self._greycheck_enabled = b
            if b:
                self._checkerboard_enabled = False
            self.changed.emit()

    @property
    def checkerboard_enabled(self) -> bool:
        return self._checkerboard_enabled

    @checkerboard_enabled.setter
    def checkerboard_enabled(self, val: bool) -> None:
        b = bool(val)
        if self._checkerboard_enabled != b:
            self._checkerboard_enabled = b
            if b:
                self._greycheck_enabled = False
            self.changed.emit()

    @property
    def grey_value(self) -> float:
        return self._grey_value

    @grey_value.setter
    def grey_value(self, val: float) -> None:
        v = max(0.0, min(1.0, float(val)))
        if abs(self._grey_value - v) > 0.001:
            self._grey_value = v
            self.changed.emit()

    @property
    def grid_scale(self) -> float:
        return self._grid_scale

    @grid_scale.setter
    def grid_scale(self, val: float) -> None:
        v = max(2.0, min(256.0, float(val)))
        if abs(self._grid_scale - v) > 0.1:
            self._grid_scale = v
            self.changed.emit()

    @property
    def checker_contrast(self) -> float:
        return self._checker_contrast

    @checker_contrast.setter
    def checker_contrast(self, val: float) -> None:
        v = max(0.0, min(1.0, float(val)))
        if abs(self._checker_contrast - v) > 0.001:
            self._checker_contrast = v
            self.changed.emit()

    @property
    def mix_overlay(self) -> float:
        return self._mix_overlay

    @mix_overlay.setter
    def mix_overlay(self, val: float) -> None:
        v = max(0.0, min(1.0, float(val)))
        if abs(self._mix_overlay - v) > 0.001:
            self._mix_overlay = v
            self._alpha_mask_opacity = v
            self.changed.emit()

    # -------------------------------------------------------------------------
    # Backward Compatibility Layer
    # -------------------------------------------------------------------------
    @property
    def clipping_threshold(self) -> float:
        return self._clipping_threshold

    @clipping_threshold.setter
    def clipping_threshold(self, val: float) -> None:
        if self._clipping_threshold != val:
            self._clipping_threshold = val
            self.changed.emit()

    @property
    def negative_over_comp(self) -> bool:
        return self._negative_over_comp

    @negative_over_comp.setter
    def negative_over_comp(self, val: bool) -> None:
        if self._negative_over_comp != val:
            self._negative_over_comp = val
            self.changed.emit()

    @property
    def saturation_boost(self) -> float:
        return self._saturation_boost

    @saturation_boost.setter
    def saturation_boost(self, val: float) -> None:
        if self._saturation_boost != val:
            self._saturation_boost = val
            self.changed.emit()

    @property
    def highpass_radius(self) -> float:
        return self._highpass_radius

    @highpass_radius.setter
    def highpass_radius(self, val: float) -> None:
        if self._highpass_radius != val:
            self._highpass_radius = val
            self._blur_radius = val
            self.changed.emit()

    @property
    def clamp_plate_values(self) -> bool:
        return self._clamp_plate_values

    @clamp_plate_values.setter
    def clamp_plate_values(self, val: bool) -> None:
        if self._clamp_plate_values != val:
            self._clamp_plate_values = val
            self.changed.emit()

    @property
    def check_clamped_alpha(self) -> bool:
        return self._check_clamped_alpha

    @check_clamped_alpha.setter
    def check_clamped_alpha(self, val: bool) -> None:
        if self._check_clamped_alpha != val:
            self._check_clamped_alpha = val
            self.changed.emit()

    @property
    def alpha_mask_enabled(self) -> bool:
        return self._alpha_overlay_enabled

    @alpha_mask_enabled.setter
    def alpha_mask_enabled(self, val: bool) -> None:
        self.alpha_overlay_enabled = val

    @property
    def alpha_mask_color(self) -> QColor:
        return self._overlay_color

    @alpha_mask_color.setter
    def alpha_mask_color(self, val: QColor) -> None:
        self.overlay_color = val

    @property
    def alpha_mask_opacity(self) -> float:
        return self._mix_overlay

    @alpha_mask_opacity.setter
    def alpha_mask_opacity(self, val: float) -> None:
        self.mix_overlay = val

    @property
    def alpha_mask_invert(self) -> bool:
        return self._alpha_mask_invert

    @alpha_mask_invert.setter
    def alpha_mask_invert(self, val: bool) -> None:
        if self._alpha_mask_invert != val:
            self._alpha_mask_invert = val
            self.changed.emit()

    @property
    def flop_comp(self) -> bool:
        return self._flop_comp

    @flop_comp.setter
    def flop_comp(self, val: bool) -> None:
        if self._flop_comp != val:
            self._flop_comp = val
            self.changed.emit()

    @property
    def grain_blur_radius(self) -> float:
        return self._blur_radius

    @grain_blur_radius.setter
    def grain_blur_radius(self, val: float) -> None:
        self.blur_radius = val

    @property
    def grain_compare_mode(self) -> int:
        return self._grain_compare_mode

    @grain_compare_mode.setter
    def grain_compare_mode(self, val: int) -> None:
        if self._grain_compare_mode != val:
            self._grain_compare_mode = val
            self.changed.emit()

    @property
    def spline_overlay_enabled(self) -> bool:
        return self._spline_overlay_enabled

    @spline_overlay_enabled.setter
    def spline_overlay_enabled(self, val: bool) -> None:
        if self._spline_overlay_enabled != val:
            self._spline_overlay_enabled = val
            self.changed.emit()

    @property
    def spline_stroke_color(self) -> QColor:
        return self._spline_stroke_color

    @spline_stroke_color.setter
    def spline_stroke_color(self, val: QColor) -> None:
        if self._spline_stroke_color != val:
            self._spline_stroke_color = val
            self.changed.emit()

    @property
    def spline_stroke_width(self) -> float:
        return self._spline_stroke_width

    @spline_stroke_width.setter
    def spline_stroke_width(self, val: float) -> None:
        if self._spline_stroke_width != val:
            self._spline_stroke_width = val
            self.changed.emit()

    @property
    def spline_fill_opacity(self) -> float:
        return self._spline_fill_opacity

    @spline_fill_opacity.setter
    def spline_fill_opacity(self, val: float) -> None:
        if self._spline_fill_opacity != val:
            self._spline_fill_opacity = val
            self.changed.emit()

    # -------------------------------------------------------------------------
    # Reset All Parameters to Neutral Default
    # -------------------------------------------------------------------------
    def reset_defaults(self) -> None:
        """Reset all QC parameters back to their neutral/off state."""
        self._qc_gamma = 1.0
        self._qc_gain = 1.0
        self._qc_softclip = 1.0
        self._qc_sat_multiplier = 1.0
        self._qc_hue_rotation = 0.0

        self._hsl_mode = HslMode.OFF
        self._blur_radius = 3.0
        self._hipass_value = 3.0
        self._grain_boost = 5.0
        self._grain_boost_raw = 50.0
        self._edge_threshold = 0.0
        self._qc_mode = QcMode.OFF
        self._compare_against_plate = False
        self._compare_plates = False

        self._enable_red = True
        self._enable_green = True
        self._enable_blue = True
        self._enable_alpha = True
        self._expr_red = ""
        self._expr_green = ""
        self._expr_blue = ""
        self._expr_alpha = ""
        self._overlay_matte_enabled = False
        self._matte_is_premult = True
        self._alpha_overlay_enabled = False
        self._clamp_alpha = False
        self._overlay_color = QColor(255, 0, 128)
        self._mix_overlay = 1.0
        self._greycheck_enabled = False
        self._checkerboard_enabled = False
        self._grey_value = 0.5
        self._grid_scale = 32.0
        self._checker_contrast = 0.2

        # Legacy reset
        self._clipping_threshold = 50.0
        self._negative_over_comp = False
        self._saturation_boost = 4.0
        self._highpass_radius = 5.0
        self._clamp_plate_values = False
        self._check_clamped_alpha = False
        self._alpha_mask_enabled = False
        self._alpha_mask_opacity = 0.5
        self._alpha_mask_invert = False
        self._flop_comp = False
        self._grain_blur_radius = 3.0
        self._grain_compare_mode = 0

        self.changed.emit()


# Semantic alias
XtraQCState = CompQCState
