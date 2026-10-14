"""
Tests for Application Icon and Favicon Resources.
"""
from pathlib import Path
from PySide6.QtGui import QIcon

from openreview.resources import get_app_icon, get_app_icon_path, get_favicon_path, ICONS_DIR
from openreview.ui.main_window import MainWindow


def test_icon_files_exist():
    assert get_app_icon_path().exists()
    assert get_favicon_path().exists()
    assert (ICONS_DIR / "openreview.ico").exists()
    assert (ICONS_DIR / "openreview.png").exists()
    assert (ICONS_DIR / "favicon.ico").exists()
    assert (ICONS_DIR / "favicon.png").exists()
    assert (ICONS_DIR / "favicon-32x32.png").exists()
    assert (ICONS_DIR / "favicon-16x16.png").exists()


def test_app_and_window_icon_loaded(qtbot):
    icon = get_app_icon()
    assert not icon.isNull()
    sizes = icon.availableSizes()
    assert len(sizes) > 0

    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.windowIcon().isNull()
