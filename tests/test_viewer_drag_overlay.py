import os
import json
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QImage, QPainter
from PySide6.QtWidgets import QApplication

from openreview.widgets.viewport import ViewportCanvas as Viewport
from openreview.ui.main_window import MainWindow
from openreview.models.session_graph import ViewType, StackView, SourceItem


@pytest.fixture
def sample_media_files(tmp_path):
    p1 = str(tmp_path / "shot_01.exr")
    p2 = str(tmp_path / "shot_02.exr")
    p3 = str(tmp_path / "shot_03.exr")
    for p in (p1, p2, p3):
        with open(p, "wb") as f:
            f.write(b"SAMPLE_IMAGE_DATA")
    return [p1, p2, p3]


def test_viewport_drag_overlay_interaction(qtbot):
    viewport = Viewport()
    qtbot.addWidget(viewport)
    viewport.resize(800, 600)
    viewport.show()

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("C:/dummy/shot_01.exr")])

    # 1. Drag enters upper half (Top: Add Media to the stack)
    enter_ev_top = QDragEnterEvent(
        QPoint(400, 150),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.dragEnterEvent(enter_ev_top)
    assert viewport._drag_overlay_active is True
    assert viewport._drag_target == "stack"

    # 2. Drag moves to lower half (Bottom: Just add the media to source bin)
    move_ev_bottom = QDragMoveEvent(
        QPoint(400, 450),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.dragMoveEvent(move_ev_bottom)
    assert viewport._drag_overlay_active is True
    assert viewport._drag_target == "bin"

    # 3. Drag moves back to upper half
    move_ev_top = QDragMoveEvent(
        QPoint(400, 150),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.dragMoveEvent(move_ev_top)
    assert viewport._drag_target == "stack"

    # 4. Drag leaves viewport
    leave_ev = QDragLeaveEvent()
    viewport.dragLeaveEvent(leave_ev)
    assert viewport._drag_overlay_active is False
    assert viewport._drag_target is None


def test_viewport_paint_overlay_renders_cleanly(qtbot):
    viewport = Viewport()
    qtbot.addWidget(viewport)
    viewport.resize(800, 600)

    # Test painting overlay in active top state
    viewport._drag_overlay_active = True
    viewport._drag_target = "stack"

    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.black)
    painter = QPainter(img)
    try:
        viewport._paint_drag_drop_overlay(painter)
    finally:
        painter.end()

    # Test painting overlay in active bottom state
    viewport._drag_target = "bin"
    painter = QPainter(img)
    try:
        viewport._paint_drag_drop_overlay(painter)
    finally:
        painter.end()


def test_main_window_drop_bottom_adds_to_bin_only(qtbot, sample_media_files):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # Verify initial active view is empty or default
    init_active_id = mw.session_graph.active_view_id

    # Drop into bottom (bin)
    mw._on_viewport_files_dropped_target(sample_media_files[:2], target="bin")

    # Sources should be in session_graph.sources
    assert len(mw.session_graph.sources) == 2
    # But active view should NOT have changed to them
    assert mw.session_graph.active_view_id == init_active_id


def test_main_window_drop_top_creates_default_stack(qtbot, sample_media_files):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # Drop 2 media files onto top
    mw._on_viewport_files_dropped_target(sample_media_files[:2], target="stack")

    # A stack named "Default stack" should be created
    assert len(mw.session_graph.stacks) == 1
    stk = list(mw.session_graph.stacks.values())[0]
    assert stk.name == "Default stack"
    assert len(stk.source_ids) == 2
    # First two layers are layer A and layer B
    assert stk.index_a == 0
    assert stk.index_b == 1
    assert stk.compare_mode == "switch"
    # Viewport should be switched to this stack
    assert mw.session_graph.active_view_type == ViewType.STACK
    assert mw.session_graph.active_view_id == stk.id


def test_main_window_drop_top_multiple_media_layers(qtbot, sample_media_files):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # Drop 3 media files onto top
    mw._on_viewport_files_dropped_target(sample_media_files, target="stack")

    stk = list(mw.session_graph.stacks.values())[0]
    assert len(stk.source_ids) == 3
    assert stk.index_a == 0
    assert stk.index_b == 1


def test_main_window_drop_top_appends_to_active_stack(qtbot, sample_media_files):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # Drop 2 items to create initial stack
    mw._on_viewport_files_dropped_target(sample_media_files[:2], target="stack")
    stk = list(mw.session_graph.stacks.values())[0]
    assert len(stk.source_ids) == 2

    # Now drop the 3rd item while stack is active
    mw._on_viewport_files_dropped_target([sample_media_files[2]], target="stack")

    # Still only 1 stack, but now with 3 layers
    assert len(mw.session_graph.stacks) == 1
    assert len(stk.source_ids) == 3
    # Layer A and B assignments preserved
    assert stk.index_a == 0
    assert stk.index_b == 1


def test_main_window_drop_internal_sources_from_panel(qtbot, sample_media_files):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # First add media to bin via bottom drop
    mw._on_viewport_files_dropped_target(sample_media_files[:2], target="bin")
    assert len(mw.session_graph.sources) == 2
    sids = list(mw.session_graph.sources.keys())

    # Now simulate dragging existing source IDs into top overlay
    mw._on_viewport_files_dropped_target([], target="stack", source_ids=sids)

    # Should create stack using existing source IDs without duplicating bin items
    assert len(mw.session_graph.sources) == 2
    assert len(mw.session_graph.stacks) == 1
    stk = list(mw.session_graph.stacks.values())[0]
    assert stk.source_ids == sids
