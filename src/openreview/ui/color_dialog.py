"""
Interactive Color Adjustments Dialog for OpenReview.
Provides live interactive controls for Gain (Master & RGB), Offset (Master & RGB),
Gamma, Saturation, Contrast, Hue, Display Brightness, Invert Colors, and Out-of-Range highlights.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSlider,
    QDoubleSpinBox,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QAbstractSpinBox,
)

from openreview.widgets.draggable_scroll_area import BlenderScrollArea

from openreview.color.lut_manager import ColorGradeSettings


class ClickResetSlider(QSlider):
    """QSlider that resets to default when Ctrl+Clicked anywhere on its track."""
    resetRequested = Signal()

    def mousePressEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.resetRequested.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class SliderSpinRow(QWidget):
    """Unified horizontal row containing Label, Slider, Spinbox, and Reset button."""

    valueChanged = Signal(float)

    def __init__(
        self,
        name: str,
        min_val: float,
        max_val: float,
        default_val: float,
        step: float = 0.05,
        decimals: int = 2,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.default_val = default_val
        self.step = step
        self.scale_factor = 100.0 if decimals <= 2 else 1000.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self.label = QLabel(name, self)
        self.label.setFixedWidth(80)
        self.label.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(self.label)

        self.slider = ClickResetSlider(Qt.Orientation.Horizontal, self)
        self.slider.setToolTip(f"{name} | Ctrl+Click anywhere to reset to {default_val}")
        self.slider.resetRequested.connect(self.reset)
        self.slider.setRange(int(min_val * self.scale_factor), int(max_val * self.scale_factor))
        self.slider.setValue(int(default_val * self.scale_factor))
        self.slider.setTracking(True)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        self.spin = QDoubleSpinBox(self)
        self.spin.setRange(min_val, max_val)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(decimals)
        self.spin.setValue(default_val)
        self.spin.setFixedWidth(58)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self.spin)

        self.reset_btn = QPushButton("↺", self)
        self.reset_btn.setFixedSize(18, 18)
        self.reset_btn.setToolTip(f"Reset {name} to default ({default_val})")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #888888;
                border: 1px solid #3c3c3c;
                border-radius: 2px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e5a823;
                color: #111111;
            }
        """)
        self.reset_btn.clicked.connect(self.reset)
        layout.addWidget(self.reset_btn)

    def _on_slider_changed(self, ival: int) -> None:
        val = ival / self.scale_factor
        self.spin.blockSignals(True)
        self.spin.setValue(val)
        self.spin.blockSignals(False)
        self.valueChanged.emit(val)

    def _on_spin_changed(self, val: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(val * self.scale_factor)))
        self.slider.blockSignals(False)
        self.valueChanged.emit(val)

    def value(self) -> float:
        return self.spin.value()

    def set_value(self, val: float) -> None:
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(val)
        self.slider.setValue(int(round(val * self.scale_factor)))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)

    def reset(self) -> None:
        self.set_value(self.default_val)
        self.valueChanged.emit(self.default_val)


