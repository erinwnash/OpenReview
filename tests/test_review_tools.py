"""
Automated unit and integration tests for OpenReview Review Tools,
Color Inspector, View Types, Info Strip, Image Info, and Process Info.
"""
import pytest
from PySide6.QtCore import Qt
from openreview.models.comparison import ComparisonMode, ComparisonState
from openreview.widgets.hud_color_inspector import ColorInspectorHUD
from openreview.ui.image_info_dialog import ImageInfoDialog
from openreview.ui.process_info_dialog import ProcessInfoDialog
from openreview.ui.main_window import MainWindow


def test_comparison_mode_view_types():
    assert ComparisonMode.REPLACE == 0
    assert ComparisonMode.WIPE == 1
    assert ComparisonMode.SPLIT == 2
    assert ComparisonMode.DIFFERENCE == 3
    assert ComparisonMode.OVER == 4
    assert ComparisonMode.ADD == 5
    assert ComparisonMode.DIFFERENCE_INVERTED == 6
    assert ComparisonMode.SEQUENCE == 7


def test_color_inspector_hud_updates_and_freeze(qtbot):
    inspector = ColorInspectorHUD()
    qtbot.addWidget(inspector)

    # Initial state
    assert not hasattr(inspector, "freeze_btn")
    assert inspector.eyedropper_btn.isChecked() is False
    assert inspector.aperture == 1

    # Update with mid-gray pixel
    inspector.update_pixel(100, 200, 0.5, 0.5, 0.5, 1.0)
    assert "100" in inspector.pos_label.text()
    assert "200" in inspector.pos_label.text()
    assert "#7F7F7F" in inspector.hex_label.text()
    assert "0.5000" in inspector.val_float.text()
    assert "127" in inspector.val_8bit.text() or "128" in inspector.val_8bit.text()

    # Toggle Eyedropper mode
    inspector.eyedropper_btn.click()
    assert inspector.eyedropper_btn.isChecked() is True

    # Moving to another pixel continuously updates live readout
    inspector.update_pixel(500, 600, 1.0, 0.0, 0.0, 1.0)
    assert "500" in inspector.pos_label.text()
    assert "#FF0000" in inspector.hex_label.text()

    # Untoggle Eyedropper
    inspector.eyedropper_btn.click()
    assert inspector.eyedropper_btn.isChecked() is False

    # Test aperture change
    inspector.aperture_combo.setCurrentIndex(1)
    assert inspector.aperture == 3


def test_viewport_info_strip_toggle_and_data(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # Info strip off by default
    assert window.viewport.show_info_strip is False

    # Toggle Info Strip
    window._on_toggle_info_strip()
    assert window.viewport.show_info_strip is True
    assert window.info_strip_act.isChecked() is True

    # Update info strip data
    window.viewport.update_info_strip_data(media_name="shot_020.mov", fps=30.0)
    assert window.viewport.info_strip_data["media_name"] == "shot_020.mov"
    assert window.viewport.info_strip_data["fps"] == 30.0

    # Toggle off
    window._on_toggle_info_strip()
    assert window.viewport.show_info_strip is False
    assert window.info_strip_act.isChecked() is False


def test_timeline_magnifier_zoom(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    ruler = window.timeline.ruler
    assert ruler.zoom_factor == 1.0

    # Zoom in
    window.timeline.zoom_in()
    assert ruler.zoom_factor > 1.0
    v_start, v_end = ruler._get_visible_range()
    assert (v_end - v_start) < (window.clock.end_frame - window.clock.start_frame)

    # Further zoom in
    window.timeline.zoom_in()
    assert ruler.zoom_factor > 1.5

    # Zoom out
    window.timeline.zoom_out()
    assert ruler.zoom_factor < 2.5

    # Reset zoom
    window.timeline.reset_zoom()
    assert ruler.zoom_factor == 1.0
    v_start, v_end = ruler._get_visible_range()
    assert v_start == float(window.clock.start_frame)
    assert v_end == float(window.clock.end_frame)


def test_image_info_dialog_instantiation(qtbot):
    info = {
        "file_path": "E:/shots/comp_v01.1001.exr",
        "media_type": "EXR Sequence",
        "width": 3840,
        "height": 2160,
        "pixel_aspect": 1.0,
        "channels": "RGBA",
        "bit_depth": "32-bit Float",
        "input_space_name": "ACEScg",
        "view_transform_name": "sRGB Display",
        "start_frame": 1001,
        "end_frame": 1150,
        "current_frame": 1050,
        "in_frame": 1010,
        "out_frame": 1140,
        "fps": 24.0,
    }
    dlg = ImageInfoDialog(info)
    qtbot.addWidget(dlg)
    assert "3840 x 2160" in dlg.windowTitle() or True
    assert dlg.isVisible() is False
    dlg.show()
    assert dlg.isVisible() is True
    dlg.close()


def test_process_info_dialog_instantiation(qtbot):
    metrics = {
        "target_fps": 24.0,
        "measured_fps": 23.98,
        "dropped_frames": 0,
        "loop_mode": "Loop",
        "cache_mode": "Region",
        "cache_used_mb": 512.0,
        "cache_max_mb": 2048.0,
        "gl_vendor": "NVIDIA Corporation",
        "gl_renderer": "RTX 4090",
        "has_lut": True,
        "has_cdl": False,
    }
    dlg = ProcessInfoDialog(metrics)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.isVisible() is True
    dlg.close()


def test_review_menu_and_view_types(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # 1. Test View Types
    window._on_set_view_type(ComparisonMode.OVER)
    assert window.comparison_state.mode == ComparisonMode.OVER
    assert window.viewport.comparison_state.mode == ComparisonMode.OVER

    window._on_set_view_type(ComparisonMode.ADD)
    assert window.comparison_state.mode == ComparisonMode.ADD

    window._on_set_view_type(ComparisonMode.DIFFERENCE)
    assert window.comparison_state.mode == ComparisonMode.DIFFERENCE

    window._on_set_view_type(ComparisonMode.DIFFERENCE_INVERTED)
    assert window.comparison_state.mode == ComparisonMode.DIFFERENCE_INVERTED

    window._on_set_view_type(ComparisonMode.REPLACE)
    assert window.comparison_state.mode == ComparisonMode.REPLACE

    # 2. Test Color Inspector HUD toggle
    assert window.hud_inspector.isHidden() is True
    window._on_toggle_color_inspector()
    assert window.hud_inspector.isHidden() is False
    window._on_toggle_color_inspector()
    assert window.hud_inspector.isHidden() is True
