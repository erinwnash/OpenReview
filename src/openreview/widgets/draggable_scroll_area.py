"""
Draggable Scroll Area with Blender-style Middle Mouse Button (MMB) click & drag scrolling.
Supports seamless panning across any long form, properties panel, or dialog.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QPoint, QObject, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QScrollArea, QWidget, QApplication


class BlenderScrollArea(QScrollArea):
    """
    QScrollArea supporting Blender-style Middle Mouse Button (MMB) click & drag scrolling.
    Recursively installs event filters on all descendant child widgets so artists can
    MMB-drag from anywhere in the scroll area without interfering with LMB or RMB actions.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mmb_dragging = False
        self._drag_start_pos = QPoint()
        self._drag_start_vscroll = 0
        self._drag_start_hscroll = 0
        self._override_cursor_set = False
        self.viewport().installEventFilter(self)

    def setWidget(self, widget: QWidget) -> None:
        super().setWidget(widget)
        if widget:
            self._install_filter_recursive(widget)

    def _install_filter_recursive(self, w: QWidget) -> None:
        w.installEventFilter(self)
        for child in w.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        t = event.type()
        if t == QEvent.Type.ChildAdded:
            child = getattr(event, "child", lambda: None)()
            if isinstance(child, QWidget):
                self._install_filter_recursive(child)
        elif t == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.MiddleButton:
                self._mmb_dragging = True
                self._drag_start_pos = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                self._drag_start_vscroll = self.verticalScrollBar().value()
                self._drag_start_hscroll = self.horizontalScrollBar().value()
                if not self._override_cursor_set:
                    QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)
                    self._override_cursor_set = True
                return True
        elif t == QEvent.Type.MouseMove:
            if self._mmb_dragging and isinstance(event, QMouseEvent):
                cur_pos = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                delta = cur_pos - self._drag_start_pos
                self.verticalScrollBar().setValue(self._drag_start_vscroll - delta.y())
                self.horizontalScrollBar().setValue(self._drag_start_hscroll - delta.x())
                return True
        elif t == QEvent.Type.MouseButtonRelease:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.MiddleButton:
                self._mmb_dragging = False
                if self._override_cursor_set:
                    QApplication.restoreOverrideCursor()
                    self._override_cursor_set = False
                return True
        return super().eventFilter(watched, event)

    def hideEvent(self, event) -> None:
        if self._mmb_dragging:
            self._mmb_dragging = False
            if self._override_cursor_set:
                QApplication.restoreOverrideCursor()
                self._override_cursor_set = False
        super().hideEvent(event)


# Alias for flexible naming convention
DraggableScrollArea = BlenderScrollArea