class ColorAdjustmentsWidget(QWidget):
    """Widget for interactive studio color grading and calibration edits."""

    colorGradeChanged = Signal(ColorGradeSettings)

    def __init__(self, current_settings: Optional[ColorGradeSettings] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = current_settings or ColorGradeSettings()
        self.setMinimumWidth(380)
        self.setMaximumHeight(540)
        self._setup_ui()
        self._load_from_settings(self.settings)

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                font-size: 11px;
                font-weight: bold;
                color: #e5a823;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }
            QCheckBox {
                color: #cccccc;
                font-size: 11px;
            }
            QPushButton#actionBtn {
                background-color: #2c2c2c;
                color: #dddddd;
                border: 1px solid #444444;
                padding: 5px 12px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#actionBtn:hover {
                background-color: #e5a823;
                color: #111111;
                border-color: #f0b429;
            }
            /* Modern Minimal Rounded ScrollBars matching Browser */
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3d3d3d;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed {
                background: #e5a823;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #3d3d3d;
                min-width: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed {
                background: #e5a823;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            QScrollBar::corner {
                background: transparent;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Scroll Area for all adjustment controls
        scroll = BlenderScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content_w = QWidget(scroll)
        content_layout = QVBoxLayout(content_w)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(10)

        # 1. Tone & Grade Group (Contrast, Gamma & Saturation moved to top)
        tone_group = QGroupBox("Contrast, Gamma & Saturation", content_w)
        tone_layout = QVBoxLayout(tone_group)
        self.row_gamma = SliderSpinRow("Gamma", 0.1, 4.0, 1.0, 0.05, 2, tone_group)
        self.row_contrast = SliderSpinRow("Contrast", 0.0, 3.0, 1.0, 0.05, 2, tone_group)
        self.row_sat = SliderSpinRow("Saturation", 0.0, 3.0, 1.0, 0.05, 2, tone_group)
        self.row_hue = SliderSpinRow("Hue Rotation", -180.0, 180.0, 0.0, 1.0, 1, tone_group)
        self.row_brightness = SliderSpinRow("Display Brightness", -5.0, 5.0, 0.0, 0.1, 2, tone_group)
        self.row_gamma.valueChanged.connect(self._emit_changes)
        self.row_contrast.valueChanged.connect(self._emit_changes)
        self.row_sat.valueChanged.connect(self._emit_changes)
        self.row_hue.valueChanged.connect(self._emit_changes)
        self.row_brightness.valueChanged.connect(self._emit_changes)
        tone_layout.addWidget(self.row_gamma)
        tone_layout.addWidget(self.row_contrast)
        tone_layout.addWidget(self.row_sat)
        tone_layout.addWidget(self.row_hue)
        tone_layout.addWidget(self.row_brightness)
        content_layout.addWidget(tone_group)

        # 2. Gain Group
        gain_group = QGroupBox("Gain (Scene-Linear Multiplier)", content_w)
        gain_layout = QVBoxLayout(gain_group)
        self.row_gain_m = SliderSpinRow("Master Gain", 0.0, 4.0, 1.0, 0.05, 2, gain_group)
        self.row_gain_r = SliderSpinRow("Red Gain", 0.0, 4.0, 1.0, 0.05, 2, gain_group)
        self.row_gain_g = SliderSpinRow("Green Gain", 0.0, 4.0, 1.0, 0.05, 2, gain_group)
        self.row_gain_b = SliderSpinRow("Blue Gain", 0.0, 4.0, 1.0, 0.05, 2, gain_group)
        self.row_gain_m.valueChanged.connect(self._on_master_gain_changed)
        self.row_gain_r.valueChanged.connect(self._on_rgb_gain_changed)
        self.row_gain_g.valueChanged.connect(self._on_rgb_gain_changed)
        self.row_gain_b.valueChanged.connect(self._on_rgb_gain_changed)
        gain_layout.addWidget(self.row_gain_m)
        gain_layout.addWidget(self.row_gain_r)
        gain_layout.addWidget(self.row_gain_g)
        gain_layout.addWidget(self.row_gain_b)
        content_layout.addWidget(gain_group)

        # 3. Offset Group
        offset_group = QGroupBox("Color Offsets (Lift / Black Level)", content_w)
        offset_layout = QVBoxLayout(offset_group)
        self.row_off_m = SliderSpinRow("Master Offset", -1.0, 1.0, 0.0, 0.01, 3, offset_group)
        self.row_off_r = SliderSpinRow("Red Offset", -1.0, 1.0, 0.0, 0.01, 3, offset_group)
        self.row_off_g = SliderSpinRow("Green Offset", -1.0, 1.0, 0.0, 0.01, 3, offset_group)
        self.row_off_b = SliderSpinRow("Blue Offset", -1.0, 1.0, 0.0, 0.01, 3, offset_group)
        self.row_off_m.valueChanged.connect(self._on_master_offset_changed)
        self.row_off_r.valueChanged.connect(self._on_rgb_offset_changed)
        self.row_off_g.valueChanged.connect(self._on_rgb_offset_changed)
        self.row_off_b.valueChanged.connect(self._on_rgb_offset_changed)
        offset_layout.addWidget(self.row_off_m)
        offset_layout.addWidget(self.row_off_r)
        offset_layout.addWidget(self.row_off_g)
        offset_layout.addWidget(self.row_off_b)
        content_layout.addWidget(offset_group)

        # 4. Calibration & Toggles Group
        opt_group = QGroupBox("Display & Diagnostic Overlays", content_w)
        opt_layout = QVBoxLayout(opt_group)
        self.chk_invert = QCheckBox("Invert Colors", opt_group)
        self.chk_invert.toggled.connect(self._emit_changes)
        self.chk_out_of_range = QCheckBox("Highlight Out-of-Range Colors (Magenta/Cyan)", opt_group)
        self.chk_out_of_range.toggled.connect(self._emit_changes)
        self.chk_lut_enable = QCheckBox("Enable Active 3D LUT", opt_group)
        self.chk_lut_enable.setChecked(True)
        self.chk_lut_enable.toggled.connect(self._emit_changes)
        self.chk_cdl_enable = QCheckBox("Enable Active ASC CDL", opt_group)
        self.chk_cdl_enable.setChecked(True)
        self.chk_cdl_enable.toggled.connect(self._emit_changes)

        opt_layout.addWidget(self.chk_invert)
        opt_layout.addWidget(self.chk_out_of_range)
        opt_layout.addWidget(self.chk_lut_enable)
        opt_layout.addWidget(self.chk_cdl_enable)
        content_layout.addWidget(opt_group)

        scroll.setWidget(content_w)
        main_layout.addWidget(scroll, stretch=1)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        self.btn_reset_all = QPushButton("Reset All Colors", self)
        self.btn_reset_all.setObjectName("actionBtn")
        self.btn_reset_all.clicked.connect(self.reset_all)
        btn_box.addWidget(self.btn_reset_all)

        btn_box.addStretch()

        self.btn_close = QPushButton("Close", self)
        self.btn_close.setObjectName("actionBtn")
        self.btn_close.clicked.connect(self._on_close_clicked)
        btn_box.addWidget(self.btn_close)

        main_layout.addLayout(btn_box)

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

    def _load_from_settings(self, s: ColorGradeSettings) -> None:
        self._block_updates = True
        try:
            self.row_gain_r.set_value(s.gain[0])
            self.row_gain_g.set_value(s.gain[1])
            self.row_gain_b.set_value(s.gain[2])
            self.row_gain_m.set_value(sum(s.gain) / 3.0)

            self.row_off_r.set_value(s.offset[0])
            self.row_off_g.set_value(s.offset[1])
            self.row_off_b.set_value(s.offset[2])
            self.row_off_m.set_value(sum(s.offset) / 3.0)

            self.row_gamma.set_value(s.gamma)
            self.row_contrast.set_value(s.contrast)
            self.row_sat.set_value(s.saturation)
            self.row_hue.set_value(s.hue)
            self.row_brightness.set_value(s.brightness)
            self.chk_invert.setChecked(s.invert_colors)
            self.chk_out_of_range.setChecked(s.show_out_of_range)
            self.chk_lut_enable.setChecked(s.lut_enabled)
            self.chk_cdl_enable.setChecked(s.cdl_enabled)
        finally:
            self._block_updates = False

    def _on_master_gain_changed(self, val: float) -> None:
        self.row_gain_r.set_value(val)
        self.row_gain_g.set_value(val)
        self.row_gain_b.set_value(val)
        self._emit_changes()

    def _on_rgb_gain_changed(self, _: float) -> None:
        self._emit_changes()

    def _on_master_offset_changed(self, val: float) -> None:
        self.row_off_r.set_value(val)
        self.row_off_g.set_value(val)
        self.row_off_b.set_value(val)
        self._emit_changes()

    def _on_rgb_offset_changed(self, _: float) -> None:
        self._emit_changes()

    def _emit_changes(self) -> None:
        if getattr(self, "_block_updates", False):
            return
        self.settings.gain = (
            float(self.row_gain_r.value()),
            float(self.row_gain_g.value()),
            float(self.row_gain_b.value()),
        )
        self.settings.offset = (
            float(self.row_off_r.value()),
            float(self.row_off_g.value()),
            float(self.row_off_b.value()),
        )
        self.settings.gamma = float(self.row_gamma.value())
        self.settings.contrast = float(self.row_contrast.value())
        self.settings.saturation = float(self.row_sat.value())
        self.settings.hue = float(self.row_hue.value())
        self.settings.brightness = float(self.row_brightness.value())
        self.settings.invert_colors = self.chk_invert.isChecked()
        self.settings.show_out_of_range = self.chk_out_of_range.isChecked()
        self.settings.lut_enabled = self.chk_lut_enable.isChecked()
        self.settings.cdl_enabled = self.chk_cdl_enable.isChecked()

        self.colorGradeChanged.emit(self.settings)

    def reset_all(self) -> None:
        self.settings.reset()
        self._load_from_settings(self.settings)
        self._emit_changes()


class ColorAdjustmentsDialog(QDialog):
    """Dialog wrapper around ColorAdjustmentsWidget for standalone usage."""

    colorGradeChanged = Signal(ColorGradeSettings)

    def __init__(self, current_settings: Optional[ColorGradeSettings] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Color Adjustments & Grading")
        self.resize(460, 600)
        self.setStyleSheet("background-color: #1c1c1c;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.widget = ColorAdjustmentsWidget(current_settings, self)
        self.widget.colorGradeChanged.connect(self.colorGradeChanged.emit)
        layout.addWidget(self.widget)

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def reset_all(self) -> None:
        self.widget.reset_all()
