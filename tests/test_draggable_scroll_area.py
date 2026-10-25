"""
Unit tests for BlenderScrollArea / DraggableScrollArea and universal MMB drag-scrolling.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
)

from openreview.widgets.draggable_scroll_area import BlenderScrollArea, DraggableScrollArea
from openreview.ui.image_info_dialog import ImageInfoWidget
from openreview.ui.export_dialog import ExportDialog
from openreview.ui.color_dialog import ColorAdjustmentsDialog
from openreview.ui.process_info_dialog import ProcessInfoDialog
from openreview.ui.preferences_dialog import PreferencesDialog
from openreview.core.preferences import PreferencesManager
from openreview.core.shortcuts import ShortcutManager


def test_blender_scroll_area_alias():
    assert BlenderScrollArea is DraggableScrollArea


def test_blender_scroll_area_mmb_drag(qtbot):
    scroll = BlenderScrollArea()
    scroll.resize(400, 300)
    qtbot.addWidget(scroll)

    content = QWidget()
    content.setFixedSize(400, 1500)
    layout = QVBoxLayout(content)
    btn_child = QPushButton("Child Button", content)
    layout.addWidget(btn_child)
    layout.addStretch()

    scroll.setWidget(content)
    scroll.show()
    qtbot.waitExposed(scroll)

    # Initial scroll position
    assert scroll.verticalScrollBar().value() == 0

    # 1. Middle Mouse Button Press at (100, 200)
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 200),
        QPointF(100, 200),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(scroll.viewport(), press_ev)
    assert scroll._mmb_dragging is True
    assert scroll._override_cursor_set is True

    # 2. Middle Mouse Drag up by 150 pixels (to y=50) -> Scroll value should increase by 150
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(100, 50),
        QPointF(100, 50),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(scroll.viewport(), move_ev)
    assert scroll.verticalScrollBar().value() == 150

    # 3. Middle Mouse Button Release
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(100, 50),
        QPointF(100, 50),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(scroll.viewport(), release_ev)
    assert scroll._mmb_dragging is False
    assert scroll._override_cursor_set is False


def test_blender_scroll_area_child_event_filtering(qtbot):
    scroll = BlenderScrollArea()
    scroll.resize(400, 300)
    qtbot.addWidget(scroll)

    content = QWidget()
    content.setFixedSize(400, 1200)
    layout = QVBoxLayout(content)
    label = QLabel("Nested Deep Label", content)
    layout.addWidget(label)
    layout.addStretch()
    scroll.setWidget(content)

    # MMB on child label directly
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(100, 200),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # The eventFilter on label intercepts MMB
    handled = scroll.eventFilter(label, press_ev)
    assert handled is True
    assert scroll._mmb_dragging is True

    # Move event
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(10, 0),
        QPointF(100, 100),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(label, move_ev)
    assert scroll.verticalScrollBar().value() == 100

    # Release event
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(10, 0),
        QPointF(100, 100),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(label, release_ev)
    assert scroll._mmb_dragging is False


def test_blender_scroll_area_hide_resets_cursor(qtbot):
    scroll = BlenderScrollArea()
    scroll.resize(400, 300)
    qtbot.addWidget(scroll)
    content = QWidget()
    content.setFixedSize(400, 1000)
    scroll.setWidget(content)
    scroll.show()

    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 100),
        QPointF(100, 100),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    scroll.eventFilter(scroll.viewport(), press_ev)
    assert scroll._mmb_dragging is True

    # Hide while dragging
    scroll.hide()
    assert scroll._mmb_dragging is False
    assert scroll._override_cursor_set is False


def test_image_info_widget_uses_blender_scroll(qtbot):
    widget = ImageInfoWidget({"file_name": "test.exr"})
    qtbot.addWidget(widget)
    assert isinstance(widget._scroll_area, BlenderScrollArea)


def test_preferences_dialog_tabs_wrapped_in_blender_scroll(qtbot):
    pref_mgr = PreferencesManager()
    dialog = PreferencesDialog(pref_mgr)
    qtbot.addWidget(dialog)

    # Verify each tab page is wrapped in a BlenderScrollArea
    assert dialog.tabs.count() == 5
    for i in range(dialog.tabs.count()):
        tab_widget = dialog.tabs.widget(i)
        assert isinstance(tab_widget, BlenderScrollArea), f"Tab {i} ({dialog.tabs.tabText(i)}) should be BlenderScrollArea"
