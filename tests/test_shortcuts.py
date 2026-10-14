"""
Unit tests for the centralized ShortcutManager.
"""
import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from openreview.core.shortcuts import ShortcutManager, ShortcutAction
from openreview.core.preferences import PreferencesManager


@pytest.fixture(autouse=True)
def setup_shortcuts():
    ShortcutManager.reset_instance()
    PreferencesManager.reset_instance()
    yield
    ShortcutManager.reset_instance()
    PreferencesManager.reset_instance()


def test_shortcut_defaults():
    mgr = ShortcutManager.instance()
    actions = mgr.get_actions()
    assert len(actions) > 30

    space_act = mgr.get_action("playback.toggle")
    assert space_act is not None
    assert space_act.default_shortcut == "Space"
    assert space_act.effective_shortcut == "Space"
    assert not space_act.is_customized()


def test_set_and_reset_shortcut():
    mgr = ShortcutManager.instance()
    mgr.set_shortcut("playback.toggle", "P")
    act = mgr.get_action("playback.toggle")
    assert act.effective_shortcut == "P"
    assert act.is_customized()

    mgr.reset_to_default("playback.toggle")
    assert act.effective_shortcut == "Space"
    assert not act.is_customized()


def test_find_conflict():
    mgr = ShortcutManager.instance()
    # "Space" is assigned to playback.toggle
    conflict = mgr.find_conflict("Space")
    assert conflict is not None
    assert conflict.action_id == "playback.toggle"

    # Excluding itself should return None
    no_conflict = mgr.find_conflict("Space", exclude_action_id="playback.toggle")
    assert no_conflict is None

    # Unassigned key combo
    assert mgr.find_conflict("Ctrl+Alt+Shift+Z") is None


def test_callback_execution():
    mgr = ShortcutManager.instance()
    executed = []
    mgr.bind_callback("playback.toggle", lambda: executed.append("play"))

    assert mgr.trigger("playback.toggle") is True
    assert executed == ["play"]


def test_event_filter_dispatch(qapp):
    mgr = ShortcutManager.instance()
    triggered = []
    mgr.bind_callback("playback.toggle", lambda: triggered.append(True))

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        " ",
    )
    handled = mgr.eventFilter(None, event)
    assert handled is True
    assert triggered == [True]


def test_event_filter_ignores_text_inputs(qapp):
    mgr = ShortcutManager.instance()
    triggered = []
    mgr.bind_callback("playback.step_fwd", lambda: triggered.append(True))

    line_edit = QLineEdit()
    # Plain text typing inside QLineEdit should not trigger review shortcuts
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.NoModifier,
        "a",
    )
    handled = mgr.eventFilter(line_edit, event)
    assert handled is False
    assert len(triggered) == 0


def test_invert_and_close_session_shortcuts(qapp):
    mgr = ShortcutManager.instance()

    inv_act = mgr.get_action("color.invert_toggle")
    assert inv_act is not None
    assert inv_act.default_shortcut == "Shift+I"

    close_act = mgr.get_action("session.close")
    assert close_act is not None
    assert close_act.default_shortcut == "Ctrl+Shift+N"

    triggered = []
    mgr.bind_callback("color.invert_toggle", lambda: triggered.append("invert"))
    mgr.bind_callback("session.close", lambda: triggered.append("close"))

    ev_invert = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_I,
        Qt.KeyboardModifier.ShiftModifier,
        "I",
    )
    assert mgr.eventFilter(None, ev_invert) is True

    ev_close = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_N,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        "N",
    )
    assert mgr.eventFilter(None, ev_close) is True
    assert triggered == ["invert", "close"]

