"""
Tests for dynamic caching behavior:
1. Starting caching only caches the active input in the viewport.
2. Inactive loaded/discovered sources are not automatically queued for background caching.
3. Switching the active viewer dynamically pivots caching:
   - In-flight background prefetch jobs are cancelled (generation bumped).
   - Prefetching begins immediately for the new active viewable.
   - Existing cached frames in RAM ring buffer are retained for fast back-and-forth switching.
4. Stack views cache both Layer A and Layer B across the timeline.
"""
import os
import tempfile
import numpy as np
from PIL import Image
import pytest

from openreview.models.session_graph import SessionGraph, ViewType, StackView, SourceItem
from openreview.models.comparison import ComparisonMode
from openreview.core.cache import CacheMode
from openreview.ui.main_window import MainWindow


@pytest.fixture
def test_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(1, 4):
            p = os.path.join(tmpdir, f"dyn_frame_{i:04d}.png")
            img = Image.new("RGBA", (64, 64), color=(i * 60, 120, 180, 255))
            img.save(p)
            paths.append(p)
        yield paths


def test_inactive_sources_not_queued_for_background_caching(qtbot, test_images):
    """Discovered sources during async import should not steal background cache bandwidth."""
    win = MainWindow()
    qtbot.addWidget(win)

    item1 = SourceItem(id="src1", name="src1", path=test_images[0], media_type="sequence", start_frame=1, end_frame=10)
    item2 = SourceItem(id="src2", name="src2", path=test_images[1], media_type="sequence", start_frame=1, end_frame=10)

    win._on_async_source_discovered(item1, 0, 2)
    win._on_async_source_discovered(item2, 1, 2)

    assert "src1" in win.session_graph.sources
    assert "src2" in win.session_graph.sources
    # Secondary background cache queue must remain empty
    assert len(win.reader_engine._bg_cache_queue) == 0


def test_only_active_viewport_input_resolved_and_cached(qtbot, test_images):
    """Prefetch resolver decomposes timeline frames strictly for the active viewport input."""
    win = MainWindow()
    qtbot.addWidget(win)

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])
    s3 = win.session_graph.add_source_from_path(test_images[2])

    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    targets = win._resolve_timeline_frame_sources(1)

    assert len(targets) == 1
    src_id, frame_num, rdr = targets[0]
    assert src_id == s1.id
    assert frame_num == 1
    assert rdr is not None


def test_dynamic_active_viewer_switching_cancels_and_caches_new(qtbot, test_images):
    """Switching active viewer dynamically cancels in-flight tasks and redirects caching to new active view."""
    win = MainWindow()
    qtbot.addWidget(win)

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])

    # Start caching in REGION mode
    win._on_set_cache_mode(CacheMode.REGION, start_prefetch=True)
    assert win._cache_started is True
    assert win.cache.mode == CacheMode.REGION

    # Set active view to s1
    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    initial_gen = win.reader_engine.current_generation

    # Populate cache for s1 frame 1
    frame_dummy = np.zeros((64, 64, 4), dtype=np.uint8)
    win.cache.put_source_frame(s1.id, 1, frame_dummy)
    assert win.cache.has_source_frame(s1.id, 1)

    # Now dynamically switch active view to s2
    win.session_graph.set_active_view(ViewType.SOURCE, s2.id)

    # Generation must have incremented (invalidating any pending/in-flight tasks from s1)
    assert win.reader_engine.current_generation > initial_gen

    # Active resolver now targets s2
    targets = win._resolve_timeline_frame_sources(1)
    assert len(targets) == 1
    assert targets[0][0] == s2.id

    # Previously cached frame for s1 is retained in LRU RAM cache
    assert win.cache.has_source_frame(s1.id, 1)


def test_stack_view_caches_both_layer_a_and_layer_b(qtbot, test_images):
    """Stack view resolves and caches both Layer A and Layer B across the timeline even in A/B switch mode."""
    win = MainWindow()
    qtbot.addWidget(win)

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])
    s3 = win.session_graph.add_source_from_path(test_images[2])

    stk = win.session_graph.create_stack("AB_Stack", [s1.id, s2.id, s3.id], compare_mode="switch")
    stk.index_a = 0  # s1
    stk.index_b = 1  # s2
    win.session_graph.set_active_view(ViewType.STACK, stk.id)

    targets = win._resolve_timeline_frame_sources(1)
    target_sids = [t[0] for t in targets]

    # Both Layer A and Layer B must be resolved, while inactive s3 is omitted
    assert s1.id in target_sids
    assert s2.id in target_sids
    assert s3.id not in target_sids
    assert len(target_sids) == 2


def test_sequence_mode_auto_caches_full_sequence_and_restores(qtbot, test_images):
    """Switching to Sequence automatically switches to CacheMode.ALL and prefetch; restores on exit."""
    from openreview.models.session_graph import SequenceClip
    win = MainWindow()
    qtbot.addWidget(win)

    s1 = win.session_graph.add_source_from_path(test_images[0])
    s2 = win.session_graph.add_source_from_path(test_images[1])

    # 1. Start on Source 1 in REGION mode, but idle (caching not started)
    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    win._on_set_cache_mode(CacheMode.REGION, start_prefetch=False)
    assert win.cache.mode == CacheMode.REGION
    assert win._cache_started is False

    # Create a Sequence
    seq = win.session_graph.create_sequence("TestSeq")
    seq.clips.append(SequenceClip(source_id=s1.id, trim_in=1, trim_out=5))
    seq.clips.append(SequenceClip(source_id=s2.id, trim_in=1, trim_out=5))

    # 2. Switch to Sequence -> Auto-switches to CacheMode.ALL and starts prefetching
    win.session_graph.set_active_view(ViewType.SEQUENCE, seq.id)
    assert win.cache.mode == CacheMode.ALL
    assert win._cache_started is True
    assert win.cache_mode_actions[CacheMode.ALL].isChecked() is True

    # 3. Switch back to Source 1 -> Reverts mode to REGION and active state to False
    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    assert win.cache.mode == CacheMode.REGION
    assert win._cache_started is False
    assert win.cache_mode_actions[CacheMode.REGION].isChecked() is True

    # 4. If user had caching active (e.g. PLAY_AHEAD active) before entering sequence
    win._on_set_cache_mode(CacheMode.PLAY_AHEAD, start_prefetch=True)
    assert win.cache.mode == CacheMode.PLAY_AHEAD
    assert win._cache_started is True

    win.session_graph.set_active_view(ViewType.SEQUENCE, seq.id)
    assert win.cache.mode == CacheMode.ALL
    assert win._cache_started is True

    # Switching to a Stack view reverts to pre-sequence mode (PLAY_AHEAD) with caching active
    stk = win.session_graph.create_stack("TestStack", [s1.id, s2.id])
    win.session_graph.set_active_view(ViewType.STACK, stk.id)
    assert win.cache.mode == CacheMode.PLAY_AHEAD
    assert win._cache_started is True

    # 5. Respect manual override while in Sequence view
    win.session_graph.set_active_view(ViewType.SEQUENCE, seq.id)
    assert win.cache.mode == CacheMode.ALL
    win._on_set_cache_mode(CacheMode.OFF)  # User manually toggles off
    assert win.cache.mode == CacheMode.OFF
    assert win._cache_started is False

    # Leaving sequence restores pre-sequence mode (PLAY_AHEAD)
    win.session_graph.set_active_view(ViewType.SOURCE, s1.id)
    assert win.cache.mode == CacheMode.PLAY_AHEAD

