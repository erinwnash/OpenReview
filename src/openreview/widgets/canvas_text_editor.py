"""
In-Canvas Floating Text Annotation Editor.
Provides an interactive, studio-grade on-screen text input directly over the viewport canvas.
Supports multi-line text (Shift+Enter), single-line commit (Enter), escape cancellation,
and auto-expanding geometry without interfering with global keyboard shortcuts.
"""
from __future__ import annotations

from typing import Optional, Tuple
from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QKeyEvent, QFocusEvent
from PySide6.QtWidgets import QTextEdit, QWidget


class CanvasTextEditor(QTextEdit):
    """
    Floating, auto-resizing text editor overlaid directly on the Viewport canvas.
    """

    committed = Signal(str)  # Emitted when user commits text (Enter)
    cancelled = Signal()     # Emitted when user cancels editing (Escape)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("CanvasTextEditor")
        self.setPlaceholderText("Type note... (Enter to save, Esc to cancel)")
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Positioning state in screen coordinates
        self.spawn_screen_pos: QPoint = QPoint(0, 0)
        self._is_finishing: bool = False
        self._is_active: bool = False
        self._stroke_color: Tuple[int, int, int, int] = (229, 168, 35, 255)

        self.set_stroke_color(self._stroke_color)
        self.textChanged.connect(self._on_text_changed)
        self.hide()

    def is_active(self) -> bool:
        """Return True if editor is currently active and editing text."""
        return self._is_active and not self.isHidden()

    def set_stroke_color(self, color_tuple: Tuple[int, int, int, int], font_pt: int = 12) -> None:
        """Update border, text color, and highlight color to match annotation brush settings."""
        self._stroke_color = color_tuple
        r, g, b = color_tuple[:3]
        self.setStyleSheet(f"""
            QTextEdit#CanvasTextEditor {{
                background-color: rgba(18, 18, 18, 235);
                color: rgb({r}, {g}, {b});
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 4px;
                padding: 6px 10px;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: {max(11, font_pt)}pt;
                font-weight: bold;
                selection-background-color: rgba({r}, {g}, {b}, 140);
                selection-color: #ffffff;
            }}
        """)

    def spawn_at(self, screen_pos: QPoint, initial_text: str = "") -> None:
        """Position and display the editor at the specified viewport screen coordinates."""
        self._is_finishing = False
        self._is_active = True
        self.spawn_screen_pos = QPoint(screen_pos)
        self.setPlainText(initial_text)
        if initial_text:
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.setTextCursor(cursor)

        self._update_geometry()
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_text_changed(self) -> None:
        """Dynamically expand bounds to fit typed text smoothly."""
        self._update_geometry()

    def _update_geometry(self) -> None:
        """Calculate responsive geometry based on text content and clamp within parent."""
        doc = self.document()
        ideal_w = int(doc.idealWidth()) + 32
        doc_h = int(self.document().size().height()) + 20

        target_w = max(220, min(650, ideal_w))
        target_h = max(46, min(360, doc_h))

        # Position clamped to parent bounds
        parent = self.parentWidget()
        x = self.spawn_screen_pos.x()
        y = self.spawn_screen_pos.y()

        if parent:
            pw = parent.width()
            ph = parent.height()
            if x + target_w > pw - 10:
                x = max(10, pw - target_w - 10)
            if y + target_h > ph - 10:
                y = max(10, ph - target_h - 10)

        self.setGeometry(x, y, target_w, target_h)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # Enter / Return handling
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter -> Insert newline
                self.insertPlainText("\n")
                event.accept()
                return
            else:
                # Enter -> Commit
                event.accept()
                self.commit()
                return

        # Escape -> Cancel
        if key == Qt.Key.Key_Escape:
            event.accept()
            self.cancel()
            return

        # Tab -> Insert spaces
        if key == Qt.Key.Key_Tab:
            self.insertPlainText("    ")
            event.accept()
            return

        super().keyPressEvent(event)

    def commit(self) -> None:
        """Commit the current text and hide the editor."""
        if self._is_finishing:
            return
        self._is_finishing = True
        self._is_active = False
        text = self.toPlainText()
        self.hide()
        self.committed.emit(text)

    def cancel(self) -> None:
        """Cancel editing, discard text, and hide the editor."""
        if self._is_finishing:
            return
        self._is_finishing = True
        self._is_active = False
        self.clear()
        self.hide()
        self.cancelled.emit()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """When clicking outside the editor widget, automatically commit if text exists."""
        super().focusOutEvent(event)
        if not self._is_finishing and self.is_active():
            text = self.toPlainText().strip()
            if text:
                self.commit()
            else:
                self.cancel()
