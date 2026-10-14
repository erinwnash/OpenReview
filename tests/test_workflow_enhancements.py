"""
Tests for UI/UX and Workflow Enhancements:
- SMPTE Timecode conversions
- Pipeline Version Stepping (v001 -> v002)
- Playlist / Media Bin Model & HUD
- Recent Files persistence
- Safe Area Guides & In-Canvas Toasts
"""
import os
import tempfile
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from openreview.core.timecode import frame_to_timecode, timecode_to_frame
from openreview.core.version_control import (
    parse_version_token,
    find_sibling_versions,
    get_next_version,
    get_prev_version,
    get_version_summary,
)
from openreview.core.preferences import PreferencesManager
from openreview.widgets.viewport import ViewportCanvas
from openreview.models.annotations import AnnotationStore


def test_timecode_conversions():
    # 24 FPS
    assert frame_to_timecode(0, 24.0) == "00:00:00:00"
    assert frame_to_timecode(24, 24.0) == "00:00:01:00"
    assert frame_to_timecode(48, 24.0) == "00:00:02:00"
    assert frame_to_timecode(86400, 24.0) == "01:00:00:00"

    # Round trip
    tc = "01:23:45:12"
    f = timecode_to_frame(tc, 24.0)
    assert frame_to_timecode(f, 24.0) == tc

    # 30 FPS
    assert frame_to_timecode(30, 30.0) == "00:00:01:00"
    assert timecode_to_frame("00:00:01:00", 30.0) == 30


def test_version_parsing_and_stepping():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create versions: v001, v002, v003
        v1 = os.path.join(tmpdir, "shot010_comp_v001.mov")
        v2 = os.path.join(tmpdir, "shot010_comp_v002.mov")
        v3 = os.path.join(tmpdir, "shot010_comp_v003.mov")
        for p in (v1, v2, v3):
            with open(p, "w") as f:
                f.write("test")

        # Parse token
        token = parse_version_token("shot010_comp_v002.mov")
        assert token is not None
        prefix, marker, ver_num, padding, suffix = token
        assert prefix == "shot010_comp"
        assert marker.lower() == "_v"
        assert ver_num == 2
        assert padding == 3
        assert suffix == ".mov"

        # Find sibling versions
        siblings = find_sibling_versions(v2)
        assert len(siblings) == 3
        assert siblings[0][0] == 1
        assert siblings[1][0] == 2
        assert siblings[2][0] == 3

        # Step next
        assert get_next_version(v1) == v2
        assert get_next_version(v2) == v3
        assert get_next_version(v3) is None

        # Step prev
        assert get_prev_version(v3) == v2
        assert get_prev_version(v2) == v1
        assert get_prev_version(v1) is None

        # Version summary
        summary = get_version_summary(v2)
        assert "v002" in summary
        assert "2 of 3" in summary


def test_recent_files_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path
        pref = PreferencesManager(config_dir=Path(tmpdir))

        file1 = os.path.join(tmpdir, "recent1.mov")
        file2 = os.path.join(tmpdir, "recent2.mov")
        for p in (file1, file2):
            with open(p, "w") as f:
                f.write("f")

        pref.add_recent_file(file1)
        pref.add_recent_file(file2)

        recents = pref.get_recent_files()
        assert len(recents) == 2
        # MRU: file2 should be first
        assert recents[0] == os.path.normpath(file2)
        assert recents[1] == os.path.normpath(file1)

        pref.clear_recent_files()
        assert len(pref.get_recent_files()) == 0


def test_viewport_safe_guides_and_toast(qtbot):
    store = AnnotationStore()
    canvas = ViewportCanvas(store)
    qtbot.addWidget(canvas)

    assert canvas.show_safe_guides is False
    canvas.toggle_safe_guides()
    assert canvas.show_safe_guides is True
    assert canvas._toast_message is not None
    assert "Safe Area Guides: ON" in canvas._toast_message

    canvas.show_toast("Testing Toast Notification", duration_ms=500)
    assert canvas._toast_message == "Testing Toast Notification"
    canvas._hide_toast()
    assert canvas._toast_message is None


def test_spinbox_arrow_stylesheet_and_icons():
    from openreview.resources import get_spin_up_icon_path, get_spin_down_icon_path
    from openreview.ui.theme import get_spinbox_arrow_stylesheet, get_3dequalizer_stylesheet

    assert get_spin_up_icon_path(pressed=False).exists()
    assert get_spin_up_icon_path(pressed=True).exists()
    assert get_spin_down_icon_path(pressed=False).exists()
    assert get_spin_down_icon_path(pressed=True).exists()

    arrow_css = get_spinbox_arrow_stylesheet()
    assert "QSpinBox::up-arrow" in arrow_css
    assert "QSpinBox::down-arrow" in arrow_css
    assert "QDoubleSpinBox::up-arrow" in arrow_css
    assert "QDoubleSpinBox::down-arrow" in arrow_css
    assert "spin_up.svg" in arrow_css
    assert "spin_down.svg" in arrow_css

    full_css = get_3dequalizer_stylesheet()
    assert "QSpinBox::up-arrow" in full_css
    assert "QSpinBox::down-arrow" in full_css

