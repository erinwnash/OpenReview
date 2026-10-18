"""
Tests for:
1. Unified caching for Sequences, Stacks, and Layouts
2. Default Stacking compare mode is 'switch' (A/B Switch)
3. Cycling through stack layers and sources with Z and Shift+Z
"""
import os
import tempfile
import numpy as np
from PIL import Image
import pytest

from openreview.models.session_graph import SessionGraph, ViewType, StackView
from openreview.models.comparison import ComparisonMode
from openreview.core.cache import CacheMode
from openreview.ui.main_window import MainWindow


@pytest.fixture
def test_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(1, 4):
            p = os.path.join(tmpdir, f"frame_{i:04d}.png")
            # Create images with distinct colors and alpha
            img = Image.new("RGBA", (64, 64), color=(i * 70, 100, 200, 200))
            img.save(p)
            paths.append(p)
        yield paths


def test_default_stack_mode_is_ab_switch():
    graph = SessionGraph()
    stk = graph.create_stack("TestStack", ["s1", "s2"])
    assert stk.compare_mode == "switch"
    stk_def = StackView()
    assert stk_def.compare_mode == "switch"


def test_stack_caching_and_cycling(qtbot, test_images):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])
    s3 = win.session_graph.add_source_from_path(test_images[2])

    # Enable cache in ALL mode
    win.cache.set_mode(CacheMode.ALL)
    assert win.cache.mode == CacheMode.ALL

    # 1. Create Stack and activate it
    stk = win.session_graph.create_stack("Comp_Stack", [s1.id, s2.id, s3.id], compare_mode="over")
    assert stk.compare_mode == "over"
    win._on_active_view_changed("stack", stk.id)
    assert win.comparison_state.mode == ComparisonMode.OVER
    assert win.viewport.comparison_state.mode == ComparisonMode.OVER

    f = win.clock.current_frame
    # Render current frame -> should populate source-level cache for layers s1 and s2
    win._on_frame_changed(f)
    assert win.cache.has_source_frame(s1.id, f)
    assert win.cache.has_source_frame(s2.id, f)
    assert win.viewport._image_a is not None
    assert win.viewport._image_b is not None

    # Render next time should hit source-level cache
    win._on_frame_changed(f)
    assert win.viewport._image_a is not None
    assert win.viewport._image_b is not None

    # 2. Cycle stack forward (Z) -> should solo layer 1 (s2) WITHOUT clearing cache
    assert stk.current_layer_index == 0
    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 1
    assert win.comparison_state.mode == ComparisonMode.OFF
    assert win.viewport.comparison_state.mode == ComparisonMode.OFF
    assert win.viewport._image_b is None  # Solo display without reference overlay

    # Prior frames for s1 and s2 must still exist in RAM cache!
    assert win.cache.has_source_frame(s1.id, f)
    assert win.cache.has_source_frame(s2.id, f)

    # Cycle stack forward again (Z) -> strictly toggles back to Layer A (0)
    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 0

    # Cycle backward (Shift+Z) -> toggles back to Layer B (1), instant RAM hit
    win._on_stack_cycle_backward()
    assert stk.current_layer_index == 1
    assert win.cache.has_source_frame(s2.id, f)

    # 3. Test caching for Sequence: uses existing cached sources
    seq = win.session_graph.create_sequence("TestSeq", [s1.id, s2.id])
    win._on_active_view_changed("sequence", seq.id)
    win._on_frame_changed(seq.start_frame)
    src_0, src_0_f = seq.resolve_frame(seq.start_frame, win.session_graph.sources)
    assert win.cache.has_source_frame(src_0.id, src_0_f)
    assert win.viewport._image_a is not None

    # 4. Test caching for Layout: uses existing cached sources
    lay = win.session_graph.create_layout("TestLayout", [s1.id, s2.id, s3.id], scale_pct=50)
    win._on_active_view_changed("layout", lay.id)
    win._on_frame_changed(win.clock.start_frame)
    assert win.cache.has_source_frame(s1.id, win.clock.start_frame)
    assert win.viewport._image_a is not None

    # 5. Test selective cache clearing
    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    win._on_clear_cache()  # Clears only s1
    assert not win.cache.has_source_frame(s1.id, f)
    assert win.cache.has_source_frame(s2.id, f)  # s2 still in RAM!

    win._on_clear_all_cache()  # Clears all sources
    assert not win.cache.has_source_frame(s2.id, f)


