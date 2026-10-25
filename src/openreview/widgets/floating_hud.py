"""
Floating Translucent HUD Card and Detachable Window.
Enables in-canvas draggable floating tools or detachable secondary-screen dialogs.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QPoint, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPaintEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QFrame,
    QSizeGrip,
)


class FloatingHUDCard(QFrame):
    """
    Floating translucent HUD card:
    - Sits inside the viewport canvas with dark semi-transparent glass styling.
    - Draggable title bar clamped to canvas boundaries.
    - Can be detached into a floating standalone tool window (Options 1 & 3).
    - Collapsible body to save screen estate.
    """

    closed = Signal()
    detached_toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        content_widget: QWidget,
        parent: Optional[QWidget] = None,
        initial_pos: QPoint = QPoint(40, 40),
    ):
        super().__init__(parent)
        self.setObjectName("floatingHUDCard")
        self._host_viewport: Optional[QWidget] = parent
        self._title = title
        self._content_widget = content_widget
        self._is_collapsed = False
        self._is_detached = False
        self._dock_mode: Optional[str] = None  # None (float), "right", "left"
        self._drag_start_pos: Optional[QPoint] = None
        self._resize_zone: str = "none"
        self._resize_start_pos: Optional[QPoint] = None
        self._resize_start_geom: Optional[QRect] = None
        self._hud_opacity: float = 0.85

        self.setMouseTracking(True)
        self.setMinimumSize(180, 50)
        self._setup_ui()
        self._enable_child_mouse_tracking(self)
        self.move(initial_pos)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render high-performance dark glass background with antialiased rounded border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = int(self._hud_opacity * 255)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setBrush(QColor(26, 26, 26, alpha))
        painter.setPen(QColor(68, 68, 68, 255))
        painter.drawRoundedRect(rect, 4, 4)

    def set_hud_opacity(self, opacity: float) -> None:
        """Set floating HUD dark glass background opacity (0.3 to 1.0) with zero CSS recalculation overhead."""
        new_op = max(0.3, min(1.0, float(opacity)))
        if abs(self._hud_opacity - new_op) > 0.001:
            self._hud_opacity = new_op
            self.update()

    def _setup_ui(self) -> None:
        from openreview.ui.theme import get_spinbox_arrow_stylesheet
        self.setStyleSheet("""
            QFrame#floatingHUDCard {
                background: transparent;
                border: none;
            }
        """ + get_spinbox_arrow_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        # Title Bar (fixed height so it never stretches when content shrinks)
        title_bar = QWidget(self)
        title_bar.setFixedHeight(22)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(2, 0, 2, 0)
        title_layout.setSpacing(4)

        # Title Label
        self.title_label = QLabel(self._title, title_bar)
        self.title_label.setStyleSheet("color: #e5a823; font-weight: bold; font-size: 11px;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # Dock to Edge Button (Photoshop style)
        self.dock_btn = QToolButton(title_bar)
        self.dock_btn.setText("◧")
        self.dock_btn.setToolTip("Dock to Right Edge / Float")
        self.dock_btn.setFixedSize(16, 16)
        self.dock_btn.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")
        self.dock_btn.clicked.connect(self.toggle_dock_edge)
        title_layout.addWidget(self.dock_btn)

        # Detach Button
        self.detach_btn = QToolButton(title_bar)
        self.detach_btn.setText("↗")
        self.detach_btn.setToolTip("Detach as floating window")
        self.detach_btn.setFixedSize(16, 16)
        self.detach_btn.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")
        self.detach_btn.clicked.connect(self.toggle_detach)
        title_layout.addWidget(self.detach_btn)

        # Collapse Button
        self.collapse_btn = QToolButton(title_bar)
        self.collapse_btn.setText("−")
        self.collapse_btn.setToolTip("Collapse panel")
        self.collapse_btn.setFixedSize(16, 16)
        self.collapse_btn.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        title_layout.addWidget(self.collapse_btn)

        # Close Button
        self.close_btn = QToolButton(title_bar)
        self.close_btn.setText("✕")
        self.close_btn.setToolTip("Close panel")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet("color: #888888; background: transparent; border: none;")
        self.close_btn.clicked.connect(self.close_panel)
        title_layout.addWidget(self.close_btn)

        layout.addWidget(title_bar, 0)

        # Content Widget
        self._content_widget.setParent(self)
        layout.addWidget(self._content_widget, 1)

        # Bottom SizeGrip Row (Right aligned)
        grip_bar = QHBoxLayout()
        grip_bar.setContentsMargins(0, 0, 0, 0)
        grip_bar.addStretch()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(12, 12)
        self.size_grip.setStyleSheet("background: transparent;")
        grip_bar.addWidget(self.size_grip)
        layout.addLayout(grip_bar, 0)

    def auto_adjust_height(self) -> None:
        """Automatically recalculate and shrink/expand the HUD card height to tightly fit its visible content."""
        if self._is_collapsed:
            self.adjustSize()
            return
        if self._content_widget.layout() is not None:
            self._content_widget.layout().invalidate()
            self._content_widget.layout().activate()
        self._content_widget.updateGeometry()
        self._content_widget.adjustSize()

        if self.layout() is not None:
            self.layout().invalidate()
            self.layout().activate()
        self.updateGeometry()

        content_hint = self._content_widget.sizeHint().expandedTo(self._content_widget.minimumSizeHint())
        content_w = max(
            content_hint.width(),
            self._content_widget.minimumWidth(),
            self._content_widget.width(),
        )
        content_h = max(content_hint.height(), self._content_widget.minimumHeight())
        # 22px title_bar + 12px grip + 10px margins + 8px spacing = 52px chrome overhead
        target_w = max(self.minimumWidth(), content_w + 16)
        target_h = max(self.minimumHeight(), content_h + 48)
        self.resize(target_w, target_h)
        self.realign_docked()

    # --------------------------------------------------------------------------
    # Dragging & Border Resizing Logic (Photoshop-style Docking and Resizing)
    # --------------------------------------------------------------------------
    RESIZE_MARGIN = 6

    def _get_resize_zone(self, pos: QPoint) -> str:
        if self._is_collapsed:
            return "none"
        w = self.width()
        h = self.height()
        x = pos.x()
        y = pos.y()
        m = self.RESIZE_MARGIN

        on_left = (0 <= x <= m)
        on_right = (w - m <= x <= w)
        on_top = (0 <= y <= m)
        on_bottom = (h - m <= y <= h)

        if on_top and on_left:
            return "top_left"
        elif on_top and on_right:
            return "top_right"
        elif on_bottom and on_left:
            return "bottom_left"
        elif on_bottom and on_right:
            return "bottom_right"
        elif on_left:
            return "left"
        elif on_right:
            return "right"
        elif on_top:
            return "top"
        elif on_bottom:
            return "bottom"
        return "none"

    def _update_cursor_for_zone(self, zone: str) -> None:
        if zone in ("top_left", "bottom_right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif zone in ("top_right", "bottom_left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif zone in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def leaveEvent(self, event) -> None:
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.raise_()
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._get_resize_zone(event.position().toPoint())
            if zone != "none":
                self._resize_zone = zone
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
                event.accept()
                return
            elif event.position().y() <= 24:
                self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
                event.accept()
                return
        super().mousePressEvent(event)

    def _enable_child_mouse_tracking(self, root: QWidget) -> None:
        """Enable mouse tracking and event filtering on all child widgets so viewport sampling never stalls."""
        for child in root.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

    def _forward_sample_pos(self, global_pos: QPoint) -> None:
        host = self.parentWidget() or self._host_viewport
        if host is not None and hasattr(host, "sample_at_global_pos"):
            host.sample_at_global_pos(global_pos)

    def eventFilter(self, watched, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseMove:
            if hasattr(event, "globalPosition"):
                self._forward_sample_pos(event.globalPosition().toPoint())
        elif event.type() == QEvent.Type.ChildAdded and hasattr(event, "child"):
            c = event.child()
            if isinstance(c, QWidget):
                c.setMouseTracking(True)
                c.installEventFilter(self)
                self._enable_child_mouse_tracking(c)
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event) -> None:
        if hasattr(event, "globalPosition"):
            self._forward_sample_pos(event.globalPosition().toPoint())

        if self._resize_zone != "none" and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geom = QRect(self._resize_start_geom)
            min_w = 180
            min_h = 60

            if "right" in self._resize_zone:
                geom.setWidth(max(min_w, self._resize_start_geom.width() + delta.x()))
            if "left" in self._resize_zone:
                new_w = max(min_w, self._resize_start_geom.width() - delta.x())
                geom.setLeft(self._resize_start_geom.right() - new_w)
            if "bottom" in self._resize_zone:
                geom.setHeight(max(min_h, self._resize_start_geom.height() + delta.y()))
            if "top" in self._resize_zone:
                new_h = max(min_h, self._resize_start_geom.height() - delta.y())
                geom.setTop(self._resize_start_geom.bottom() - new_h)

            self.setGeometry(geom)
            event.accept()
            return

        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            if not self._is_detached and self.parentWidget():
                parent_rect = self.parentWidget().rect()
                max_x = max(0, parent_rect.width() - self.width())
                max_y = max(0, parent_rect.height() - self.height())
                clamped_x = max(0, min(new_pos.x(), max_x))
                clamped_y = max(0, min(new_pos.y(), max_y))

                # Edge snapping (28px threshold)
                snap_dist = 28
                if clamped_x >= max_x - snap_dist:
                    clamped_x = max(0, max_x - 8)
                    self._dock_mode = "right"
                    self.dock_btn.setStyleSheet("color: #e5a823; background: transparent; border: none;")
                elif clamped_x <= snap_dist:
                    clamped_x = 8
                    self._dock_mode = "left"
                    self.dock_btn.setStyleSheet("color: #e5a823; background: transparent; border: none;")
                else:
                    self._dock_mode = None
                    self.dock_btn.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")

                self.move(clamped_x, clamped_y)
            else:
                self.move(new_pos)
            event.accept()
            return

        # No buttons down: update hover cursor
        zone = self._get_resize_zone(event.position().toPoint())
        self._update_cursor_for_zone(zone)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resize_zone = "none"
        self._drag_start_pos = None
        self._update_cursor_for_zone(self._get_resize_zone(event.position().toPoint()))
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_I):
            self.close_panel()
            event.accept()
            return
        super().keyPressEvent(event)

    # --------------------------------------------------------------------------
    # Panel Actions
    # --------------------------------------------------------------------------
    def toggle_dock_edge(self) -> None:
        """Dock panel flush to right edge or restore to float."""
        if not self.parentWidget() or self._is_detached:
            return
        if self._dock_mode == "right":
            self._dock_mode = None
            self.dock_btn.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")
            self.move(max(20, self.x() - 100), self.y())
        else:
            self.dock_to_right()

    def dock_to_right(self) -> None:
        """Snap panel flush against right canvas boundary."""
        if not self.parentWidget():
            return
        self._dock_mode = "right"
        self.dock_btn.setStyleSheet("color: #e5a823; background: transparent; border: none;")
        max_x = max(0, self.parentWidget().width() - self.width() - 8)
        self.move(max_x, self.y())

    def dock_to_left(self) -> None:
        """Snap panel flush against left canvas boundary."""
        if not self.parentWidget():
            return
        self._dock_mode = "left"
        self.dock_btn.setStyleSheet("color: #e5a823; background: transparent; border: none;")
        self.move(8, self.y())

    def realign_docked(self) -> None:
        """Re-anchor to docked edge on parent resize or clamp within canvas."""
        if not self.parentWidget() or self._is_detached:
            return
        if self._dock_mode == "right":
            max_x = max(0, self.parentWidget().width() - self.width() - 8)
            self.move(max_x, self.y())
        elif self._dock_mode == "left":
            self.move(8, self.y())
        else:
            max_x = max(8, self.parentWidget().width() - self.width() - 8)
            max_y = max(8, self.parentWidget().height() - self.height() - 8)
            cur_x = min(max(8, self.x()), max_x)
            cur_y = min(max(8, self.y()), max_y)
            self.move(cur_x, cur_y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.realign_docked()

    def toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        self._content_widget.setVisible(not self._is_collapsed)
        self.collapse_btn.setText("+" if self._is_collapsed else "−")
        self.adjustSize()

    def toggle_detach(self) -> None:
        """Toggle between in-canvas child widget and standalone OS tool window."""
        self._is_detached = not self._is_detached
        if self._is_detached:
            pos = self.mapToGlobal(QPoint(0, 0))
            self.setParent(None)
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self.move(pos)
            self.show()
            self.detach_btn.setText("↙")
            self.detach_btn.setToolTip("Dock back to canvas")
        else:
            # Need to be reparented by container
            self.setWindowFlags(Qt.WindowType.Widget)
            self.detach_btn.setText("↗")
            self.detach_btn.setToolTip("Detach as floating window")
        self.detached_toggled.emit(self._is_detached)

    def close_panel(self) -> None:
        self.hide()
        self.closed.emit()
