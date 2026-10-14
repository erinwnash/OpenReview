import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QTimer
from openreview.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_fullscreen_context_menu(qapp):
    win = MainWindow()
    win.show()
    QApplication.processEvents()

    vp = win.viewport

    # Test fullscreen entry
    win._on_toggle_fullscreen()
    QApplication.processEvents()
    assert win.isFullScreen()

    def close_menu_fullscreen():
        if hasattr(vp, "_last_context_menu") and vp._last_context_menu:
            menu = vp._last_context_menu
            action_texts = [a.text() for a in menu.actions()]
            assert "Exit Fullscreen (F12 / Esc)" in action_texts
            assert "Fit View (F)" in action_texts
            assert "Enter Presentation Mode (Tab)" in action_texts
            menu.close()

    QTimer.singleShot(0, close_menu_fullscreen)
    vp._show_context_menu(QPoint(200, 200))

    # Test Sources Panel context menu while in fullscreen mode
    sources_panel = win.sources_dock.panel
    def close_sources_menu():
        pop = QApplication.activePopupWidget()
        if pop:
            pop.close()

    QTimer.singleShot(0, close_sources_menu)
    sources_panel._on_tree_context_menu(QPoint(10, 10))

    # Test toggling back to normal
    win._on_toggle_fullscreen()
    QApplication.processEvents()
    assert not win.isFullScreen()

    def close_menu_normal():
        if hasattr(vp, "_last_context_menu") and vp._last_context_menu:
            menu = vp._last_context_menu
            action_texts = [a.text() for a in menu.actions()]
            assert "Fullscreen (F12)" in action_texts
            assert "Presentation Mode (Tab)" in action_texts
            menu.close()

    vp._last_context_menu_time = 0.0
    QTimer.singleShot(0, close_menu_normal)
    vp._show_context_menu(QPoint(200, 200))

    # Test entering fullscreen from maximized covers full screen height (including taskbar area)
    win.showMaximized()
    QApplication.processEvents()
    win._on_toggle_fullscreen()
    QApplication.processEvents()
    assert win.isFullScreen()
    screen = win.screen() or QApplication.primaryScreen()
    if screen:
        assert win.geometry().height() >= screen.geometry().height()
        assert win.geometry().width() >= screen.geometry().width()

    # Sources dock is visible in regular Fullscreen (F12)
    assert not win.sources_dock.isHidden()

    # Entering Presentation Mode (Tab) while in Fullscreen (F12) hides docks
    win._on_toggle_presentation_mode()
    QApplication.processEvents()
    assert win._in_presentation_mode
    assert win.isFullScreen()
    assert win.sources_dock.isHidden()
    assert win.file_browser_dock.isHidden()

    # Exiting Presentation Mode returns to Fullscreen (F12) and restores Sources dock
    win._on_toggle_presentation_mode()
    QApplication.processEvents()
    assert not win._in_presentation_mode
    assert win.isFullScreen()
    assert not win.sources_dock.isHidden()

    # Exiting Fullscreen returns to maximized state
    win._on_toggle_fullscreen()
    QApplication.processEvents()
    assert not win.isFullScreen()

    win.close()

