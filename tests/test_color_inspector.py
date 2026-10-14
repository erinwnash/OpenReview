"""
Tests for the Color Inspector HUD & Multi-Sampler Eyedropper system:
- Continuous pixel sampling under the widget (no Freeze toggle)
- Point/Aperture (1x1, 3x3, 5x5) and Rectangular Area (WxH) sampling
- Multiple pinned Eyedropper samplers (#1, #2, #3...)
- Live updates across frame changes
- Individual sampler removal (✕) and Clear All
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent, QPointF

from openreview.ui.main_window import MainWindow
from openreview.widgets.hud_color_inspector import ColorInspectorHUD


def test_color_inspector_no_freeze_and_continuous_sampling_under_widget(qtbot):
    """Verify Freeze button is removed and hovering over ColorInspectorHUD continues sampling under the widget."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.resize(1280, 720)
    win.show()

    # Load a known test image into viewport (100x100 float32 gradient)
    img = np.zeros((100, 100, 4), dtype=np.float32)
    for y in range(100):
        for x in range(100):
            img[y, x] = [x / 100.0, y / 100.0, 0.5, 1.0]
    win.viewport.set_primary_frame(1001, img)

    # Show Color Inspector HUD
    win._on_toggle_color_inspector()
    assert win.hud_inspector.isVisible()

    # Freeze button must no longer exist; Eyedropper & Clear All buttons must exist
    assert not hasattr(win.inspector_widget, "freeze_btn")
    assert hasattr(win.inspector_widget, "eyedropper_btn")
    assert hasattr(win.inspector_widget, "clear_samplers_btn")

    # Position HUD over viewport center and simulate mouse move directly on the HUD's child widget
    win.hud_inspector.move(200, 200)
    target_global = win.inspector_widget.mapToGlobal(QPoint(30, 30))
    win.hud_inspector._forward_sample_pos(target_global)

    expected_local = win.viewport.mapFromGlobal(target_global)
    expected_ix, expected_iy = win.viewport._screen_to_image_coords(expected_local.x(), expected_local.y())
    assert win.inspector_widget._current_x == expected_ix
    assert win.inspector_widget._current_y == expected_iy

    # Verify RGB & Luma color-coding in both ColorInspectorHUD and MainWindow status bar
    for col in ("#ff6b6b", "#69db7c", "#4dabf7"):
        assert col in win.inspector_widget.val_float.text()
        assert col in win.inspector_widget.val_8bit.text()
        assert col in win.inspector_widget.val_10bit.text()
        assert col in win.rgba_label.text()
        assert col in win.u8_label.text()
    assert "#ffd43b" in win.inspector_widget.val_luma.text()
    assert "#ffd43b" in win.luma_label.text()
    assert win.hud_inspector.width() >= win.inspector_widget.width() + 12

    win.close()


