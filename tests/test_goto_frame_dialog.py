"""
Unit tests for the GoToFrameDialog and modal keyboard handling.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog

from openreview.ui.goto_frame_dialog import GoToFrameDialog
from openreview.ui.main_window import MainWindow
from openreview.core.shortcuts import ShortcutManager


def test_goto_frame_dialog_clamping(qtbot):
    dlg = GoToFrameDialog(start_frame=1001, end_frame=1200, current_frame=1050)
    qtbot.addWidget(dlg)

    # Within bounds
    dlg.spin_box.setValue(1100)
    assert dlg.get_clamped_frame() == 1100

    # Below start frame clamps to start_frame
    dlg.spin_box.setValue(500)
    assert dlg.get_clamped_frame() == 1001

    # Above end frame clamps to end_frame
    dlg.spin_box.setValue(9999)
    assert dlg.get_clamped_frame() == 1200


def test_goto_frame_dialog_single_enter_accepts(qtbot):
    dlg = GoToFrameDialog(start_frame=1001, end_frame=1200, current_frame=1001)
    qtbot.addWidget(dlg)
    dlg.show()

    dlg.spin_box.setValue(1150)
    # Press Enter
    enter_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    dlg.keyPressEvent(enter_ev)

    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.get_clamped_frame() == 1150


def test_goto_frame_dialog_escape_cancels(qtbot):
    dlg = GoToFrameDialog(start_frame=1001, end_frame=1200, current_frame=1001)
    qtbot.addWidget(dlg)
    dlg.show()

    dlg.spin_box.setValue(1150)
    # Press Escape
    esc_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    dlg.keyPressEvent(esc_ev)

    assert dlg.result() == QDialog.DialogCode.Rejected


def test_dialogs_exempt_from_shortcut_manager_interception(qtbot):
    sm = ShortcutManager.instance()
    dlg = GoToFrameDialog(start_frame=1001, end_frame=1200, current_frame=1001)
    qtbot.addWidget(dlg)

    spin = dlg.spin_box
    # ShortcutManager eventFilter must return False for widgets inside QDialog
    enter_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    handled = sm.eventFilter(spin, enter_ev)
    assert handled is False

    esc_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    handled_esc = sm.eventFilter(spin, esc_ev)
    assert handled_esc is False


def test_main_window_goto_frame_modal_on_fresh_app(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    # Verify freshly opened app state
    assert win.clock.current_frame == 1001
    assert win.isVisible()

    # Mock GoToFrameDialog.get_target_frame to simulate user typing 1125 and pressing Enter
    monkeypatch.setattr(
        GoToFrameDialog,
        "get_target_frame",
        lambda parent, start_f, end_f, curr_f: (1125, True),
    )

    win._on_goto_frame_modal()

    # Window remains open and visible, frame is updated
    assert win.isVisible()
    assert win.clock.current_frame == 1125