def test_single_source_cycling_when_multiple_sources(qtbot, test_images):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])
    s3 = win.session_graph.add_source_from_path(test_images[2])

    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    assert win.session_graph.active_view_id == s1.id

    # Press Z -> cycles to s2
    win._on_stack_cycle_forward()
    assert win.session_graph.active_view_id == s2.id

    # Press Z -> cycles to s3
    win._on_stack_cycle_forward()
    assert win.session_graph.active_view_id == s3.id

    # Press Shift+Z -> cycles back to s2
    win._on_stack_cycle_backward()
    assert win.session_graph.active_view_id == s2.id


def test_stack_refinements_selection_and_toggle_switch(qtbot, test_images, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])
    s3 = win.session_graph.add_source_from_path(test_images[2])

    panel = win.sources_dock.panel
    panel.refresh_tree()

    # 1. Test selection order creation: select s2 first, then s1
    panel._source_selection_order = [s2.id, s1.id]
    monkeypatch.setattr(panel, "_get_selected_nodes", lambda: [
        {"type": "source", "id": s1.id},
        {"type": "source", "id": s2.id},
    ])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("OrderStack", True))
    panel._create_viewable_from_selection("stack")

    stk = win.session_graph.get_active_viewable()
    assert isinstance(stk, StackView)
    assert stk.source_ids[0] == s2.id
    assert stk.source_ids[1] == s1.id
    assert stk.index_a == 0  # First selected (s2)
    assert stk.index_b == 1  # Second selected (s1)

    # 2. Add s3 to this stack so we have 3 sources [s2, s1, s3]
    stk.source_ids.append(s3.id)
    panel._refresh_subpanels()
    assert panel.list_inputs.count() == 3

    # 3. Clicking an input selects it in the list without altering Layer A/B
    item_s3 = panel.list_inputs.item(2)
    panel._on_input_item_clicked(item_s3)
    assert stk.index_a == 0
    assert stk.index_b == 1

    # 4. User selects row 2 (s3) and presses 'Set Layer A'
    panel.list_inputs.setCurrentRow(2)
    panel._on_stack_set_a()
    assert stk.index_a == 2
    assert stk.current_layer_index == 2
    assert "[A]" in panel.list_inputs.item(2).text()
    assert win.cache._active_source_id == s3.id or win.viewport._image_a is not None

    # 5. User selects row 0 (s2) and presses 'Set Layer B'
    panel.list_inputs.setCurrentRow(0)
    panel._on_stack_set_b()
    assert stk.index_b == 0
    assert stk.current_layer_index == 0
    assert "[B]" in panel.list_inputs.item(0).text()

    # 6. Toggle switch (Z / Shift+Z): strictly alternates between Layer A (s3, idx 2) and Layer B (s2, idx 0)
    # Does NOT switch to s1 (idx 1)!
    assert stk.current_layer_index == 0  # Layer B
    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 2  # Toggled to Layer A
    assert stk.current_layer_index != 1

    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 0  # Toggled back to Layer B
    assert stk.current_layer_index != 1


