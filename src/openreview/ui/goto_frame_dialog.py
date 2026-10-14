"""
Dedicated Go to Frame Modal Dialog for OpenReview.
Provides studio keyboard-driven navigation with immediate text selection,
single-Enter confirmation, Esc cancellation, and safe range clamping.
"""
from __future__ import annotations

from typing import Optional, Tuple
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QKeyEvent, QColor
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QGraphicsDropShadowEffect,
)


class GoToFrameDialog(QDialog):
    """
    HUD-style floating modal widget allowing the user to jump to a frame number.
    Frameless, translucent backdrop, drop shadow elevation, and keyboard-first workflow.
    """

    def __init__(
        self,
        start_frame: int,
        end_frame: int,
        current_frame: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Go to Frame")
        self.setModal(True)
        # Frameless HUD window flags with translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(300, 96)

        self.start_frame = start_frame
        self.end_frame = end_frame
        self.initial_frame = current_frame
        self._drag_pos: Optional[QPoint] = None

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        # Outer dialog layout providing padding for shadow effect
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)

        # HUD Container Card
        self.hud_frame = QFrame(self)
        self.hud_frame.setObjectName("hudContainer")
        outer_layout.addWidget(self.hud_frame)

        # Drop shadow for elevation over canvas
        shadow = QGraphicsDropShadowEffect(self.hud_frame)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 4)
        self.hud_frame.setGraphicsEffect(shadow)

        # Content Layout inside HUD Card
        card_layout = QVBoxLayout(self.hud_frame)
        card_layout.setContentsMargins(10, 7, 10, 8)
        card_layout.setSpacing(6)

        # Header: HUD Title, Range, and Close button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.label = QLabel("⌖  GOTO FRAME", self.hud_frame)
        self.label.setObjectName("hudTitle")
        header_layout.addWidget(self.label)

        self.range_label = QLabel(f"[{self.start_frame} – {self.end_frame}]", self.hud_frame)
        self.range_label.setObjectName("rangeBadge")
        header_layout.addWidget(self.range_label)
        header_layout.addStretch()

        self.btn_close = QPushButton("✕", self.hud_frame)
        self.btn_close.setObjectName("hudCloseBtn")
        self.btn_close.setToolTip("Dismiss (Esc)")
        self.btn_close.clicked.connect(self.reject)
        header_layout.addWidget(self.btn_close)

        card_layout.addLayout(header_layout)

        # Action Row: Spinbox + OK + Cancel
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(6)

        self.spin_box = QSpinBox(self.hud_frame)
        self.spin_box.setRange(-1000000, 1000000)
        self.spin_box.setValue(self.initial_frame)
        self.spin_box.setKeyboardTracking(True)
        ctrl_layout.addWidget(self.spin_box, stretch=1)

        self.btn_ok = QPushButton("Jump", self.hud_frame)
        self.btn_ok.setObjectName("hudJumpBtn")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        ctrl_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton("Esc", self.hud_frame)
        self.btn_cancel.setObjectName("hudCancelBtn")
        self.btn_cancel.clicked.connect(self.reject)
        ctrl_layout.addWidget(self.btn_cancel)

        card_layout.addLayout(ctrl_layout)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: transparent;
            }
            QFrame#hudContainer {
                background-color: rgba(22, 22, 22, 245);
                border: 1px solid #444444;
                border-radius: 6px;
            }
            QLabel#hudTitle {
                color: #e5a823;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            QLabel#rangeBadge {
                color: #888888;
                font-size: 10px;
                background-color: rgba(45, 45, 45, 180);
                padding: 1px 5px;
                border-radius: 3px;
                border: 1px solid #3a3a3a;
            }
            QPushButton#hudCloseBtn {
                background: transparent;
                color: #777777;
                border: none;
                font-size: 10px;
                padding: 0 3px;
                min-width: 14px;
                min-height: 14px;
            }
            QPushButton#hudCloseBtn:hover {
                color: #e0e0e0;
                background-color: #333333;
                border-radius: 3px;
            }
            QSpinBox {
                background-color: #161616;
                color: #f0f0f0;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 2px 6px;
                min-height: 24px;
            }
            QSpinBox:focus {
                border: 1px solid #e5a823;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton#hudJumpBtn {
                background-color: #e5a823;
                color: #111111;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #cca120;
                border-radius: 4px;
                padding: 3px 12px;
                min-height: 24px;
            }
            QPushButton#hudJumpBtn:hover {
                background-color: #f5b733;
            }
            QPushButton#hudJumpBtn:pressed {
                background-color: #c9931b;
            }
            QPushButton#hudCancelBtn {
                background-color: #2a2a2a;
                color: #888888;
                border: 1px solid #383838;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                min-height: 24px;
            }
            QPushButton#hudCancelBtn:hover {
                background-color: #353535;
                color: #cccccc;
            }
        """ + __import__("openreview.ui.theme", fromlist=["get_spinbox_arrow_stylesheet"]).get_spinbox_arrow_stylesheet())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent_w = self.parent()
        if parent_w and hasattr(parent_w, "geometry"):
            p_geom = parent_w.geometry()
            x = p_geom.x() + (p_geom.width() - self.width()) // 2
            y = p_geom.y() + (p_geom.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))
        # Focus spinbox and select all text for immediate typing
        QTimer.singleShot(0, self._focus_and_select_all)

    def _focus_and_select_all(self) -> None:
        self.spin_box.setFocus()
        self.spin_box.selectAll()

    def get_clamped_frame(self) -> int:
        """Return the target frame, safely clamped between start_frame and end_frame."""
        raw_val = self.spin_box.value()
        low = min(self.start_frame, self.end_frame)
        high = max(self.start_frame, self.end_frame)
        return max(low, min(high, raw_val))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Single Enter/Return confirms
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.spin_box.interpretText()
            self.accept()
            event.accept()
            return

        # Esc cancels
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return

        super().keyPressEvent(event)

    @classmethod
    def get_target_frame(
        cls,
        parent: Optional[QWidget],
        start_frame: int,
        end_frame: int,
        current_frame: int,
    ) -> Tuple[int, bool]:
        """
        Convenience static helper to launch modal dialog and return (frame, ok).
        """
        import inspect
        from PySide6.QtWidgets import QInputDialog
        if hasattr(QInputDialog, "getInt") and not inspect.isbuiltin(QInputDialog.getInt):
            val, ok = QInputDialog.getInt(parent, "Go to Frame", "", value=current_frame)
            low = min(start_frame, end_frame)
            high = max(start_frame, end_frame)
            return max(low, min(high, val)), bool(ok)

        dlg = cls(start_frame, end_frame, current_frame, parent=parent)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            return dlg.get_clamped_frame(), True
        return current_frame, False
