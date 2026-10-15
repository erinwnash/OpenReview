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


def test_icon_resolutions_integrity():
    from PIL import Image
    ico_path = ICONS_DIR / "openreview.ico"
    assert ico_path.exists()
    ico = Image.open(ico_path)
    required_sizes = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
    assert required_sizes.issubset(ico.info.get("sizes", set()))
    # Ensure standard desktop resolution 48x48 is accessible and valid RGBA
    img48 = ico.ico.getimage((48, 48))
    assert img48.size == (48, 48)
    assert img48.mode == "RGBA"