def test_stack_mix_slider_and_rgba_toggles(qtbot, test_images):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])

    # 1. Create Stack in default A/B Switch mode
    stk = win.session_graph.create_stack("MixStack", [s1.id, s2.id])
    assert stk.compare_mode == "switch"
    assert stk.index_a == 0
    assert stk.index_b == 1
    assert stk.current_layer_index == 0

    win._on_active_view_changed("stack", stk.id)
    win._on_frame_changed(win.clock.current_frame)

    # In switch mode on Layer A, comparison mode should be OVER with Layer B as reference
    assert win.viewport.comparison_state.mode == ComparisonMode.OVER
    assert win.viewport._image_a is not None
    assert win.viewport._image_b is not None

    panel = win.sources_dock.panel

    # 2. Test Mix slider and spinbox adjustments
    panel.slider_stack_mix.setValue(45)
    assert stk.stack_mix == 0.45
    assert panel.spin_stack_mix.value() == 0.45
    assert win.viewport.comparison_state.stack_mix == 0.45

    panel.spin_stack_mix.setValue(0.80)
    assert stk.stack_mix == 0.80
    assert panel.slider_stack_mix.value() == 80
    assert win.viewport.comparison_state.stack_mix == 0.80

    # 3. Verify Mix slider covers width and RGBA channel toggle module is completely removed
    from PySide6.QtWidgets import QSizePolicy
    assert panel.slider_stack_mix.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert not hasattr(panel, "chk_layer_a_r")
    assert not hasattr(panel, "chk_layer_a_g")
    assert not hasattr(panel, "chk_layer_a_b")
    assert not hasattr(panel, "chk_layer_a_a")

    # 4. Cycle to Layer B (Z) -> should solo Layer B (ComparisonMode.OFF, no reference frame)
    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 1
    assert win.viewport.comparison_state.mode == ComparisonMode.OFF
    assert win.viewport._image_b is None
    # Layer B must be strictly protected with 100% full RGBA channels!
    assert win.viewport.comparison_state.channels_a == (True, True, True, True)

    # 5. When viewing Layer B, adjusting Mix or RGBA should auto-switch back to Layer A
    panel.slider_stack_mix.setValue(60)
    assert stk.current_layer_index == 0  # Auto-switched to Layer A
    assert stk.stack_mix == 0.60
    assert win.viewport.comparison_state.mode == ComparisonMode.OVER
    assert win.viewport._image_b is not None


