"""
Tests for Direct In-Canvas Text Annotation mode and Keyboard Shortcut Suppression.
Verifies that typing annotation letters does not trigger application shortcuts,
supports multi-line notes via Shift+Enter, commits on Enter, and properly restores
global shortcuts upon tool cancellation or exit.
"""
import pytest
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from openreview.models.annotations import AnnotationStore, ShapeType
from openreview.core.shortcuts import ShortcutManager
from openreview.widgets.viewport import ViewportCanvas
from openreview.widgets.markup_tools import MarkupToolPalette
from openreview.ui.main_window import MainWindow


@pytest.fixture
def test_setup(qtbot):
    app = QApplication.instance() or QApplication([])
    sm = ShortcutManager.instance()
    app.installEventFilter(sm)
    store = AnnotationStore()
    canvas = ViewportCanvas(annotation_store=store)
    palette = MarkupToolPalette(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.addWidget(canvas)

    palette.tool_changed.connect(canvas.set_draw_tool)
    canvas.draw_tool_changed.connect(palette.select_tool)
    sm.set_suppress_predicate(lambda: canvas.is_typing_active() or canvas.active_draw_tool == ShapeType.TEXT)

    fired_actions = []
    sm.bind_callback("annot.toggle_palette", lambda: fired_actions.append("x"))
    sm.bind_callback("annot.toggle_pen", lambda: fired_actions.append("d"))
    sm.bind_callback("playback.toggle_play_pause", lambda: fired_actions.append("space"))

    def on_escape():
        if canvas.is_typing_active():
            canvas.cancel_text_editor()
        elif canvas.active_draw_tool is not None:
            canvas.set_draw_tool(None)
            palette.select_tool(None)

    sm.bind_callback("app.escape", on_escape)

    yield canvas, palette, store, sm, fired_actions

    sm.set_suppress_predicate(None)
    app.removeEventFilter(sm)


def test_shortcut_suppression_when_text_tool_active(test_setup):
    canvas, palette, store, sm, fired = test_setup

    # 1. When no tool active, shortcuts fire normally
    ev_x = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier, "x")
    QApplication.instance().sendEvent(canvas, ev_x)
    assert "x" in fired
    fired.clear()

    # 2. Select Text Tool
    palette.select_tool(ShapeType.TEXT)
    assert canvas.active_draw_tool == ShapeType.TEXT
    assert sm.is_suppressed() is True

    # 3. Typing letters (e.g. 'x', 'd', 'space') does NOT fire shortcuts
    ev_d = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier, "d")
    QApplication.instance().sendEvent(canvas, ev_d)
    assert len(fired) == 0, "No application shortcuts should trigger while Text tool is active"
    assert canvas.is_typing_active() is True
    assert canvas._text_editor.toPlainText() == "d"


def test_direct_in_canvas_typing_and_commit(test_setup):
    canvas, palette, store, sm, fired = test_setup
    palette.select_tool(ShapeType.TEXT)

    # Type first character
    ev_h = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.NoModifier, "H")
    QApplication.instance().sendEvent(canvas, ev_h)
    assert canvas.is_typing_active() is True
    assert canvas._text_editor.toPlainText() == "H"

    # Type additional characters into the active editor
    ev_i = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.NoModifier, "i")
    QApplication.instance().sendEvent(canvas._text_editor.viewport(), ev_i)

    # Shift+Enter inserts newline
    ev_shift_enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier, "\r")
    QApplication.instance().sendEvent(canvas._text_editor, ev_shift_enter)

    # Type second line
    ev_v = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier, "V")
    QApplication.instance().sendEvent(canvas._text_editor.viewport(), ev_v)

    assert canvas._text_editor.toPlainText() == "Hi\nV"
    assert len(fired) == 0

    # Enter without shift commits note
    ev_enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r")
    QApplication.instance().sendEvent(canvas._text_editor, ev_enter)

    # Text editor is closed, note saved to annotation store
    assert canvas.is_typing_active() is False
    assert canvas.active_draw_tool == ShapeType.TEXT  # Tool persists for consecutive notes
    strokes = store.get_strokes(canvas.current_frame)
    assert len(strokes) == 1
    assert strokes[0].shape_type == ShapeType.TEXT
    assert strokes[0].text == "Hi\nV"


def test_escape_workflow(test_setup):
    canvas, palette, store, sm, fired = test_setup
    palette.select_tool(ShapeType.TEXT)

    # Start typing note
    ev_a = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "A")
    QApplication.instance().sendEvent(canvas, ev_a)
    assert canvas.is_typing_active() is True

    # Escape cancels the active typing session without saving
    ev_esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_esc)

    assert canvas.is_typing_active() is False
    assert len(store.get_strokes(canvas.current_frame)) == 0
    assert canvas.active_draw_tool == ShapeType.TEXT  # Tool still active

    # Escape again deselects the tool
    QApplication.instance().sendEvent(canvas, ev_esc)
    assert canvas.active_draw_tool is None
    assert sm.is_suppressed() is False

    # Shortcuts work again
    ev_x = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier, "x")
    QApplication.instance().sendEvent(canvas, ev_x)
    assert "x" in fired


def test_main_window_text_annotation_integration(qtbot):
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    qtbot.addWidget(win)

    # Select text tool
    win.markup_palette.select_tool(ShapeType.TEXT)
    assert win.viewport.active_draw_tool == ShapeType.TEXT

    # Direct typing via main window key press
    ev_t = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier, "x")
    win.keyPressEvent(ev_t)

    assert win.viewport.is_typing_active() is True
    assert win.viewport._text_editor.toPlainText() == "x"

    # Commit note with Enter
    ev_enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r")
    QApplication.instance().sendEvent(win.viewport._text_editor, ev_enter)

    assert win.viewport.is_typing_active() is False
    strokes = win.annotation_store.get_strokes(win.clock.current_frame)
    assert len(strokes) >= 1
    assert any(s.text == "x" for s in strokes)

    # Press Escape to deselect tool
    ev_esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(ev_esc)
    assert win.viewport.active_draw_tool is None
    win.close()


def test_canvas_click_and_drag_with_text_tool_does_not_create_ghost_layers(test_setup, qtbot):
    canvas, palette, store, sm, fired = test_setup
    palette.select_tool(ShapeType.TEXT)
    assert canvas.active_draw_tool == ShapeType.TEXT

    # 1. Click on canvas
    ev_press = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(150, 150), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_press)
    assert canvas.is_typing_active() is True

    # 2. Mouse move while holding mouse button should NOT create stroke points
    ev_move = QMouseEvent(QEvent.Type.MouseMove, QPoint(160, 160), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_move)
    assert len(canvas._current_stroke_points) == 0

    # 3. Mouse release should NOT add a dummy "Note" stroke
    ev_release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPoint(160, 160), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_release)
    assert len(store.get_strokes(canvas.current_frame)) == 0

    # 4. Clicking elsewhere on the canvas without typing should cancel empty editor and not create strokes
    ev_press2 = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(300, 300), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_press2)
    ev_release2 = QMouseEvent(QEvent.Type.MouseButtonRelease, QPoint(300, 300), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QApplication.instance().sendEvent(canvas, ev_release2)

    assert len(store.get_strokes(canvas.current_frame)) == 0
