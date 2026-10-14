import math
import pytest
import numpy as np
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QMouseEvent, QPainter, QImage

from openreview.models.comparison import ComparisonState, ComparisonMode
from openreview.widgets.hud_wipe import WipeComparisonHUD
from openreview.widgets.viewport import ViewportCanvas
from openreview.ui.main_window import MainWindow


def test_comparison_state_orientation_and_reset():
    state = ComparisonState()
    assert state.wipe_position == 0.5
    assert state.wipe_angle_deg == 0.0

    # Test flip orientation
    state.flip_orientation()
    assert state.wipe_angle_deg == 90.0

    state.flip_orientation()
    assert state.wipe_angle_deg == 0.0

    # Modify state and reset
    state.wipe_position = 0.8
    state.wipe_angle_deg = 135.0
    state.diff_boost = 3.5

    state.reset_wipe()
    assert state.wipe_position == 0.5
    assert state.wipe_angle_deg == 0.0
    assert state.diff_boost == 1.0


def test_hud_wipe_controls(qtbot):
    state = ComparisonState()
    hud = WipeComparisonHUD(state)
    qtbot.addWidget(hud)

    # Initial state
    assert hud.btn_vert.isChecked()
    assert not hud.btn_horiz.isChecked()
    assert hud.pos_slider.value() == 50
    assert hud.angle_slider.value() == 0

    # Click Horizontal button
    hud.btn_horiz.click()
    assert state.wipe_angle_deg == 90.0
    assert not hud.btn_vert.isChecked()
    assert hud.btn_horiz.isChecked()
    assert hud.angle_slider.value() == 90
    assert hud.angle_val_label.text() == "90°"

    # Click Vertical button
    hud.btn_vert.click()
    assert state.wipe_angle_deg == 0.0
    assert hud.btn_vert.isChecked()
    assert not hud.btn_horiz.isChecked()
    assert hud.angle_slider.value() == 0

    # Set custom angle slider
    hud.angle_slider.setValue(45)
    assert state.wipe_angle_deg == 45.0
    assert hud.angle_val_label.text() == "45°"
    assert not hud.btn_vert.isChecked()
    assert not hud.btn_horiz.isChecked()

    # Flip orientation
    hud.flip_orientation()
    assert state.wipe_angle_deg == 90.0
    assert hud.btn_horiz.isChecked()

    # Move position slider
    hud.pos_slider.setValue(75)
    assert state.wipe_position == 0.75
    assert hud.pos_val_label.text() == "75%"

    # Reset wipe
    hud.reset_wipe()
    assert state.wipe_position == 0.5
    assert state.wipe_angle_deg == 0.0
    assert state.diff_boost == 1.0
    assert hud.pos_slider.value() == 50
    assert hud.angle_slider.value() == 0
    assert hud.btn_vert.isChecked()


def test_viewport_wipe_geometry_and_rendering(qtbot):
    viewport = ViewportCanvas()
    qtbot.addWidget(viewport)
    viewport.resize(800, 600)
    viewport.show()

    viewport.comparison_state.mode = ComparisonMode.WIPE
    viewport.comparison_state.wipe_position = 0.5
    viewport.comparison_state.wipe_angle_deg = 0.0

    # Check vertical divider line geometry (0°)
    handle, rot, p1, p2, norm, tang = viewport._get_wipe_geometry()
    assert math.isclose(handle.x(), 400.0, abs_tol=10.0)
    assert math.isclose(handle.y(), 300.0, abs_tol=10.0)
    # Normal points along +X (horizontal motion)
    assert math.isclose(norm.x(), 1.0, abs_tol=1e-2)
    assert math.isclose(norm.y(), 0.0, abs_tol=1e-2)
    # Tangent points along +Y (vertical line)
    assert math.isclose(tang.x(), 0.0, abs_tol=1e-2)
    assert math.isclose(tang.y(), 1.0, abs_tol=1e-2)

    # Check horizontal divider line geometry (90°)
    viewport.comparison_state.wipe_angle_deg = 90.0
    handle_h, rot_h, p1_h, p2_h, norm_h, tang_h = viewport._get_wipe_geometry()
    # Normal points along +Y (vertical motion)
    assert math.isclose(norm_h.x(), 0.0, abs_tol=1e-2)
    assert math.isclose(norm_h.y(), 1.0, abs_tol=1e-2)
    # Tangent points along -X (horizontal line)
    assert math.isclose(tang_h.x(), -1.0, abs_tol=1e-2)
    assert math.isclose(tang_h.y(), 0.0, abs_tol=1e-2)

    # Render overlay to ensure no drawing exceptions
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    viewport._paint_wipe_overlay(painter)
    painter.end()


