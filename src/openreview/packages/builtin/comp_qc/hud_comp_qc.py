"""
xtra QC Utils HUD & Dock Widget.
Restyled to match OpenReview's native 3DEqualizer-inspired Dark Slate & Warm Amber (#e5a823) aesthetic.
Featuring Source Plate inspection, real-time non-destructive QC color grading, HSL soloing,
grain analysis, highpass edge checks, RGBA matte expression evaluation,
and alpha overlay blending.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QEvent, QObject, QRect, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QMouseEvent, QDragEnterEvent, QDropEvent, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QCheckBox,
    QSlider,
    QDoubleSpinBox,
    QPushButton,
    QLineEdit,
    QProgressBar,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QDockWidget,
    QApplication,
    QColorDialog,
    QToolButton,
    QBoxLayout,
    QMenu,
)

from openreview.packages.builtin.comp_qc.qc_state import CompQCState, QcMode, HslMode
from openreview.color.shader_builder import validate_and_compile_expression
from openreview.ui.dock_title_bar import TabbedDockTitleBar

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 1. Blender-style Middle Mouse Button Scroll Area
# -----------------------------------------------------------------------------
from openreview.widgets.draggable_scroll_area import BlenderScrollArea


# -----------------------------------------------------------------------------
# 2. Native Collapsible Section Header (Warm Amber Accent)
# -----------------------------------------------------------------------------
class CollapsibleSectionHeader(QWidget):
    """Clickable accordion header matching native dark slate & amber aesthetic."""

    toggled = Signal(bool)  # is_expanded

    def __init__(self, title: str, parent: Optional[QWidget] = None, expanded: bool = False) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        self.lbl_arrow = QLabel("▼" if self._expanded else "▶", self)
        self.lbl_arrow.setStyleSheet(
            "color: #e5a823; font-size: 10px; font-weight: bold;"
            if self._expanded
            else "color: #777777; font-size: 10px;"
        )
        layout.addWidget(self.lbl_arrow)

        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold; letter-spacing: 0.3px;")
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        self.setStyleSheet("""
            CollapsibleSectionHeader {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 2px;
            }
            CollapsibleSectionHeader:hover {
                background-color: #2a2a2a;
                border: 1px solid #444444;
            }
        """)

    def set_title(self, title: str) -> None:
        self.lbl_title.setText(title)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self.lbl_arrow.setText("▼" if self._expanded else "▶")
            self.lbl_arrow.setStyleSheet(
                "color: #e5a823; font-size: 10px; font-weight: bold;"
                if self._expanded
                else "color: #777777; font-size: 10px;"
            )
            self.toggled.emit(self._expanded)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_expanded(not self._expanded)
            event.accept()
            return
        super().mousePressEvent(event)


# -----------------------------------------------------------------------------
# 3. Native File Sequence Drop Zone (Precision Slate & Amber)
# -----------------------------------------------------------------------------
# 3. Native File Sequence Drop Zone (with Aspect-Fitted Thumbnail Preview)
# -----------------------------------------------------------------------------
class DropZoneWidget(QFrame):
    """Drag and drop area with native dark slate styling, thumbnail preview, and amber hover highlight."""

    file_dropped = Signal(str)

    def __init__(self, default_text: str, parent: Optional[QWidget] = None, height: int = 70) -> None:
        super().__init__(parent)
        self._default_text = default_text
        self.setAcceptDrops(True)
        self.setFixedHeight(height)

        self._inner_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._inner_layout.setContentsMargins(6, 4, 6, 4)
        self._inner_layout.setSpacing(6)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_thumb = QLabel(self)
        self.lbl_thumb.setFixedSize(60, 38)
        self.lbl_thumb.setScaledContents(True)
        self.lbl_thumb.setStyleSheet("background-color: #0d0d0d; border: 1px solid #333333; border-radius: 2px;")
        self.lbl_thumb.hide()
        self._inner_layout.addWidget(self.lbl_thumb)

        self.lbl_text = QLabel(default_text, self)
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color: #a0a0a0; font-size: 11px; font-weight: 500;")
        self._inner_layout.addWidget(self.lbl_text)

        self._normal_style = """
            DropZoneWidget {
                background-color: #161616;
                border: 1px solid #333333;
                border-radius: 2px;
            }
            DropZoneWidget:hover {
                background-color: #1c1c1c;
                border: 1px solid #444444;
            }
        """
        self._hover_style = """
            DropZoneWidget {
                background-color: #241e12;
                border: 1px dashed #e5a823;
                border-radius: 2px;
            }
        """
        self.setStyleSheet(self._normal_style)

    def reset_text(self) -> None:
        self.lbl_thumb.clear()
        self.lbl_thumb.hide()
        self.lbl_text.setText(self._default_text)
        self.lbl_text.setStyleSheet("color: #a0a0a0; font-size: 11px; font-weight: 500;")
        self._inner_layout.setDirection(QBoxLayout.Direction.TopToBottom)

    def set_loaded_text(self, text: str) -> None:
        self.lbl_text.setText(text)
        self.lbl_text.setStyleSheet("color: #e5a823; font-size: 11px; font-weight: bold; font-family: monospace;")

    def set_thumbnail(self, pixmap: QPixmap, text: str = "") -> None:
        """Display an aspect-fit media thumbnail beside sequence info."""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(60, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_thumb.setPixmap(scaled)
            self.lbl_thumb.show()
            self._inner_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        if text:
            self.set_loaded_text(text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(self._hover_style)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QEvent) -> None:
        self.setStyleSheet(self._normal_style)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._normal_style)
        path = ""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
        elif event.mimeData().hasText():
            path = event.mimeData().text().strip()

        if path:
            event.acceptProposedAction()
            self.set_loaded_text(f"Loaded: {Path(path).name}")
            self.file_dropped.emit(path)
        else:
            event.ignore()


# -----------------------------------------------------------------------------
# 4. Native Prefetch Progress Bar (Warm Amber Track)
# -----------------------------------------------------------------------------
class PrefetchStatusRow(QWidget):
    """Displays progress bar with native amber chunk and cache status label."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(18)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #161616;
                border: 1px solid #333333;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #e5a823;
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.progress, 1)

        self.lbl_info = QLabel("Prefetch status 0% cached", self)
        self.lbl_info.setStyleSheet("color: #888888; font-size: 10px; font-family: monospace;")
        layout.addWidget(self.lbl_info)

    def set_progress(self, percent: float) -> None:
        p = int(round(max(0.0, min(100.0, percent * 100.0))))
        self.progress.setValue(p)
        self.lbl_info.setText(f"Prefetch status {p}% cached")


# -----------------------------------------------------------------------------
# 5. Native Labeled Slider Row (Smooth, Ctrl+Click Reset, Wheel Ignored)
# -----------------------------------------------------------------------------
class NonWheelSlider(QSlider):
    """QSlider that ignores mouse wheel events and supports Ctrl+Click reset."""

    def __init__(self, orientation, parent=None, on_reset=None):
        super().__init__(orientation, parent)
        self._on_reset = on_reset

    def wheelEvent(self, event):
        event.ignore()

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if callable(self._on_reset):
                self._on_reset()
            event.accept()
            return
        super().mousePressEvent(event)


class NonWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that ignores mouse wheel events."""

    def wheelEvent(self, event):
        event.ignore()


class LabeledSliderRow(QWidget):
    """Horizontal slider row with manual spinbox input, reset button, and wheel suppression."""

    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default_val: float,
        parent: Optional[QWidget] = None,
        scale: int = 100,
        decimals: int = 2,
    ) -> None:
        super().__init__(parent)
        self._min_val = min_val
        self._max_val = max_val
        self._default_val = default_val
        self._scale = scale
        self._decimals = decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self.lbl_name = QLabel(label, self)
        self.lbl_name.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        header.addWidget(self.lbl_name)
        header.addStretch()

        # Manual numeric input
        self.spin = NonWheelDoubleSpinBox(self)
        self.spin.setRange(min_val, max_val)
        self.spin.setDecimals(decimals)
        step = 1.0 / float(scale) if scale > 0 else 0.01
        self.spin.setSingleStep(max(0.01, step))
        self.spin.setValue(default_val)
        self.spin.setFixedWidth(54)
        self.spin.setFixedHeight(20)
        self.spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #161616;
                color: #e5a823;
                border: 1px solid #333333;
                border-radius: 2px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 2px;
            }
            QDoubleSpinBox:hover, QDoubleSpinBox:focus {
                border-color: #e5a823;
            }
        """)
        self.spin.valueChanged.connect(self._on_spin_changed)
        header.addWidget(self.spin)

        # Reset icon button
        self.btn_reset = QToolButton(self)
        self.btn_reset.setText("↺")
        self.btn_reset.setToolTip(f"Reset {label} to default ({default_val}) [or Ctrl+Click slider]")
        self.btn_reset.setFixedSize(18, 18)
        self.btn_reset.setStyleSheet("""
            QToolButton {
                background-color: #252525;
                color: #888888;
                border: 1px solid #333333;
                border-radius: 2px;
                font-size: 10px;
            }
            QToolButton:hover {
                background-color: #383838;
                color: #e5a823;
                border-color: #e5a823;
            }
        """)
        self.btn_reset.clicked.connect(self.reset_to_default)
        header.addWidget(self.btn_reset)
        layout.addLayout(header)

        # Non-wheel slider
        self.slider = NonWheelSlider(Qt.Orientation.Horizontal, self, on_reset=self.reset_to_default)
        self.slider.setRange(int(round(min_val * scale)), int(round(max_val * scale)))
        self.slider.setValue(int(round(default_val * scale)))
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #252525;
                border: 1px solid #383838;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #333333;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #b0b0b0;
                border: 1px solid #161616;
                width: 10px;
                height: 14px;
                margin: -5px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal:hover {
                background: #e5a823;
                border-color: #f0b83b;
            }
            QSlider::handle:horizontal:pressed {
                background: #f0b83b;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

    @property
    def lbl_val(self):
        """Backward compatibility alias for tests accessing lbl_val."""
        return self.spin

    def _on_slider_moved(self, val_int: int) -> None:
        fval = float(val_int) / float(self._scale)
        self.spin.blockSignals(True)
        self.spin.setValue(fval)
        self.spin.blockSignals(False)
        self.value_changed.emit(fval)

    def _on_spin_changed(self, fval: float) -> None:
        val_int = int(round(fval * self._scale))
        self.slider.blockSignals(True)
        self.slider.setValue(val_int)
        self.slider.blockSignals(False)
        self.value_changed.emit(fval)

    def get_value(self) -> float:
        return self.spin.value()

    def value(self) -> float:
        return self.spin.value()

    def set_value(self, fval: float, emit_signal: bool = False) -> None:
        val_int = int(round(fval * self._scale))
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(val_int)
        self.spin.setValue(fval)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)
        if emit_signal:
            self.value_changed.emit(fval)

    def reset_to_default(self) -> None:
        self.set_value(self._default_val, emit_signal=True)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.reset_to_default()
        event.accept()


# -----------------------------------------------------------------------------
# 6. Native Dots Divider Widget
# -----------------------------------------------------------------------------
class DotsSeparator(QFrame):
    """Subtle horizontal divider line matching OpenReview menus."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedHeight(10)
        self.setStyleSheet("color: #2b2b2b; background-color: transparent;")


def _create_checker_icon(size: int = 14) -> QIcon:
    """Generate crisp alternating light/dark checkerboard preview icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    step = size // 2
    c1 = QColor("#cccccc")
    c2 = QColor("#444444")
    painter.fillRect(0, 0, step, step, c1)
    painter.fillRect(step, 0, size - step, step, c2)
    painter.fillRect(0, step, step, size - step, c2)
    painter.fillRect(step, step, size - step, size - step, c1)
    painter.setPen(QColor("#222222"))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return QIcon(pix)


def _create_grey_icon(size: int = 14) -> QIcon:
    """Generate crisp neutral grey preview icon."""
    pix = QPixmap(size, size)
    pix.fill(QColor("#7f7f7f"))
    painter = QPainter(pix)
    painter.setPen(QColor("#333333"))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return QIcon(pix)


