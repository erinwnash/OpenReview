"""
Stereoscopic 3D HUD Widget for OpenReview.
Provides togglable floating widget to control stereo 3D display modes.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
)


class HUDStereoWidget(QWidget):
    """Interactive widget for stereoscopic 3D display modes & parallax adjustments."""

    stereo_mode_changed = Signal(int)  # 0: Off, 1: Left, 2: Right, 3: Anaglyph, 4: SBS, 5: Diff
    mode_changed = stereo_mode_changed
    offset_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self._current_mode: int = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr_lbl = QLabel("Stereoscopic 3D Mode", self)
        hdr_lbl.setStyleSheet("font-weight: bold; color: #e5a823; font-size: 11px;")
        layout.addWidget(hdr_lbl)

        self.btn_group = QButtonGroup(self)
        modes = [
            (0, "2D (Off)"),
            (1, "Left Eye Only"),
            (2, "Right Eye Only"),
            (3, "Anaglyph (Red-Cyan)"),
            (4, "Side-by-Side (SBS)"),
            (5, "Difference"),
        ]

        for mode_id, text in modes:
            rb = QRadioButton(text, self)
            rb.setStyleSheet("color: #cccccc; font-size: 11px;")
            if mode_id == 0:
                rb.setChecked(True)
            self.btn_group.addButton(rb, mode_id)
            layout.addWidget(rb)

        self.btn_group.idToggled.connect(self._on_mode_toggled)

        layout.addSpacing(4)
        offset_box = QHBoxLayout()
        offset_lbl = QLabel("Eye Offset / Parallax:", self)
        offset_lbl.setStyleSheet("color: #888888; font-size: 10px;")
        offset_box.addWidget(offset_lbl)

        self.spin_offset = QDoubleSpinBox(self)
        self.spin_offset.setRange(-200.0, 200.0)
        self.spin_offset.setValue(0.0)
        self.spin_offset.setSingleStep(1.0)
        self.spin_offset.setSuffix(" px")
        from openreview.ui.theme import get_spinbox_arrow_stylesheet
        self.spin_offset.setStyleSheet("QDoubleSpinBox { font-size: 10px; }" + get_spinbox_arrow_stylesheet())
        self.spin_offset.valueChanged.connect(self.offset_changed.emit)
        offset_box.addWidget(self.spin_offset)
        layout.addLayout(offset_box)

    def set_mode(self, mode_id: int) -> None:
        self._current_mode = mode_id
        btn = self.btn_group.button(mode_id)
        if btn:
            btn.setChecked(True)

    def _on_mode_toggled(self, button_id: int, checked: bool) -> None:
        if checked:
            self._current_mode = button_id
            self.stereo_mode_changed.emit(button_id)