def test_multiple_eyedropper_samplers_point_area_and_removal(qtbot):
    """Test placing multiple point and rectangular area samplers, live frame updates, and removing/clearing them."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.resize(1280, 720)
    win.show()

    # Frame 1: solid red in top-left, solid green in bottom-right
    frame1 = np.zeros((100, 100, 4), dtype=np.float32)
    frame1[:50, :50] = [0.8, 0.1, 0.2, 1.0]
    frame1[50:, 50:] = [0.1, 0.9, 0.3, 1.0]
    win.viewport.set_primary_frame(1, frame1)

    # Show the Color Inspector HUD and record its compact initial height (0 samplers)
    win._on_toggle_color_inspector()
    assert win.hud_inspector.isVisible()
    compact_height = win.hud_inspector.height()

    # Enable Eyedropper mode via ColorInspectorHUD button
    win.inspector_widget.eyedropper_btn.setChecked(True)
    assert win.viewport.is_eyedropper_mode_active() is True

    # 1. Add Point Sampler #1 at pixel (20, 20) -> top-left red region
    s1 = win.viewport.add_color_sampler_at_pixel(20, 20)
    assert s1.sampler_id == 1
    assert abs(s1.r - 0.8) < 1e-4
    assert abs(s1.g - 0.1) < 1e-4
    assert abs(s1.b - 0.2) < 1e-4

    # 2. Add Rectangular Area Sampler #2 covering (40, 40) of size 20x20 (straddling both regions)
    s2 = win.viewport.add_color_sampler_at_pixel(40, 40, w=20, h=20)
    assert s2.sampler_id == 2
    assert s2.w == 20 and s2.h == 20

    # 3. Add Point Sampler #3 at pixel (75, 75) -> bottom-right green region
    s3 = win.viewport.add_color_sampler_at_pixel(75, 75)
    assert s3.sampler_id == 3
    assert abs(s3.r - 0.1) < 1e-4
    assert abs(s3.g - 0.9) < 1e-4

    # Inspector UI must have 3 sampler rows, Clear All enabled, and expanded height
    assert len(win.inspector_widget._sampler_rows) == 3
    assert win.inspector_widget.clear_samplers_btn.isEnabled() is True
    assert "Pinned Samplers (3/3)" in win.inspector_widget.samplers_hdr_label.text()
    expanded_height = win.hud_inspector.height()
    assert expanded_height > compact_height

    # 3b. Adding a 4th sampler enforces the 3-sampler limit via FIFO (replaces oldest #1, keeps IDs #1-#3)
    s4 = win.viewport.add_color_sampler_at_pixel(80, 80)
    assert s4.sampler_id == 1
    assert len(win.viewport.get_color_samplers()) == 3
    assert [s.sampler_id for s in win.viewport.get_color_samplers()] == [2, 3, 1]
    assert win.inspector_widget.get_active_analyzer_sampler_id() == 1

    # 4. Advance to Frame 2 with inverted colors -> all pinned samplers must live-update automatically
    frame2 = np.zeros((100, 100, 4), dtype=np.float32)
    frame2[:, :] = [0.25, 0.5, 0.75, 1.0]
    win.viewport.set_primary_frame(2, frame2)

    assert abs(win.viewport.get_color_samplers()[0].r - 0.25) < 1e-4
    assert abs(win.viewport.get_color_samplers()[0].g - 0.50) < 1e-4
    assert abs(win.viewport.get_color_samplers()[0].b - 0.75) < 1e-4
    assert "0.2500" in win.inspector_widget._sampler_rows[1].float_lbl.text()

    # 5. Remove Sampler #2 individually via its row remove button
    win.inspector_widget._sampler_rows[2].remove_btn.click()
    remaining_ids = [s.sampler_id for s in win.viewport.get_color_samplers()]
    assert remaining_ids == [3, 1]
    assert set(win.inspector_widget._sampler_rows.keys()) == {1, 3}
    assert "Pinned Samplers (2/3)" in win.inspector_widget.samplers_hdr_label.text()

    # 6. Clear all remaining samplers via Clear All button (even when edge-snapped/docked) -> widget shrinks to compact auto height
    win.hud_inspector.dock_to_left()
    win.inspector_widget.clear_samplers_btn.click()
    assert len(win.viewport.get_color_samplers()) == 0
    assert len(win.inspector_widget._sampler_rows) == 0
    assert win.inspector_widget.clear_samplers_btn.isEnabled() is False
    assert "Pinned Samplers (0/3)" in win.inspector_widget.samplers_hdr_label.text()
    assert win.inspector_widget.analyzer_container.isVisible() is False
    assert win.hud_inspector.height() <= compact_height + 4

    win.close()


def test_pixel_analyzer_min_max_avg_median_swatches_and_nan_inf_neg_checks(qtbot):
    """Verify Pixel Analyzer calculates Min/Max/Avg/Median, updates swatch thumbnails, and detects NaN/Inf/Negative pixels."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.resize(1280, 720)
    win.show()

    # Construct a 10x10 float32 test frame with controlled values inside a 4x4 region at (2, 2):
    # Most finite pixels have known R values: [0.1, 0.2, 0.4, 0.9]
    # Plus specific anomalous pixels: NaN, +Inf, and Negative (-0.25)
    frame = np.full((10, 10, 4), 0.5, dtype=np.float32)
    region = np.zeros((4, 4, 4), dtype=np.float32)
    region[:, :] = [0.2, 0.4, 0.6, 1.0]
    region[0, 0] = [0.1, 0.2, 0.3, 1.0]          # finite min
    region[0, 1] = [0.8, 0.9, 1.0, 1.0]          # finite max
    region[1, 0] = [-0.25, 0.4, 0.6, 1.0]        # Negative value (< 0.0) -> also the finite min for R!
    region[2, 0] = [np.nan, 0.4, 0.6, 1.0]       # NaN pixel
    region[3, 0] = [np.inf, 0.4, 0.6, 1.0]       # +Inf pixel
    frame[2:6, 2:6] = region
    win.viewport.set_primary_frame(1, frame)

    # Add rectangular area sampler covering (2, 2) of size 4x4
    sampler = win.viewport.add_color_sampler_at_pixel(2, 2, w=4, h=4)

    # 1. Verify NaN, Inf, and Negative pixel counts
    assert sampler.nan_count == 1
    assert sampler.inf_count == 1
    assert sampler.neg_count == 1
    assert len(sampler.nan_coords) == 1 and sampler.nan_coords[0] == (2, 4)
    assert len(sampler.inf_coords) == 1 and sampler.inf_coords[0] == (2, 5)
    assert len(sampler.neg_coords) == 1 and sampler.neg_coords[0] == (2, 3)

    # 2. Verify finite-safe Min, Max, Average, and Median on R, G, B
    # Finite R values in the 16-pixel 4x4 block:
    # Twelve pixels of 0.2, one of 0.1, one of 0.8, one of -0.25 (total 15 finite R values; 1 NaN, 1 Inf -> wait: 16 - 2 = 14 finite R values)
    assert abs(sampler.min_rgba[0] - (-0.25)) < 1e-4
    assert abs(sampler.min_rgba[1] - 0.20) < 1e-4
    assert abs(sampler.min_rgba[2] - 0.30) < 1e-4

    assert abs(sampler.max_rgba[0] - 0.80) < 1e-4
    assert abs(sampler.max_rgba[1] - 0.90) < 1e-4
    assert abs(sampler.max_rgba[2] - 1.00) < 1e-4

    # Median of 14 finite R values (eleven 0.2s, one -0.25, one 0.1, one 0.8) is 0.2
    assert abs(sampler.med_rgba[0] - 0.20) < 1e-4
    assert abs(sampler.med_rgba[1] - 0.40) < 1e-4
    assert abs(sampler.med_rgba[2] - 0.60) < 1e-4

    # 3. Verify ColorInspectorHUD Pixel Analyzer UI updated automatically for Sampler #1
    hud = win.inspector_widget
    assert hud.get_active_analyzer_sampler_id() == sampler.sampler_id
    assert "-0.2500" in hud.stat_min_lbl.text()
    assert "0.8000" in hud.stat_max_lbl.text()
    assert "0.2000" in hud.stat_med_lbl.text()

    # Verify the 4 swatch thumbnails store the expected RGB values
    assert abs(hud.swatch_min.rgba[0] - (-0.25)) < 1e-4
    assert abs(hud.swatch_max.rgba[0] - 0.80) < 1e-4
    assert abs(hud.swatch_med.rgba[0] - 0.20) < 1e-4
    assert abs(hud.swatch_avg.rgba[0] - sampler.avg_rgba[0]) < 1e-4

    # Verify NaN / Inf / Negative check buttons show counts and toggle viewport overlay flags
    assert "NaN: 1" in hud.chk_nan_btn.text()
    assert "Inf: 1" in hud.chk_inf_btn.text()
    assert "Neg (<0): 1" in hud.chk_neg_btn.text()

    assert win.viewport.highlight_nan_pixels is True
    hud.chk_nan_btn.click()
    assert win.viewport.highlight_nan_pixels is False

    # 4. Verify Eyedropper automatically toggles OFF after the user draws a selection on the viewport
    hud.eyedropper_btn.setChecked(True)
    assert win.viewport.is_eyedropper_mode_active() is True
    assert hud.eyedropper_btn.isChecked() is True

    p_start = win.viewport._image_norm_to_screen(0.2, 0.2)
    p_end = win.viewport._image_norm_to_screen(0.6, 0.6)
    press_ev = QMouseEvent(
        QEvent.Type.MouseButtonPress, p_start, win.viewport.mapToGlobal(p_start.toPoint()),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    move_ev = QMouseEvent(
        QEvent.Type.MouseMove, p_end, win.viewport.mapToGlobal(p_end.toPoint()),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    rel_ev = QMouseEvent(
        QEvent.Type.MouseButtonRelease, p_end, win.viewport.mapToGlobal(p_end.toPoint()),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
    )
    win.viewport.mousePressEvent(press_ev)
    win.viewport.mouseMoveEvent(move_ev)
    win.viewport.mouseReleaseEvent(rel_ev)

    assert win.viewport.is_eyedropper_mode_active() is False
    assert hud.eyedropper_btn.isChecked() is False
    assert len(win.viewport.get_color_samplers()) == 2

    win.close()