# -----------------------------------------------------------------------------
# 7. Main xtra QC Utils HUD Widget
# -----------------------------------------------------------------------------
class XtraQCWidget(QWidget):
    """
    Complete UI control widget for xtra QC Utils with native 3DEqualizer Dark Slate & Warm Amber styling.
    """

    source_plate_dropped = Signal(str)
    source_prefetch_requested = Signal()
    source_unload_requested = Signal()

    matte_dropped = Signal(str)
    matte_prefetch_requested = Signal()
    matte_unload_requested = Signal()

    reset_requested = Signal()
    latched = Signal(bool)

    # Backward-compatible signals
    splines_loaded = Signal(list)
    splines_cleared = Signal()
    scan_missing_frames_requested = Signal()

    def __init__(self, state: CompQCState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self._setup_ui()
        self._bind_state()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # User interacted with widget: latch it so releasing Q does not auto-close
        self.latched.emit(True)
        super().mousePressEvent(event)

    def _setup_ui(self) -> None:
        self.setMinimumWidth(310)
        self.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0; font-size: 11px;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(5)

        # Title bar with Amber header
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 2)
        title_bar.setSpacing(4)

        self.lbl_header = QLabel("xtra QC Utils", self)
        self.lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_header.setStyleSheet("""
            background-color: #242424;
            color: #e5a823;
            font-size: 13px;
            font-weight: bold;
            padding: 4px;
            border: 1px solid #333333;
            border-radius: 2px;
            letter-spacing: 0.5px;
        """)
        title_bar.addWidget(self.lbl_header, 1)

        self.btn_pin = QToolButton(self)
        self.btn_pin.setText("📌")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setToolTip("Pin panel open (prevent auto-closing when releasing 'Q')")
        self.btn_pin.setStyleSheet("""
            QToolButton {
                background-color: #242424;
                color: #777777;
                border: 1px solid #333333;
                border-radius: 2px;
                padding: 3px;
                font-size: 12px;
            }
            QToolButton:hover {
                border-color: #555555;
            }
            QToolButton:checked {
                background-color: #e5a823;
                color: #121212;
                border-color: #f0b83b;
            }
        """)
        self.btn_pin.toggled.connect(lambda chk: self.latched.emit(chk))
        title_bar.addWidget(self.btn_pin)
        root_layout.addLayout(title_bar)

        # Scroll area for compact height
        scroll = BlenderScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(2, 2, 4, 2)
        self._content_layout.setSpacing(5)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # =====================================================================
        # Section 1: Source Plate (Expanded by default)
        # =====================================================================
        self.sec_source_header = CollapsibleSectionHeader("Source Plate File sequence name", content, expanded=True)
        self._content_layout.addWidget(self.sec_source_header)

        self.sec_source_body = QWidget(content)
        self.sec_source_body.setVisible(True)
        lay_sbody = QVBoxLayout(self.sec_source_body)
        lay_sbody.setContentsMargins(0, 0, 0, 0)
        lay_sbody.setSpacing(5)

        self.drop_source = DropZoneWidget("Drop the Source/Input plate ⬇", self.sec_source_body, height=75)
        self.drop_source.file_dropped.connect(self._on_source_plate_dropped)
        lay_sbody.addWidget(self.drop_source)

        row_sbtns = QHBoxLayout()
        row_sbtns.setSpacing(6)
        self.btn_prefetch_source = QPushButton("Prefetch Source", self.sec_source_body)
        self.btn_prefetch_source.setFixedHeight(24)
        self.btn_prefetch_source.setStyleSheet(self._btn_style())
        self.btn_prefetch_source.clicked.connect(self.source_prefetch_requested.emit)
        row_sbtns.addWidget(self.btn_prefetch_source)

        self.btn_unload_source = QPushButton("Unload source", self.sec_source_body)
        self.btn_unload_source.setFixedHeight(24)
        self.btn_unload_source.setStyleSheet(self._btn_style())
        self.btn_unload_source.clicked.connect(self._on_unload_source)
        row_sbtns.addWidget(self.btn_unload_source)
        lay_sbody.addLayout(row_sbtns)

        self.progress_source = PrefetchStatusRow(self.sec_source_body)
        lay_sbody.addWidget(self.progress_source)
        self._content_layout.addWidget(self.sec_source_body)

        self.sec_source_header.toggled.connect(self.sec_source_body.setVisible)

        # Divider
        self._content_layout.addWidget(DotsSeparator(content))

        # =====================================================================
        # Section 2: Real-time QC Diagnostic Grading Sliders (Color correction)
        # =====================================================================
        self.sec_cc_header = CollapsibleSectionHeader("Color correction", content, expanded=False)
        self._content_layout.addWidget(self.sec_cc_header)

        self.sec_cc_body = QWidget(content)
        self.sec_cc_body.setVisible(False)
        lay_cc_body = QVBoxLayout(self.sec_cc_body)
        lay_cc_body.setContentsMargins(0, 0, 0, 0)
        lay_cc_body.setSpacing(5)

        self.slider_gamma = LabeledSliderRow("Gamma", 0.1, 4.0, 1.0, self.sec_cc_body, scale=100)
        self.slider_gamma.value_changed.connect(lambda v: setattr(self.state, "qc_gamma", v))
        lay_cc_body.addWidget(self.slider_gamma)

        self.slider_gain = LabeledSliderRow("Gain", 0.0, 8.0, 1.0, self.sec_cc_body, scale=100)
        self.slider_gain.value_changed.connect(lambda v: setattr(self.state, "qc_gain", v))
        lay_cc_body.addWidget(self.slider_gain)

        self.slider_softclip = LabeledSliderRow("Softclip Knee", 0.0, 1.0, 1.0, self.sec_cc_body, scale=100)
        self.slider_softclip.value_changed.connect(lambda v: setattr(self.state, "qc_softclip", v))
        lay_cc_body.addWidget(self.slider_softclip)

        self.slider_sat = LabeledSliderRow("Saturation Multiplier", 0.0, 4.0, 1.0, self.sec_cc_body, scale=100)
        self.slider_sat.value_changed.connect(lambda v: setattr(self.state, "qc_sat_multiplier", v))
        lay_cc_body.addWidget(self.slider_sat)

        self.slider_hue = LabeledSliderRow("Hue Rotation", -180.0, 180.0, 0.0, self.sec_cc_body, scale=1, decimals=1)
        self.slider_hue.value_changed.connect(lambda v: setattr(self.state, "qc_hue_rotation", v))
        lay_cc_body.addWidget(self.slider_hue)

        self._content_layout.addWidget(self.sec_cc_body)
        self.sec_cc_header.toggled.connect(self.sec_cc_body.setVisible)

        # Divider
        self._content_layout.addWidget(DotsSeparator(content))

        # =====================================================================
        # Section 3: HSL Colorspace / Grain Inspection / Highpass
        # =====================================================================
        self.sec_hsl_header = CollapsibleSectionHeader("HSL Colorspace / Grain Inspection / Highpass", content, expanded=False)
        self._content_layout.addWidget(self.sec_hsl_header)

        self.sec_hsl_body = QWidget(content)
        self.sec_hsl_body.setVisible(False)
        lay_hbody = QVBoxLayout(self.sec_hsl_body)
        lay_hbody.setContentsMargins(0, 0, 0, 0)
        lay_hbody.setSpacing(5)

        # Hue, Saturation, Luminance Solo Row
        row_hsl = QHBoxLayout()
        row_hsl.setSpacing(4)
        self.btn_hue = QPushButton("Hue", self.sec_hsl_body)
        self.btn_hue.setCheckable(True)
        self.btn_hue.setFixedHeight(24)
        self.btn_hue.setStyleSheet(self._toggle_btn_style())
        self.btn_hue.clicked.connect(lambda: self._toggle_hsl_mode(HslMode.HUE))
        row_hsl.addWidget(self.btn_hue)

        self.btn_sat = QPushButton("Saturation", self.sec_hsl_body)
        self.btn_sat.setCheckable(True)
        self.btn_sat.setFixedHeight(24)
        self.btn_sat.setStyleSheet(self._toggle_btn_style())
        self.btn_sat.clicked.connect(lambda: self._toggle_hsl_mode(HslMode.SATURATION))
        row_hsl.addWidget(self.btn_sat)

        self.btn_lum = QPushButton("Luminance", self.sec_hsl_body)
        self.btn_lum.setCheckable(True)
        self.btn_lum.setFixedHeight(24)
        self.btn_lum.setStyleSheet(self._toggle_btn_style())
        self.btn_lum.clicked.connect(lambda: self._toggle_hsl_mode(HslMode.LUMINANCE))
        row_hsl.addWidget(self.btn_lum)
        lay_hbody.addLayout(row_hsl)

        # Dedicated HSL Mode button below HSL row
        self.btn_hsl_mode = QPushButton("HSL mode", self.sec_hsl_body)
        self.btn_hsl_mode.setCheckable(True)
        self.btn_hsl_mode.setFixedHeight(24)
        self.btn_hsl_mode.setStyleSheet(self._toggle_btn_style())
        self.btn_hsl_mode.clicked.connect(lambda: self._toggle_hsl_mode(HslMode.FULL_HSL))
        lay_hbody.addWidget(self.btn_hsl_mode)

        # Sliders for Hipass Value (0-10), Grain Boost (0-100), Edge Threshold (0-1)
        self.slider_hipass = LabeledSliderRow("Hipass value", 0.0, 10.0, 3.0, self.sec_hsl_body, scale=10)
        self.slider_hipass.value_changed.connect(lambda v: setattr(self.state, "hipass_value", v))
        self.slider_blur = self.slider_hipass  # Backward compatibility alias
        lay_hbody.addWidget(self.slider_hipass)

        self.slider_grain_boost = LabeledSliderRow("Grain Boost", 0.0, 100.0, 50.0, self.sec_hsl_body, scale=1)
        self.slider_grain_boost.value_changed.connect(lambda v: setattr(self.state, "grain_boost_raw", v))
        lay_hbody.addWidget(self.slider_grain_boost)

        # 2x3 Action Grid Buttons
        grid_modes = QGridLayout()
        grid_modes.setSpacing(4)

        self.btn_grain = QPushButton("Grain check", self.sec_hsl_body)
        self.btn_grain.setCheckable(True)
        self.btn_grain.setFixedHeight(26)
        self.btn_grain.setStyleSheet(self._toggle_btn_style())
        self.btn_grain.clicked.connect(lambda: self._toggle_qc_mode(QcMode.GRAIN_CHECK))
        grid_modes.addWidget(self.btn_grain, 0, 0)

        self.btn_black = QPushButton("Black Levels", self.sec_hsl_body)
        self.btn_black.setCheckable(True)
        self.btn_black.setFixedHeight(26)
        self.btn_black.setStyleSheet(self._toggle_btn_style())
        self.btn_black.clicked.connect(lambda: self._toggle_qc_mode(QcMode.BLACK_LEVELS))
        grid_modes.addWidget(self.btn_black, 0, 1)

        self.btn_neg = QPushButton("Negative pixels", self.sec_hsl_body)
        self.btn_neg.setCheckable(True)
        self.btn_neg.setFixedHeight(26)
        self.btn_neg.setStyleSheet(self._toggle_btn_style())
        self.btn_neg.clicked.connect(lambda: self._toggle_qc_mode(QcMode.NEGATIVE_PIXELS))
        grid_modes.addWidget(self.btn_neg, 1, 0)

        self.btn_highpass = QPushButton("High pass", self.sec_hsl_body)
        self.btn_highpass.setCheckable(True)
        self.btn_highpass.setFixedHeight(26)
        self.btn_highpass.setStyleSheet(self._toggle_btn_style())
        self.btn_highpass.clicked.connect(lambda: self._toggle_qc_mode(QcMode.HIGHPASS_COMP))
        grid_modes.addWidget(self.btn_highpass, 1, 1)

        self.btn_diff = QPushButton("Difference", self.sec_hsl_body)
        self.btn_diff.setCheckable(True)
        self.btn_diff.setFixedHeight(26)
        self.btn_diff.setStyleSheet(self._toggle_btn_style())
        self.btn_diff.clicked.connect(lambda: self._toggle_qc_mode(QcMode.COMP_DIFF_PLATE))
        grid_modes.addWidget(self.btn_diff, 2, 0)

        self.btn_nan = QPushButton("NAN / inf", self.sec_hsl_body)
        self.btn_nan.setCheckable(True)
        self.btn_nan.setFixedHeight(26)
        self.btn_nan.setStyleSheet(self._toggle_btn_style())
        self.btn_nan.clicked.connect(lambda: self._toggle_qc_mode(QcMode.NAN_INF_PIXELS))
        grid_modes.addWidget(self.btn_nan, 2, 1)
        lay_hbody.addLayout(grid_modes)

        # Full-width Compare plates button
        self.btn_compare_plate = QPushButton("Compare plates", self.sec_hsl_body)
        self.btn_compare_plate.setCheckable(True)
        self.btn_compare_plate.setFixedHeight(30)
        self.btn_compare_plate.setStyleSheet(self._toggle_btn_style())
        self.btn_compare_plate.clicked.connect(self._toggle_compare_against_plate)
        self.btn_compare_plates = self.btn_compare_plate  # Alias
        lay_hbody.addWidget(self.btn_compare_plate)

        self._content_layout.addWidget(self.sec_hsl_body)
        self.sec_hsl_header.toggled.connect(self.sec_hsl_body.setVisible)

        # Divider
        self._content_layout.addWidget(DotsSeparator(content))

        # =====================================================================
        # Section 4: Matte Loader (Expanded by default)
        # =====================================================================
        self.sec_matte_loader_header = CollapsibleSectionHeader("Matte Loader", content, expanded=True)
        self._content_layout.addWidget(self.sec_matte_loader_header)

        self.sec_matte_loader_body = QWidget(content)
        self.sec_matte_loader_body.setVisible(True)
        lay_mlbody = QVBoxLayout(self.sec_matte_loader_body)
        lay_mlbody.setContentsMargins(0, 0, 0, 0)
        lay_mlbody.setSpacing(5)

        self.drop_matte = DropZoneWidget("Drop your RGBA matte ⬇", self.sec_matte_loader_body, height=55)
        self.drop_matte.file_dropped.connect(self._on_matte_dropped)
        lay_mlbody.addWidget(self.drop_matte)

        row_mbtns = QHBoxLayout()
        row_mbtns.setSpacing(6)
        self.btn_prefetch_matte = QPushButton("Prefetch matte", self.sec_matte_loader_body)
        self.btn_prefetch_matte.setFixedHeight(24)
        self.btn_prefetch_matte.setStyleSheet(self._btn_style())
        self.btn_prefetch_matte.clicked.connect(self.matte_prefetch_requested.emit)
        row_mbtns.addWidget(self.btn_prefetch_matte)

        self.btn_unload_matte = QPushButton("Unload Matte", self.sec_matte_loader_body)
        self.btn_unload_matte.setFixedHeight(24)
        self.btn_unload_matte.setStyleSheet(self._btn_style())
        self.btn_unload_matte.clicked.connect(self._on_unload_matte)
        row_mbtns.addWidget(self.btn_unload_matte)
        lay_mlbody.addLayout(row_mbtns)

        self.progress_matte = PrefetchStatusRow(self.sec_matte_loader_body)
        lay_mlbody.addWidget(self.progress_matte)

        self._content_layout.addWidget(self.sec_matte_loader_body)
        self.sec_matte_loader_header.toggled.connect(self.sec_matte_loader_body.setVisible)

        # Divider
        self._content_layout.addWidget(DotsSeparator(content))

        # =====================================================================
        # Section 5: Matte Check Controls (Collapsed by default)
        # =====================================================================
        self.sec_matte_header = CollapsibleSectionHeader("Matte Check Controls", content, expanded=False)
        self._content_layout.addWidget(self.sec_matte_header)

        self.sec_matte_body = QWidget(content)
        self.sec_matte_body.setVisible(False)
        lay_mbody = QVBoxLayout(self.sec_matte_body)
        lay_mbody.setContentsMargins(0, 0, 0, 0)
        lay_mbody.setSpacing(5)

        # Full-width Overlay Matte button (Shortcut 'O')
        self.btn_overlay_matte = QPushButton("Overlay Matte  (O)", self.sec_matte_body)
        self.btn_overlay_matte.setCheckable(True)
        self.btn_overlay_matte.setFixedHeight(28)
        self.btn_overlay_matte.setStyleSheet(self._toggle_btn_style())
        self.btn_overlay_matte.clicked.connect(self._toggle_overlay_matte)
        lay_mbody.addWidget(self.btn_overlay_matte)

        row_premult = QHBoxLayout()
        row_premult.setSpacing(6)
        row_premult.setContentsMargins(2, 0, 0, 0)
        self.chk_matte_premult = QCheckBox("Matte is Premultiplied", self.sec_matte_body)
        self.chk_matte_premult.setChecked(getattr(self.state, "matte_is_premult", True))
        self.chk_matte_premult.setToolTip("Enable standard VFX premultiplied Over (A + B*(1-a)). Uncheck if loaded matte is straight / unpremultiplied RGB.")
        self.chk_matte_premult.setStyleSheet(self._checkbox_style())
        self.chk_matte_premult.toggled.connect(self._on_matte_premult_toggled)
        row_premult.addWidget(self.chk_matte_premult)
        row_premult.addStretch()
        lay_mbody.addLayout(row_premult)

        # Setup shortcut 'O' for Overlay Matte
        self.shortcut_overlay = QShortcut(QKeySequence(Qt.Key.Key_O), self)
        self.shortcut_overlay.activated.connect(self._toggle_overlay_matte)

        # ---------------------------------------------------------------------
        # Channel Expressions (Foundry Nuke-style Expression node)
        # ---------------------------------------------------------------------
        row_expr_header = QHBoxLayout()
        row_expr_header.setContentsMargins(0, 4, 0, 2)
        lbl_expr = QLabel("Channel Expressions (Nuke Node):", self.sec_matte_body)
        lbl_expr.setStyleSheet("color: #b0b0b0; font-size: 11px; font-weight: bold;")
        row_expr_header.addWidget(lbl_expr)
        row_expr_header.addStretch()

        self.btn_expr_presets = QToolButton(self.sec_matte_body)
        self.btn_expr_presets.setText("Presets ▾")
        self.btn_expr_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_expr_presets.setStyleSheet("""
            QToolButton {
                background-color: #242424;
                color: #e5a823;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #333333;
                border-color: #e5a823;
            }
            QToolButton::menu-indicator { image: none; }
        """)
        self._setup_expr_presets_menu()
        row_expr_header.addWidget(self.btn_expr_presets)
        lay_mbody.addLayout(row_expr_header)

        # Single-shot timer to debounce live typing recompilations (300ms)
        self._expr_debounce_timer = QTimer(self)
        self._expr_debounce_timer.setSingleShot(True)
        self._expr_debounce_timer.timeout.connect(self._commit_channel_expressions)

        grid_expr = QGridLayout()
        grid_expr.setSpacing(4)
        grid_expr.setContentsMargins(0, 0, 0, 0)

        # Hidden dummy checkboxes for backward compatibility
        self.chk_red = QCheckBox(self)
        self.chk_red.setChecked(self.state.enable_red)
        self.chk_red.toggled.connect(self._on_chk_red_toggled)
        self.chk_red.hide()
        self.chk_green = QCheckBox(self)
        self.chk_green.setChecked(self.state.enable_green)
        self.chk_green.toggled.connect(self._on_chk_green_toggled)
        self.chk_green.hide()
        self.chk_blue = QCheckBox(self)
        self.chk_blue.setChecked(self.state.enable_blue)
        self.chk_blue.toggled.connect(self._on_chk_blue_toggled)
        self.chk_blue.hide()
        self.chk_alpha = QCheckBox(self)
        self.chk_alpha.setChecked(self.state.enable_alpha)
        self.chk_alpha.toggled.connect(self._on_chk_alpha_toggled)
        self.chk_alpha.hide()

        # Red Channel Row: r = [ LineEdit ] [↺]
        lbl_r = QLabel("r =", self.sec_matte_body)
        lbl_r.setStyleSheet("color: #e05555; font-size: 11px; font-family: 'Consolas', monospace; font-weight: bold;")
        lbl_r.setFixedWidth(24)
        grid_expr.addWidget(lbl_r, 0, 0)

        self.txt_expr_r = QLineEdit(self.sec_matte_body)
        self.txt_expr_r.setPlaceholderText("r")
        self.txt_expr_r.setClearButtonEnabled(True)
        self.txt_expr_r.setStyleSheet(self._input_style())
        self.txt_expr_r.textChanged.connect(self._on_expr_text_changed)
        self.txt_expr_r.returnPressed.connect(self._commit_channel_expressions)
        self.txt_expr_r.editingFinished.connect(self._commit_channel_expressions)
        grid_expr.addWidget(self.txt_expr_r, 0, 1)

        self.btn_rst_r = QToolButton(self.sec_matte_body)
        self.btn_rst_r.setText("↺")
        self.btn_rst_r.setToolTip("Reset Red expression to default ('r')")
        self.btn_rst_r.setFixedSize(18, 18)
        self.btn_rst_r.setStyleSheet(self._mini_tool_btn_style())
        self.btn_rst_r.clicked.connect(lambda: self._reset_single_expr(self.txt_expr_r, "expr_red"))
        grid_expr.addWidget(self.btn_rst_r, 0, 2)

        # Green Channel Row: g = [ LineEdit ] [↺]
        lbl_g = QLabel("g =", self.sec_matte_body)
        lbl_g.setStyleSheet("color: #55c055; font-size: 11px; font-family: 'Consolas', monospace; font-weight: bold;")
        lbl_g.setFixedWidth(24)
        grid_expr.addWidget(lbl_g, 1, 0)

        self.txt_expr_g = QLineEdit(self.sec_matte_body)
        self.txt_expr_g.setPlaceholderText("g")
        self.txt_expr_g.setClearButtonEnabled(True)
        self.txt_expr_g.setStyleSheet(self._input_style())
        self.txt_expr_g.textChanged.connect(self._on_expr_text_changed)
        self.txt_expr_g.returnPressed.connect(self._commit_channel_expressions)
        self.txt_expr_g.editingFinished.connect(self._commit_channel_expressions)
        grid_expr.addWidget(self.txt_expr_g, 1, 1)

        self.btn_rst_g = QToolButton(self.sec_matte_body)
        self.btn_rst_g.setText("↺")
        self.btn_rst_g.setToolTip("Reset Green expression to default ('g')")
        self.btn_rst_g.setFixedSize(18, 18)
        self.btn_rst_g.setStyleSheet(self._mini_tool_btn_style())
        self.btn_rst_g.clicked.connect(lambda: self._reset_single_expr(self.txt_expr_g, "expr_green"))
        grid_expr.addWidget(self.btn_rst_g, 1, 2)

        # Blue Channel Row: b = [ LineEdit ] [↺]
        lbl_b = QLabel("b =", self.sec_matte_body)
        lbl_b.setStyleSheet("color: #5588e0; font-size: 11px; font-family: 'Consolas', monospace; font-weight: bold;")
        lbl_b.setFixedWidth(24)
        grid_expr.addWidget(lbl_b, 2, 0)

        self.txt_expr_b = QLineEdit(self.sec_matte_body)
        self.txt_expr_b.setPlaceholderText("b")
        self.txt_expr_b.setClearButtonEnabled(True)
        self.txt_expr_b.setStyleSheet(self._input_style())
        self.txt_expr_b.textChanged.connect(self._on_expr_text_changed)
        self.txt_expr_b.returnPressed.connect(self._commit_channel_expressions)
        self.txt_expr_b.editingFinished.connect(self._commit_channel_expressions)
        grid_expr.addWidget(self.txt_expr_b, 2, 1)

        self.btn_rst_b = QToolButton(self.sec_matte_body)
        self.btn_rst_b.setText("↺")
        self.btn_rst_b.setToolTip("Reset Blue expression to default ('b')")
        self.btn_rst_b.setFixedSize(18, 18)
        self.btn_rst_b.setStyleSheet(self._mini_tool_btn_style())
        self.btn_rst_b.clicked.connect(lambda: self._reset_single_expr(self.txt_expr_b, "expr_blue"))
        grid_expr.addWidget(self.btn_rst_b, 2, 2)

        # Alpha Channel Row: a = [ LineEdit ] [↺]
        lbl_a = QLabel("a =", self.sec_matte_body)
        lbl_a.setStyleSheet("color: #e5a823; font-size: 11px; font-family: 'Consolas', monospace; font-weight: bold;")
        lbl_a.setFixedWidth(24)
        grid_expr.addWidget(lbl_a, 3, 0)

        self.txt_expr_a = QLineEdit(self.sec_matte_body)
        self.txt_expr_a.setPlaceholderText("a")
        self.txt_expr_a.setClearButtonEnabled(True)
        self.txt_expr_a.setStyleSheet(self._input_style())
        self.txt_expr_a.textChanged.connect(self._on_expr_text_changed)
        self.txt_expr_a.returnPressed.connect(self._commit_channel_expressions)
        self.txt_expr_a.editingFinished.connect(self._commit_channel_expressions)
        grid_expr.addWidget(self.txt_expr_a, 3, 1)

        self.btn_rst_a = QToolButton(self.sec_matte_body)
        self.btn_rst_a.setText("↺")
        self.btn_rst_a.setToolTip("Reset Alpha expression to default ('a')")
        self.btn_rst_a.setFixedSize(18, 18)
        self.btn_rst_a.setStyleSheet(self._mini_tool_btn_style())
        self.btn_rst_a.clicked.connect(lambda: self._reset_single_expr(self.txt_expr_a, "expr_alpha"))
        grid_expr.addWidget(self.btn_rst_a, 3, 2)

        grid_expr.setColumnStretch(1, 1)
        lay_mbody.addLayout(grid_expr)

        # Mix overlay slider & spinbox (Moved below Channel Expressions)
        row_mix = QHBoxLayout()
        row_mix.setSpacing(6)
        lbl_mix = QLabel("Mix overlay:", self.sec_matte_body)
        lbl_mix.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        row_mix.addWidget(lbl_mix)

        self.slider_mix = NonWheelSlider(Qt.Orientation.Horizontal, self.sec_matte_body, on_reset=self._reset_mix_overlay)
        self.slider_mix.setRange(0, 100)
        self.slider_mix.setValue(100)
        self.slider_mix.setStyleSheet(self._slider_style())
        self.slider_mix.valueChanged.connect(self._on_mix_slider_changed)
        row_mix.addWidget(self.slider_mix, 1)

        self.spin_mix = NonWheelDoubleSpinBox(self.sec_matte_body)
        self.spin_mix.setRange(0.0, 1.0)
        self.spin_mix.setSingleStep(0.05)
        self.spin_mix.setValue(1.0)
        self.spin_mix.setFixedWidth(54)
        self.spin_mix.setStyleSheet(self._spin_style())
        self.spin_mix.valueChanged.connect(self._on_mix_spin_changed)
        row_mix.addWidget(self.spin_mix)

        self.btn_rst_mix = QToolButton(self.sec_matte_body)
        self.btn_rst_mix.setText("↺")
        self.btn_rst_mix.setToolTip("Reset Mix overlay to default (1.0) [or Ctrl+Click slider]")
        self.btn_rst_mix.setFixedSize(18, 18)
        self.btn_rst_mix.setStyleSheet(self._mini_tool_btn_style())
        self.btn_rst_mix.clicked.connect(self._reset_mix_overlay)
        row_mix.addWidget(self.btn_rst_mix)
        lay_mbody.addLayout(row_mix)

        # Alpha Overlay toggle button
        row_overlay = QHBoxLayout()
        row_overlay.setSpacing(6)
        lbl_ov = QLabel("Alpha Overlay:", self.sec_matte_body)
        lbl_ov.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        row_overlay.addWidget(lbl_ov)

        self.btn_alpha_overlay = QPushButton("Enable Alpha Overlay", self.sec_matte_body)
        self.btn_alpha_overlay.setCheckable(True)
        self.btn_alpha_overlay.setFixedHeight(24)
        self.btn_alpha_overlay.setStyleSheet(self._toggle_btn_style())
        self.btn_alpha_overlay.toggled.connect(self._on_alpha_overlay_toggled)
        row_overlay.addWidget(self.btn_alpha_overlay, 1)
        lay_mbody.addLayout(row_overlay)

        # Clamp Alpha & Overlay color
        row_clamp_color = QHBoxLayout()
        row_clamp_color.setSpacing(6)

        lbl_clamp = QLabel("Clamp Alpha:", self.sec_matte_body)
        lbl_clamp.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        row_clamp_color.addWidget(lbl_clamp)

        self.btn_clamp = QPushButton("Off", self.sec_matte_body)
        self.btn_clamp.setCheckable(True)
        self.btn_clamp.setChecked(False)
        self.btn_clamp.setFixedWidth(38)
        self.btn_clamp.setFixedHeight(22)
        self.btn_clamp.setStyleSheet(self._toggle_btn_style())
        self.btn_clamp.toggled.connect(self._on_clamp_toggled)
        row_clamp_color.addWidget(self.btn_clamp)

        row_clamp_color.addSpacing(6)
        lbl_ovcol = QLabel("Overlay color:", self.sec_matte_body)
        lbl_ovcol.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        row_clamp_color.addWidget(lbl_ovcol)

        # Primary Colors: Pure Red (#ff2222), Pure Green (#22cc22), Pure Blue (#2255ff) + Custom Color Picker
        self.btn_swatch_red = QPushButton(self.sec_matte_body)
        self.btn_swatch_red.setFixedSize(20, 20)
        self.btn_swatch_red.setToolTip("Primary Red (#ff2222)")
        self.btn_swatch_red.setStyleSheet("background-color: #ff2222; border: 1px solid #444444; border-radius: 2px;")
        self.btn_swatch_red.clicked.connect(lambda: self._set_overlay_color(QColor(255, 34, 34)))
        row_clamp_color.addWidget(self.btn_swatch_red)

        self.btn_swatch_green = QPushButton(self.sec_matte_body)
        self.btn_swatch_green.setFixedSize(20, 20)
        self.btn_swatch_green.setToolTip("Primary Green (#22cc22)")
        self.btn_swatch_green.setStyleSheet("background-color: #22cc22; border: 1px solid #444444; border-radius: 2px;")
        self.btn_swatch_green.clicked.connect(lambda: self._set_overlay_color(QColor(34, 204, 34)))
        row_clamp_color.addWidget(self.btn_swatch_green)

        self.btn_swatch_blue = QPushButton(self.sec_matte_body)
        self.btn_swatch_blue.setFixedSize(20, 20)
        self.btn_swatch_blue.setToolTip("Primary Blue (#2255ff)")
        self.btn_swatch_blue.setStyleSheet("background-color: #2255ff; border: 1px solid #444444; border-radius: 2px;")
        self.btn_swatch_blue.clicked.connect(lambda: self._set_overlay_color(QColor(34, 85, 255)))
        row_clamp_color.addWidget(self.btn_swatch_blue)

        self.btn_swatch_custom = QPushButton(self.sec_matte_body)
        self.btn_swatch_custom.setFixedSize(20, 20)
        self.btn_swatch_custom.setToolTip("Custom Color (Click to choose...)")
        cur_col = getattr(self.state, "overlay_color", QColor(255, 34, 34))
        self.btn_swatch_custom.setStyleSheet(f"background-color: {cur_col.name()}; border: 1px solid #e5a823; border-radius: 2px;")
        self.btn_swatch_custom.clicked.connect(self._open_color_picker)
        self.btn_swatch_magenta = self.btn_swatch_custom  # Alias for backward compatibility
        row_clamp_color.addWidget(self.btn_swatch_custom)
        row_clamp_color.addStretch()
        lay_mbody.addLayout(row_clamp_color)

        # Greycheck and Checkerboard toggle buttons with preview icons
        row_diag = QHBoxLayout()
        row_diag.setSpacing(6)
        self.btn_greycheck = QPushButton("Greycheck", self.sec_matte_body)
        self.btn_greycheck.setCheckable(True)
        self.btn_greycheck.setFixedHeight(24)
        self.btn_greycheck.setIcon(_create_grey_icon(14))
        self.btn_greycheck.setIconSize(QSize(14, 14))
        self.btn_greycheck.setStyleSheet(self._toggle_btn_style())
        self.btn_greycheck.clicked.connect(self._toggle_greycheck)
        row_diag.addWidget(self.btn_greycheck)

        self.btn_checkerboard = QPushButton("Checkerboard", self.sec_matte_body)
        self.btn_checkerboard.setCheckable(True)
        self.btn_checkerboard.setFixedHeight(24)
        self.btn_checkerboard.setIcon(_create_checker_icon(14))
        self.btn_checkerboard.setIconSize(QSize(14, 14))
        self.btn_checkerboard.setStyleSheet(self._toggle_btn_style())
        self.btn_checkerboard.clicked.connect(self._toggle_checkerboard)
        row_diag.addWidget(self.btn_checkerboard)
        lay_mbody.addLayout(row_diag)

        # Sliders below greycheck & Checkerboard
        self.slider_grey_val = LabeledSliderRow("Grey value", 0.0, 1.0, 0.5, self.sec_matte_body, scale=100)
        self.slider_grey_val.value_changed.connect(lambda v: setattr(self.state, "grey_value", v))
        lay_mbody.addWidget(self.slider_grey_val)

        self.slider_grid_scale = LabeledSliderRow("Grid scale", 4.0, 128.0, 32.0, self.sec_matte_body, scale=1)
        self.slider_grid_scale.value_changed.connect(lambda v: setattr(self.state, "grid_scale", v))
        lay_mbody.addWidget(self.slider_grid_scale)

        self.slider_checker_contrast = LabeledSliderRow("Checker contrast", 0.0, 1.0, 0.2, self.sec_matte_body, scale=100)
        self.slider_checker_contrast.value_changed.connect(lambda v: setattr(self.state, "checker_contrast", v))
        lay_mbody.addWidget(self.slider_checker_contrast)

        self._content_layout.addWidget(self.sec_matte_body)
        self.sec_matte_header.toggled.connect(self.sec_matte_body.setVisible)

        # Stretch pushes all collapsible sections to the top, eliminating vertical gaps
        self._content_layout.addStretch(1)

        # Scroll widget packaging
        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)

        # =====================================================================
        # Section 5: Subdued VFX Slate-Red Reset Button
        # =====================================================================
        self.btn_reset = QPushButton("Reset to Default", self)
        self.btn_reset.setFixedHeight(30)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #3a1616;
                color: #e0e0e0;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #552222;
                border-radius: 2px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background-color: #4a1c1c;
                border: 1px solid #e5a823;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #240c0c;
                border-color: #e5a823;
            }
        """)
        self.btn_reset.clicked.connect(self._on_reset_all)
        root_layout.addWidget(self.btn_reset)

    # -------------------------------------------------------------------------
    # State Synchronization & Slots
    # -------------------------------------------------------------------------
    def _bind_state(self) -> None:
        self.state.changed.connect(self._sync_from_state)
        self._sync_from_state()

    def _sync_from_state(self) -> None:
        # Block signals during sync to avoid echo
        self.slider_gamma.set_value(self.state.qc_gamma)
        self.slider_gain.set_value(self.state.qc_gain)
        self.slider_softclip.set_value(self.state.qc_softclip)
        self.slider_sat.set_value(self.state.qc_sat_multiplier)
        self.slider_hue.set_value(self.state.qc_hue_rotation)

        self.slider_hipass.set_value(self.state.hipass_value)
        self.slider_grain_boost.set_value(self.state.grain_boost_raw)

        # HSL Solo mode buttons
        hm = self.state.hsl_mode
        self.btn_hue.setChecked(hm == HslMode.HUE)
        self.btn_sat.setChecked(hm == HslMode.SATURATION)
        self.btn_lum.setChecked(hm == HslMode.LUMINANCE)
        self.btn_hsl_mode.setChecked(hm in (HslMode.FULL_HSL, 1))

        # QC Mode buttons
        qm = self.state.qc_mode
        self.btn_grain.setChecked(qm == QcMode.GRAIN_CHECK)
        self.btn_black.setChecked(qm == QcMode.BLACK_LEVELS)
        self.btn_neg.setChecked(qm == QcMode.NEGATIVE_PIXELS)
        self.btn_highpass.setChecked(qm in (QcMode.HIGHPASS_COMP, QcMode.HIGHPASS_PLATE))
        self.btn_diff.setChecked(qm == QcMode.COMP_DIFF_PLATE)
        self.btn_nan.setChecked(qm == QcMode.NAN_INF_PIXELS)

        # Compare button
        self.btn_compare_plate.setChecked(self.state.compare_plates or self.state.compare_against_plate)

        # Matte Check controls
        self.btn_overlay_matte.setChecked(self.state.overlay_matte_enabled)
        self.chk_matte_premult.setChecked(getattr(self.state, "matte_is_premult", True))
        self.btn_alpha_overlay.setChecked(self.state.alpha_overlay_enabled)
        self.btn_clamp.setChecked(self.state.clamp_alpha)
        self.btn_clamp.setText("On" if self.state.clamp_alpha else "Off")

        self.btn_greycheck.setChecked(self.state.greycheck_enabled)
        self.btn_checkerboard.setChecked(self.state.checkerboard_enabled)
        self.slider_grey_val.set_value(self.state.grey_value)
        self.slider_grid_scale.set_value(self.state.grid_scale)
        self.slider_checker_contrast.set_value(self.state.checker_contrast)

        # Synchronize channel expression fields
        for txt, ch, attr in [
            (self.txt_expr_r, "r", "expr_red"),
            (self.txt_expr_g, "g", "expr_green"),
            (self.txt_expr_b, "b", "expr_blue"),
            (self.txt_expr_a, "a", "expr_alpha"),
        ]:
            val = getattr(self.state, attr, "")
            if txt.text() != val:
                txt.blockSignals(True)
                txt.setText(val)
                txt.blockSignals(False)
            glsl, err = validate_and_compile_expression(val, ch)
            if err:
                txt.setStyleSheet(self._expr_error_style())
                txt.setToolTip(f"Syntax Error: {err}")
            else:
                txt.setStyleSheet(self._input_style())
                txt.setToolTip(f"Compiled GLSL: {glsl}")

        # Synchronize channel checkboxes & text enable state
        self.chk_red.blockSignals(True)
        self.chk_red.setChecked(self.state.enable_red)
        self.txt_expr_r.setEnabled(self.state.enable_red)
        self.chk_red.blockSignals(False)

        self.chk_green.blockSignals(True)
        self.chk_green.setChecked(self.state.enable_green)
        self.txt_expr_g.setEnabled(self.state.enable_green)
        self.chk_green.blockSignals(False)

        self.chk_blue.blockSignals(True)
        self.chk_blue.setChecked(self.state.enable_blue)
        self.txt_expr_b.setEnabled(self.state.enable_blue)
        self.chk_blue.blockSignals(False)

        self.chk_alpha.blockSignals(True)
        self.chk_alpha.setChecked(self.state.enable_alpha)
        self.txt_expr_a.setEnabled(self.state.enable_alpha)
        self.chk_alpha.blockSignals(False)

        mv = self.state.mix_overlay
        self.slider_mix.blockSignals(True)
        self.spin_mix.blockSignals(True)
        self.slider_mix.setValue(int(round(mv * 100)))
        self.spin_mix.setValue(mv)
        self.slider_mix.blockSignals(False)
        self.spin_mix.blockSignals(False)

        col = self.state.overlay_color
        self.btn_swatch_magenta.setStyleSheet(
            f"background-color: {col.name()}; border: 1px solid #e5a823; border-radius: 2px;"
        )

        # Progress
        self.progress_source.set_progress(self.state.source_prefetch_progress)
        self.progress_matte.set_progress(self.state.matte_prefetch_progress)

    def _toggle_hsl_mode(self, mode: HslMode) -> None:
        if self.state.hsl_mode == mode:
            self.state.hsl_mode = HslMode.OFF
        else:
            self.state.hsl_mode = mode

    def _toggle_qc_mode(self, mode: QcMode) -> None:
        if self.state.qc_mode == mode:
            self.state.qc_mode = QcMode.OFF
        else:
            self.state.qc_mode = mode

    def _toggle_compare_against_plate(self) -> None:
        new_val = not (self.state.compare_plates or self.state.compare_against_plate)
        self.state.compare_plates = new_val
        self.state.compare_against_plate = new_val

    def _toggle_overlay_matte(self) -> None:
        self.state.overlay_matte_enabled = not self.state.overlay_matte_enabled
        self.btn_overlay_matte.setChecked(self.state.overlay_matte_enabled)

    def _on_matte_premult_toggled(self, chk: bool) -> None:
        self.state.matte_is_premult = chk

    def _toggle_greycheck(self) -> None:
        new_val = not self.state.greycheck_enabled
        self.state.greycheck_enabled = new_val
        if new_val:
            self.state.checkerboard_enabled = False

    def _toggle_checkerboard(self) -> None:
        new_val = not self.state.checkerboard_enabled
        self.state.checkerboard_enabled = new_val
        if new_val:
            self.state.greycheck_enabled = False

    def _on_alpha_overlay_toggled(self, chk: bool) -> None:
        self.state.alpha_overlay_enabled = chk

    def _on_clamp_toggled(self, chk: bool) -> None:
        self.state.clamp_alpha = chk
        self.btn_clamp.setText("On" if chk else "Off")

    def _set_overlay_color(self, color: QColor) -> None:
        self.state.overlay_color = color
        if hasattr(self, "btn_swatch_custom"):
            self.btn_swatch_custom.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #e5a823; border-radius: 2px;"
            )

    def _open_color_picker(self) -> None:
        col = QColorDialog.getColor(self.state.overlay_color, self, "Select Overlay Color")
        if col.isValid():
            self._set_overlay_color(col)

    def _on_mix_slider_changed(self, ival: int) -> None:
        fval = float(ival) / 100.0
        self.spin_mix.blockSignals(True)
        self.spin_mix.setValue(fval)
        self.spin_mix.blockSignals(False)
        self.state.mix_overlay = fval

    def _on_mix_spin_changed(self, fval: float) -> None:
        self.slider_mix.blockSignals(True)
        self.slider_mix.setValue(int(round(fval * 100)))
        self.slider_mix.blockSignals(False)
        self.state.mix_overlay = fval

    def _reset_mix_overlay(self) -> None:
        self.slider_mix.blockSignals(True)
        self.spin_mix.blockSignals(True)
        self.slider_mix.setValue(100)
        self.spin_mix.setValue(1.0)
        self.slider_mix.blockSignals(False)
        self.spin_mix.blockSignals(False)
        self.state.mix_overlay = 1.0

    def _on_source_plate_dropped(self, path: str) -> None:
        self.state.source_plate_path = path
        self.sec_source_header.set_title(f"Source: {Path(path).name}")
        self.source_plate_dropped.emit(path)

    def _on_unload_source(self) -> None:
        self.state.source_plate_path = None
        self.drop_source.reset_text()
        self.sec_source_header.set_title("Source Plate File sequence name")
        self.progress_source.set_progress(0.0)
        self.source_unload_requested.emit()

    def _on_matte_dropped(self, path: str) -> None:
        self.state.matte_path = path
        if hasattr(self, "sec_matte_loader_header"):
            self.sec_matte_loader_header.set_title(f"Matte: {Path(path).name}")
        self.matte_dropped.emit(path)

    def _on_unload_matte(self) -> None:
        self.state.matte_path = None
        self.drop_matte.reset_text()
        if hasattr(self, "sec_matte_loader_header"):
            self.sec_matte_loader_header.set_title("Matte Loader")
        self.progress_matte.set_progress(0.0)
        self.matte_unload_requested.emit()

    def _on_reset_all(self) -> None:
        self.state.reset_defaults()
        self.reset_requested.emit()

    # -------------------------------------------------------------------------
    # Channel Expression (Foundry Nuke-style) Slots & Actions
    # -------------------------------------------------------------------------
    def _setup_expr_presets_menu(self) -> None:
        menu = QMenu(self.btn_expr_presets)
        menu.setStyleSheet("""
            QMenu {
                background-color: #222222;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item {
                padding: 4px 18px 4px 8px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #353535;
                color: #e5a823;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333333;
                margin: 4px 0;
            }
        """)

        def set_exprs(r=None, g=None, b=None, a=None):
            self._expr_debounce_timer.stop()
            for txt, val in [(self.txt_expr_r, r), (self.txt_expr_g, g), (self.txt_expr_b, b), (self.txt_expr_a, a)]:
                if val is not None:
                    txt.blockSignals(True)
                    txt.setText(val)
                    txt.blockSignals(False)
            self._commit_channel_expressions()

        act_rst = menu.addAction("Reset to Default (r, g, b, a)")
        act_rst.triggered.connect(lambda: set_exprs("", "", "", ""))

        menu.addSeparator()

        act_inv = menu.addAction("Invert Alpha (1 - a)")
        act_inv.triggered.connect(lambda: set_exprs(a="1 - a"))

        act_solid = menu.addAction("Solid Alpha (1.0)")
        act_solid.triggered.connect(lambda: set_exprs(a="1.0"))

        act_luma = menu.addAction("Luma to Alpha (0.2126*r + 0.7152*g + 0.0722*b)")
        act_luma.triggered.connect(lambda: set_exprs(a="0.2126*r + 0.7152*g + 0.0722*b"))

        act_max = menu.addAction("Max RGB to Alpha (max(r, max(g, b)))")
        act_max.triggered.connect(lambda: set_exprs(a="max(r, max(g, b))"))

        act_min = menu.addAction("Min RGB to Alpha (min(r, min(g, b)))")
        act_min.triggered.connect(lambda: set_exprs(a="min(r, min(g, b))"))

        menu.addSeparator()

        act_hramp = menu.addAction("Horizontal Ramp (cx)")
        act_hramp.triggered.connect(lambda: set_exprs(a="cx"))

        act_vramp = menu.addAction("Vertical Ramp (cy)")
        act_vramp.triggered.connect(lambda: set_exprs(a="cy"))

        act_vign = menu.addAction("Radial Vignette")
        act_vign.triggered.connect(lambda: set_exprs(a="clamp(1.0 - distance(vec2(cx, cy), vec2(0.5)) * 2.0, 0.0, 1.0)"))

        act_step = menu.addAction("Threshold Step (step(0.5, a))")
        act_step.triggered.connect(lambda: set_exprs(a="step(0.5, a)"))

        self.btn_expr_presets.setMenu(menu)

    def _on_expr_text_changed(self) -> None:
        """Debounce live typing recompilations (350ms) so keyboard input is 100% fluid and responsive."""
        self._expr_debounce_timer.start(350)

    def _commit_channel_expressions(self) -> None:
        """Validate all channel expressions and commit valid ones to reactive state with batched updates."""
        self._expr_debounce_timer.stop()

        ch_map = [
            (self.txt_expr_r, "r", "expr_red"),
            (self.txt_expr_g, "g", "expr_green"),
            (self.txt_expr_b, "b", "expr_blue"),
            (self.txt_expr_a, "a", "expr_alpha"),
        ]

        any_changed = False
        self.state.blockSignals(True)
        try:
            for txt, ch, attr in ch_map:
                text = txt.text().strip()
                glsl, err = validate_and_compile_expression(text, ch)
                if err:
                    txt.setStyleSheet(self._expr_error_style())
                    txt.setToolTip(f"Syntax Error: {err}")
                else:
                    txt.setStyleSheet(self._input_style())
                    txt.setToolTip(f"Compiled GLSL: {glsl}")
                    if getattr(self.state, attr, None) != text:
                        setattr(self.state, attr, text)
                        any_changed = True
        finally:
            self.state.blockSignals(False)

        if any_changed:
            self.state.changed.emit()

    def _reset_single_expr(self, txt: QLineEdit, attr: str) -> None:
        """Reset a single channel expression to default immediately."""
        self._expr_debounce_timer.stop()
        txt.blockSignals(True)
        txt.setText("")
        txt.blockSignals(False)
        setattr(self.state, attr, "")
        self._commit_channel_expressions()

    def _on_chk_red_toggled(self, chk: bool) -> None:
        self.state.enable_red = chk
        self.txt_expr_r.setEnabled(chk)

    def _on_chk_green_toggled(self, chk: bool) -> None:
        self.state.enable_green = chk
        self.txt_expr_g.setEnabled(chk)

    def _on_chk_blue_toggled(self, chk: bool) -> None:
        self.state.enable_blue = chk
        self.txt_expr_b.setEnabled(chk)

    def _on_chk_alpha_toggled(self, chk: bool) -> None:
        self.state.enable_alpha = chk
        self.txt_expr_a.setEnabled(chk)

    # -------------------------------------------------------------------------
    # Stylesheet Generators (Native 3DEqualizer Dark Slate & Warm Amber)
    # -------------------------------------------------------------------------
    def _btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #2c2c2c;
                color: #d8d8d8;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #555555;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #e5a823;
                color: #121212;
                border-color: #e5a823;
            }
        """

    def _toggle_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #2c2c2c;
                color: #d8d8d8;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #555555;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #e5a823;
                border-color: #f0b83b;
                color: #121212;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #c8921a;
                color: #121212;
            }
        """

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #141414;
                color: #f0f0f0;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 2px 5px;
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QLineEdit:focus {
                border-color: #e5a823;
                background-color: #191919;
            }
        """

    def _checkbox_style(self) -> str:
        return """
            QCheckBox {
                color: #d8d8d8;
                spacing: 4px;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                background-color: #161616;
            }
            QCheckBox::indicator:hover {
                border-color: #e5a823;
            }
            QCheckBox::indicator:checked {
                background-color: #e5a823;
                border-color: #f0b83b;
            }
        """

    def _slider_style(self) -> str:
        return """
            QSlider::groove:horizontal {
                height: 4px;
                background: #252525;
                border: 1px solid #383838;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #333333;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #b0b0b0;
                border: 1px solid #161616;
                width: 10px;
                height: 14px;
                margin: -5px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal:hover {
                background: #e5a823;
                border-color: #f0b83b;
            }
            QSlider::handle:horizontal:pressed {
                background: #f0b83b;
            }
        """

    def _spin_style(self) -> str:
        return """
            QDoubleSpinBox {
                background-color: #161616;
                color: #f0f0f0;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 1px 3px;
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QDoubleSpinBox:focus {
                border-color: #e5a823;
            }
        """

    def _mini_tool_btn_style(self) -> str:
        return """
            QToolButton {
                background-color: #252525;
                color: #888888;
                border: 1px solid #333333;
                border-radius: 2px;
                font-size: 10px;
            }
            QToolButton:hover {
                background-color: #383838;
                color: #e5a823;
                border-color: #e5a823;
            }
        """

    def _expr_error_style(self) -> str:
        return """
            QLineEdit {
                background-color: #2a1414;
                color: #ff9999;
                border: 1px solid #d9534f;
                border-radius: 2px;
                padding: 2px 5px;
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QLineEdit:focus {
                border-color: #ff5555;
            }
        """


# -----------------------------------------------------------------------------
# 8. Modern Dock Widget Wrapper
# -----------------------------------------------------------------------------
class XtraQCDockWidget(QDockWidget):
    """QDockWidget hosting the xtra QC Utils panel with hold-Q latch tracking."""

    def __init__(self, state: CompQCState, parent: Optional[QWidget] = None) -> None:
        super().__init__("xtra QC Utils", parent)
        self.setObjectName("CompQCDockWidget")
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.setTitleBarWidget(TabbedDockTitleBar(self))

        self._latched = False
        self.panel = XtraQCWidget(state, self)
        self.panel.latched.connect(self.set_latched)
        self.setWidget(self.panel)

    def is_latched(self) -> bool:
        return self._latched or self.panel.btn_pin.isChecked()

    def set_latched(self, val: bool) -> None:
        self._latched = val

    def closeEvent(self, event) -> None:
        self._latched = False
        self.panel.btn_pin.setChecked(False)
        super().closeEvent(event)


# Aliases for backward compatibility
CompQCHUDWidget = XtraQCWidget
CompQCDockWidget = XtraQCDockWidget
