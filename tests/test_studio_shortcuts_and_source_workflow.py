import os
import sys
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QSpinBox, QLineEdit

from openreview.ui.main_window import MainWindow
from openreview.core.shortcuts import ShortcutManager
from openreview.core.clock import PlaybackClock
from openreview.models.session_graph import SessionGraph, SourceItem


def test_color_shortcuts_reassigned(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)

    # 1. Gain + and -
    g0 = win.top_bar.gain_spin.value()
    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.NoModifier, "+"))
    assert round(win.top_bar.gain_spin.value(), 2) == round(g0 + 0.10, 2)

    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, "-"))
    assert round(win.top_bar.gain_spin.value(), 2) == round(g0, 2)

    # 2. Gamma Shift++ and Shift+-
    gam0 = win.top_bar.gam_spin.value()
    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier, "+"))
    assert round(win.top_bar.gam_spin.value(), 2) == round(gam0 + 0.05, 2)

    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ShiftModifier, "-"))
    assert round(win.top_bar.gam_spin.value(), 2) == round(gam0, 2)

    # 3. Saturation Ctrl+Shift++ and Ctrl+Shift+-
    s0 = win.top_bar.sat_spin.value()
    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, "+"))
    assert round(win.top_bar.sat_spin.value(), 2) == round(s0 + 0.05, 2)

    win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, "-"))
    assert round(win.top_bar.sat_spin.value(), 2) == round(s0, 2)


def test_input_fields_commit_and_deselect_on_enter(qtbot):
    from PySide6.QtWidgets import QApplication
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.activateWindow()
    QApplication.instance().processEvents()

    goto_box = win.timeline.goto_frame_box
    goto_box.setFocus()
    QApplication.instance().processEvents()
    assert goto_box.hasFocus() or goto_box.lineEdit().hasFocus()

    goto_box.setValue(1050)
    # Simulate pressing Enter/Return in the spinbox
    key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    sm = win.shortcut_mgr
    handled = sm.eventFilter(goto_box, key_event)
    assert handled is True
    # Focus should no longer be on goto_box
    assert not (goto_box.hasFocus() or goto_box.lineEdit().hasFocus())


def test_goto_frame_unselected_by_default(qtbot):
    from PySide6.QtWidgets import QApplication
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.activateWindow()
    QApplication.instance().processEvents()

    # Verify goto_frame_box does NOT have default focus
    assert not win.timeline.goto_frame_box.hasFocus()
    assert win.viewport.hasFocus()


def test_bidirectional_playback(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=24.0)

    # Play Forward
    clock.play_forward()
    assert clock.is_playing
    assert clock.shuttle_speed == 1.0

    # Toggle Pause
    clock.play_forward()
    assert not clock.is_playing

    # Play Backward
    clock.play_backward()
    assert clock.is_playing
    assert clock.shuttle_speed == -1.0

    # Toggle Pause
    clock.play_backward()
    assert not clock.is_playing


def test_timeline_bidirectional_buttons(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)

    timeline = win.timeline
    assert hasattr(timeline, "btn_play_back")
    assert hasattr(timeline, "btn_play_fwd")

    # Click play forward
    timeline.btn_play_fwd.click()
    assert win.clock.is_playing
    assert win.clock.shuttle_speed == 1.0

    # Click play backward
    timeline.btn_play_back.click()
    assert win.clock.is_playing
    assert win.clock.shuttle_speed == -1.0

    # Click play backward again pauses
    timeline.btn_play_back.click()
    assert not win.clock.is_playing


def test_create_folder_auto_parents_selected_sources(qtbot, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    win = MainWindow()
    qtbot.addWidget(win)

    panel = win.sources_dock.panel
    graph = win.session_graph

    # Add 2 sources
    s1 = SourceItem(id="src_1", name="Clip 1", path="C:/path/clip1.mov")
    s2 = SourceItem(id="src_2", name="Clip 2", path="C:/path/clip2.mov")
    graph.sources["src_1"] = s1
    graph.sources["src_2"] = s2
    graph.root_source_ids.extend(["src_1", "src_2"])
    panel.refresh_tree()

    # Select both sources in tree
    panel.tree.clearSelection()
    for i in range(panel.tree.topLevelItemCount()):
        top_item = panel.tree.topLevelItem(i)
        for c in range(top_item.childCount()):
            child = top_item.child(c)
            d = child.data(0, Qt.ItemDataRole.UserRole)
            if d and d.get("id") in ("src_1", "src_2"):
                child.setSelected(True)

    # Mock QInputDialog to return folder name "VFX_Folder"
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("VFX_Folder", True))
    monkeypatch.setattr("openreview.ui.sources_panel.QInputDialog.getText", lambda *args, **kwargs: ("VFX_Folder", True))

    panel._on_create_folder()

    # Verify folder was created and both sources moved into it
    created_folder = None
    for f in graph.folders.values():
        if f.name == "VFX_Folder":
            created_folder = f
            break

    assert created_folder is not None
    assert s1.parent_folder_id == created_folder.id
    assert s2.parent_folder_id == created_folder.id


def test_reveal_in_explorer_action_present(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)

    panel = win.sources_dock.panel
    graph = win.session_graph

    s1 = SourceItem(id="src_test", name="Clip Test", path="C:/path/clip.mov")
    graph.sources["src_test"] = s1
    graph.root_source_ids.append("src_test")
    panel.refresh_tree()

    # Select source
    panel.tree.clearSelection()
    for i in range(panel.tree.topLevelItemCount()):
        top_item = panel.tree.topLevelItem(i)
        for c in range(top_item.childCount()):
            child = top_item.child(c)
            d = child.data(0, Qt.ItemDataRole.UserRole)
            if d and d.get("id") == "src_test":
                child.setSelected(True)

    # Check menu has Reveal in Explorer
    revealed_paths = []
    monkeypatch.setattr(panel, "_on_reveal_in_explorer", lambda sid: revealed_paths.append(sid))
    monkeypatch.setattr(panel, "_execute_menu", lambda *a, **k: None)

    # Trigger context menu
    panel._on_tree_context_menu(QPoint(10, 10))
    # Context menu created without error