def test_viewport_mouse_wipe_interaction(qtbot):
    viewport = ViewportCanvas()
    qtbot.addWidget(viewport)
    viewport.resize(800, 600)
    viewport.show()

    viewport.comparison_state.mode = ComparisonMode.WIPE
    viewport.comparison_state.wipe_position = 0.5
    viewport.comparison_state.wipe_angle_deg = 0.0

    # 1. Dragging horizontally at angle 0° updates position
    viewport._update_wipe_from_mouse(600.0, 300.0)
    assert viewport.comparison_state.wipe_position > 0.65

    # 2. Switch to horizontal split (90°) and drag vertically
    viewport.comparison_state.wipe_angle_deg = 90.0
    viewport._update_wipe_from_mouse(400.0, 150.0)
    assert viewport.comparison_state.wipe_position < 0.35

    # 3. Rotation via _start_wipe_rotation and _update_wipe_rotation_from_mouse
    viewport._wipe_handle_center = QPointF(400.0, 300.0)
    viewport._start_wipe_rotation(400.0, 336.0) # 90 deg offset
    viewport._update_wipe_rotation_from_mouse(436.0, 300.0, snap=False) # dragged 90 deg clockwise
    assert viewport.comparison_state.wipe_angle_deg != 90.0

    # Test snap to 15 degrees
    viewport._wipe_start_wipe_angle = 0.0
    viewport._wipe_drag_start_angle = 0.0
    viewport._update_wipe_rotation_from_mouse(450.0, 310.0, snap=True)
    # Result must be a multiple of 15
    angle = viewport.comparison_state.wipe_angle_deg
    assert math.isclose(angle % 15.0, 0.0, abs_tol=1e-4) or math.isclose(angle % 15.0, 15.0, abs_tol=1e-4)

    # 4. Double click reset
    viewport.comparison_state.wipe_position = 0.9
    viewport.comparison_state.wipe_angle_deg = 180.0
    viewport._wipe_screen_normal = QPointF(1, 0)
    viewport._wipe_handle_center = QPointF(400, 300)
    viewport._wipe_rot_handle_center = QPointF(400, 336)

    dbl_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPointF(400.0, 300.0),
        QPointF(400.0, 300.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mouseDoubleClickEvent(dbl_event)
    assert viewport.comparison_state.wipe_position == 0.5
    assert viewport.comparison_state.wipe_angle_deg == 0.0


def test_main_window_wipe_shortcuts_and_sync(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()

    # Toggle wipe on
    window._on_toggle_wipe()
    assert window.comparison_state.mode == ComparisonMode.WIPE
    assert window.viewport.comparison_state.mode == ComparisonMode.WIPE

    # Flip orientation (Shift+W)
    assert window.comparison_state.wipe_angle_deg == 0.0
    window._on_flip_wipe_orientation()
    assert window.comparison_state.wipe_angle_deg == 90.0
    assert window.wipe_widget.angle_slider.value() == 90

    # Flip back
    window._on_flip_wipe_orientation()
    assert window.comparison_state.wipe_angle_deg == 0.0

    # Modify position and angle, then test reset (Alt+W)
    window.viewport.comparison_state.wipe_position = 0.82
    window.viewport.comparison_state.wipe_angle_deg = 45.0
    window._on_reset_wipe()
    assert window.comparison_state.wipe_position == 0.5
    assert window.comparison_state.wipe_angle_deg == 0.0
    assert window.wipe_widget.pos_slider.value() == 50
    assert window.wipe_widget.angle_slider.value() == 0


def test_shader_wipe_single_line_and_aspect_ratio_alignment():
    from openreview.color.shader_builder import FRAGMENT_SHADER_SOURCE

    # Verify shader no longer contains duplicate embedded gold line
    assert "vec4(0.898, 0.658, 0.137, 1.0)" not in FRAGMENT_SHADER_SOURCE
    assert "abs(proj - uWipePos) < edgeWidth" not in FRAGMENT_SHADER_SOURCE

    # Verify aspect ratio uniform is defined
    assert "uniform float uAspect;" in FRAGMENT_SHADER_SOURCE

    # Verify isotropic projection calculation in shader
    assert "float rMax = 0.5 * (aspect * abs(dir.x) + abs(dir.y));" in FRAGMENT_SHADER_SOURCE
    assert "float p = (TexCoord.x - 0.5) * aspect * dir.x + (TexCoord.y - 0.5) * dir.y;" in FRAGMENT_SHADER_SOURCE
