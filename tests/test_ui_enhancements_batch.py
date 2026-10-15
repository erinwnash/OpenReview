"""
Tests for UI and Core enhancements:
- Freehand pen smoothing & draft rendering
- Slider transparent backgrounds
- About window and App minimal SVG icons & favicons
- Window menu categories and alphabetical ordering
- Timeline transport frame count label
- Screenspace color transforms on export
"""
import pytest
import numpy as np
from pathlib import Path
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QLabel

from openreview.ui.main_window import MainWindow
from openreview.widgets.viewport import ViewportCanvas
from openreview.widgets.markup_tools import MarkupToolPalette
from openreview.models.annotations import ShapeType, Stroke
from openreview.resources import (
    get_app_icon_path,
    get_app_logo_path,
    get_favicon_path,
    get_app_icon,
)
from openreview.core.exporter import MediaExporter


def test_freehand_pen_smoothing():
    """Verify Chaikin smoothing algorithm creates smooth natural curves."""
    raw_points = [(0.1, 0.1), (0.2, 0.4), (0.5, 0.8), (0.9, 0.9)]
    smoothed = ViewportCanvas._smooth_points_chaikin(raw_points, iterations=2)
    # Check that number of points increased
    assert len(smoothed) > len(raw_points)
    # Check that endpoints are preserved
    assert abs(smoothed[0][0] - raw_points[0][0]) < 1e-5
    assert abs(smoothed[0][1] - raw_points[0][1]) < 1e-5
    assert abs(smoothed[-1][0] - raw_points[-1][0]) < 1e-5
    assert abs(smoothed[-1][1] - raw_points[-1][1]) < 1e-5


def test_markup_sliders_transparent_background(qtbot):
    """Verify brush size and opacity sliders have transparent backgrounds."""
    palette = MarkupToolPalette()
    qtbot.addWidget(palette)

    # Check palette stylesheet contains transparent rule for QSlider
    sheet = palette.styleSheet()
    assert "QFrame#MarkupToolPalette > QSlider" in sheet
    assert "transparent" in sheet


def test_minimal_vector_icons_and_logo():
    """Verify primary and horizontal vector SVGs are resolved for app icon, logo, and favicon."""
    icon_p = get_app_icon_path()
    logo_p = get_app_logo_path()
    fav_p = get_favicon_path()

    assert icon_p.name == "openreview-primary-logo.svg"
    assert logo_p.name == "openreview-logo-horizontal.svg"
    assert fav_p.name == "openreview-primary-logo.svg"

    app_icon = get_app_icon()
    assert not app_icon.isNull()
    assert len(app_icon.availableSizes()) > 0
    # Check multi-res pixmaps rendered
    pix_16 = app_icon.pixmap(16, 16)
    pix_64 = app_icon.pixmap(64, 64)
    pix_256 = app_icon.pixmap(256, 256)
    assert not pix_16.isNull()
    assert not pix_64.isNull()
    assert not pix_256.isNull()


def test_window_menu_categories_and_ascending_order(qtbot):
    """Verify Window menu is organized by category sections with actions in ascending order."""
    window = MainWindow()
    qtbot.addWidget(window)

    menu_bar = window.menuBar()
    win_menu = None
    for action in menu_bar.actions():
        if "Window" in action.text():
            win_menu = action.menu()
            break
    assert win_menu is not None

    actions = win_menu.actions()
    # Group actions by section
    sections = {}
    current_sec = "TOP"
    sections[current_sec] = []

    for a in actions:
        if a.isSeparator() and a.text():
            current_sec = a.text()
            sections[current_sec] = []
        elif not a.isSeparator():
            sections[current_sec].append(a.text())

    # Assert Interactive Color Adjustments is not in Window menu
    assert not any("Interactive Color Adjustments" in a.text() for a in actions)

    # Check expected categories exist
    expected_categories = [
        "Panels & Navigation",
        "Panel Layout & Docking",
        "Toolbars",
        "System & Display",
    ]
    for cat in expected_categories:
        assert cat in sections, f"Category '{cat}' missing from Window menu"
        # Check alphabetical sorting
        items = sections[cat]
        assert len(items) > 0
        sorted_items = sorted(items, key=lambda s: s.lower())
        assert items == sorted_items, f"Items in '{cat}' not in ascending order: {items}"


def test_timeline_frame_count_label(qtbot):
    """Verify frame count label updates dynamically for total and selected in/out range."""
    window = MainWindow()
    qtbot.addWidget(window)

    tl = window.timeline
    assert hasattr(tl, "lbl_frame_count")

    # Initial state: 1001 to 1200 (200 frames total, unconstrained)
    assert tl.lbl_frame_count.text() == "200 frames"

    # Set In/Out range to 1010-1059 (50 frames selected)
    window.clock.set_in_out(1010, 1059)
    assert tl.lbl_frame_count.text() == "50 / 200 frames"

    # Clear In/Out range
    window.clock.clear_in_out()
    assert tl.lbl_frame_count.text() == "200 frames"


def test_screenspace_color_transforms_on_export():
    """Verify linear float EXR frames are not dark when exported with sRGB display transform."""
    # Linear middle grey frame (0.18)
    linear_img = np.full((100, 100, 3), 0.18, dtype=np.float32)

    class MockViewport:
        input_space = 1      # ACEScg / Scene Linear
        view_transform = 0   # sRGB Display View
        exposure_ev = 0.0
        gain = 1.0
        saturation = 1.0
        gamma = 1.0
        color_grading = None

    vp = MockViewport()
    result = MediaExporter.apply_screenspace_color_transforms(linear_img, vp)

    assert result.dtype == np.uint8
    assert result.shape == (100, 100, 3)

    # In sRGB transfer function, linear 0.18 maps to approximately 117-120 in 8-bit.
    # Without color management (raw linear * 255), it would be 45 (far too dark).
    assert 110 <= result[0, 0, 0] <= 125, f"Expected ~118, got {result[0, 0, 0]}"


def test_layered_input_menu_dynamic_visibility(qtbot):
    """Verify Layered input menu dynamically becomes visible when EXR or Stereo media is present."""
    from openreview.models.session_graph import SourceItem
    from openreview.core.stereo import StereoPair

    window = MainWindow()
    qtbot.addWidget(window)

    menu_action = window.layered_input_menu.menuAction()
    # Initially hidden
    assert not menu_action.isVisible()

    # Add a multilayer EXR to session graph
    src = SourceItem(name="shot_comp", path="C:/vfx/shot_comp.exr")
    window.session_graph.add_source(src)
    assert menu_action.isVisible()
    assert window.act_exr_pass_inspector.isEnabled()
    assert not window.act_stereo_controls.isEnabled()

    # Add a stereo pair to window
    window._current_stereo_pair = StereoPair(left_path="C:/vfx/left.png", right_path="C:/vfx/right.png")
    window._update_layered_input_menu_visibility()
    assert menu_action.isVisible()
    assert window.act_stereo_controls.isEnabled()

    # Clear session
    window._on_close_session(prompt=False)
    assert not menu_action.isVisible()