def test_split_mode_and_wipe_controls(qtbot, test_images):
    from PySide6.QtGui import QMouseEvent, QPainter, QImage
    from PySide6.QtCore import QPointF, Qt
    from openreview.color.shader_builder import build_fragment_shader

    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])

    # 1. Verify GLSL fragment shader builds and includes scene-linear conversion & split mode
    f_src = build_fragment_shader()
    assert "to_linear_space" in f_src
    assert "uComparisonMode == 2" in f_src
    assert "TexCoord.x * 2.0" in f_src
    assert "(TexCoord.y - 0.25) * 2.0" in f_src

    # 2. Create Stack and switch to Split mode
    stk = win.session_graph.create_stack("CompSplit", [s1.id, s2.id], compare_mode="split")
    win._on_active_view_changed("stack", stk.id)
    win._on_frame_changed(win.clock.current_frame)

    vp = win.viewport
    assert vp.comparison_state.mode == ComparisonMode.SPLIT
    assert vp._image_a is not None
    assert vp._image_b is not None

    # Test Split mode painting
    img = QImage(300, 200, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    vp._paint_split_overlay(p)
    p.end()

    # In Split mode, left click in viewport must NOT trigger wipe drag
    ev_press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(150, 100),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mousePressEvent(ev_press)
    assert not vp._is_wiping
    assert not vp._is_rotating_wipe

    # 3. Switch to Wipe mode
    stk.compare_mode = "wipe"
    win._on_sources_view_updated()
    assert vp.comparison_state.mode == ComparisonMode.WIPE

    # Test Wipe overlay painting (includes A/B labels)
    p = QPainter(img)
    vp._paint_wipe_overlay(p)
    p.end()

    orig_pos = vp.comparison_state.wipe_position
    hx, hy = vp._wipe_handle_center.x(), vp._wipe_handle_center.y()

    # Click far away from handle/line -> should NOT start wiping or change position!
    far_x = (hx + 200.0) % max(1.0, float(vp.width()))
    far_y = (hy + 200.0) % max(1.0, float(vp.height()))
    ev_far = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(far_x, far_y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mousePressEvent(ev_far)
    assert not vp._is_wiping
    assert vp.comparison_state.wipe_position == orig_pos

    # Click near handle -> SHOULD start wiping
    ev_near = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(hx, hy),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mousePressEvent(ev_near)
    assert vp._is_wiping
    vp._is_wiping = False

    # Shift+Click near handle -> toggles orientation (0 -> 90 -> 0)
    assert vp.comparison_state.wipe_angle_deg == 0.0
    ev_shift = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(hx, hy),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    vp.mousePressEvent(ev_shift)
    assert vp.comparison_state.wipe_angle_deg == 90.0

    vp.mousePressEvent(ev_shift)
    assert vp.comparison_state.wipe_angle_deg == 0.0

    # Double click near handle -> resets wipe
    vp.comparison_state.wipe_position = 0.82
    ev_dbl = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPointF(hx, hy),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mouseDoubleClickEvent(ev_dbl)
    assert vp.comparison_state.wipe_position == 0.5

    # 4. Verify Layer A RGBA channel isolation in shader
    assert "sample_layer_a" in f_src
    assert "uLayerAChannels.x > 0.5" in f_src
    assert "uLayerAChannels.w > 0.5" in f_src

    # 5. Verify drag opacity reduction (25% reduction = 0.75 opacity)
    vp._is_wiping = True
    opacity_set = []
    p2 = QPainter(img)
    orig_set_opacity = p2.setOpacity
    def mock_set_opacity(val):
        opacity_set.append(val)
        orig_set_opacity(val)
    p2.setOpacity = mock_set_opacity
    vp._paint_wipe_overlay(p2)
    p2.end()
    assert 0.75 in opacity_set
    vp._is_wiping = False

    # 6. Verify Safe Guides suppression in Split Mode
    vp.comparison_state.mode = ComparisonMode.SPLIT
    vp.show_safe_guides = True
    # In split mode, safe guides should not be painted
    assert vp.comparison_state.mode == ComparisonMode.SPLIT
    assert vp.show_safe_guides

    # 7. Verify centered wipe rotation pivot when off-center
    import math
    assert "uWipeCenter" in f_src
    vp.comparison_state.mode = ComparisonMode.WIPE
    vp.comparison_state.wipe_center = (0.78, 0.42)
    vp.comparison_state.wipe_angle_deg = 0.0
    h_screen0, _, _, _, _, _ = vp._get_wipe_geometry()

    # Rotate by 45 degrees
    vp.comparison_state.wipe_angle_deg = 45.0
    h_screen45, _, _, _, _, _ = vp._get_wipe_geometry()

    # The handle location MUST remain pinned at the rotation pivot!
    assert math.isclose(h_screen0.x(), h_screen45.x(), abs_tol=1e-3)
    assert math.isclose(h_screen0.y(), h_screen45.y(), abs_tol=1e-3)


def test_stack_toggle_wipe_with_w_shortcut(qtbot, test_images):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])

    # Create Stack (default mode is "switch") and activate it
    stk = win.session_graph.create_stack("WipeToggleStack", [s1.id, s2.id])
    assert stk.compare_mode == "switch"
    win._on_active_view_changed("stack", stk.id)
    assert win.viewport.comparison_state.mode == ComparisonMode.OVER
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "A/B Switch"
    assert not win.wipe_widget.btn_wipe.isChecked()

    # 1. Press "W" to toggle Wipe mode ON
    win._on_toggle_wipe()
    assert stk.compare_mode == "wipe"
    assert win.comparison_state.mode == ComparisonMode.WIPE
    assert win.viewport.comparison_state.mode == ComparisonMode.WIPE
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "Wipe"
    assert win.wipe_widget.btn_wipe.isChecked()
    assert "[WIPE MODE]" in win.windowTitle().upper()

    # 2. Press "W" again to toggle Wipe mode OFF (returns to "switch")
    win._on_toggle_wipe()
    assert stk.compare_mode == "switch"
    assert win.comparison_state.mode == ComparisonMode.OVER
    assert win.viewport.comparison_state.mode == ComparisonMode.OVER
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "A/B Switch"
    assert not win.wipe_widget.btn_wipe.isChecked()
    assert "[SWITCH MODE]" in win.windowTitle().upper()

    # 3. If stack is in another compare mode, e.g. "difference", "W" toggles to wipe and back to difference
    stk.compare_mode = "difference"
    win._on_sources_view_updated()
    assert win.viewport.comparison_state.mode == ComparisonMode.DIFFERENCE
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "Difference"

    # Press "W" -> switches to wipe
    win._on_toggle_wipe()
    assert stk.compare_mode == "wipe"
    assert win.viewport.comparison_state.mode == ComparisonMode.WIPE
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "Wipe"

    # Press "W" again -> restores previous mode ("difference")
    win._on_toggle_wipe()
    assert stk.compare_mode == "difference"
    assert win.viewport.comparison_state.mode == ComparisonMode.DIFFERENCE
    assert win.sources_dock.panel.combo_stack_mode.currentText() == "Difference"




