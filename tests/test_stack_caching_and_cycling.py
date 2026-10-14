"""
Tests for:
1. Unified caching for Sequences, Stacks, and Layouts
2. Default Stacking compare mode is 'over'
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


def test_default_stack_mode_is_over():
    graph = SessionGraph()
    stk = graph.create_stack("TestStack", ["s1", "s2"])
    assert stk.compare_mode == "over"
    stk_def = StackView()
    assert stk_def.compare_mode == "over"


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
    stk = win.session_graph.create_stack("Comp_Stack", [s1.id, s2.id, s3.id])
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

    # Cycle stack forward again (Z) -> should solo layer 2 (s3)
    win._on_stack_cycle_forward()
    assert stk.current_layer_index == 2
    assert win.cache.has_source_frame(s3.id, f)

    # Cycle backward (Shift+Z) -> back to layer 1 (s2), instant RAM hit
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
