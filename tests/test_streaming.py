"""
Unit & Integration Tests for High-Performance Streaming and Caching:
- Directional RAM cache eviction (evict behind playhead before ahead)
- Cancellable ReaderEngine with generation tokens on scrub
- Multi-source timeline resolver for Sequences, Stacks, and Layouts
- SIMD-accelerated format decoding
"""
import os
import tempfile
import numpy as np
import pytest
from PySide6.QtCore import QObject

from openreview.core.cache import RingBufferCache, CacheMode
from openreview.core.reader import MediaReader, ReaderEngine, DiskMediaReader
from openreview.core.sequence_parser import SequenceInfo, DiskSequenceReader
from openreview.models.session_graph import SourceItem, SequenceView, SequenceClip, StackView


class DummyReader(MediaReader):
    def __init__(self, width: int = 100, height: int = 100):
        self.width = width
        self.height = height
        self.read_calls: list[int] = []

    def read_frame(self, frame: int) -> np.ndarray:
        self.read_calls.append(frame)
        return np.zeros((self.height, self.width, 4), dtype=np.float32)


def test_directional_eviction_behind_before_ahead():
    """Test that frames behind the playhead are evicted before frames ahead of the playhead."""
    # 4 frames of 100x100 float32 RGBA = 100 * 100 * 4 * 4 bytes = 160,000 bytes per frame
    # Set limit to 563 KB (0.55 MB, holds ~3.5 frames).
    # When adding the 4th frame, exactly 1 frame must be evicted.
    cache = RingBufferCache(max_memory_mb=0.55, mode=CacheMode.PLAY_AHEAD)
    playhead = 1010
    cache.update_playhead(playhead)

    f_behind = np.ones((100, 100, 4), dtype=np.float32)
    f_current = np.ones((100, 100, 4), dtype=np.float32)
    f_ahead = np.ones((100, 100, 4), dtype=np.float32)

    # Put frame behind playhead (1005)
    cache.put_frame(1005, f_behind)
    assert cache.has_frame(1005)

    # Put playhead frame (1010)
    cache.put_frame(1010, f_current)
    assert cache.has_frame(1010)

    # Put frame ahead of playhead (1015)
    cache.put_frame(1015, f_ahead)
    assert cache.has_frame(1015)

    # Put another frame ahead (1020) which forces eviction
    f_ahead2 = np.ones((100, 100, 4), dtype=np.float32)
    cache.put_frame(1020, f_ahead2)

    # Frame 1005 (behind playhead) MUST have been evicted before frames ahead (1015, 1020)
    assert not cache.has_frame(1005), "Frame behind playhead should be evicted first"
    assert cache.has_frame(1010), "Current playhead frame must be protected"
    assert cache.has_frame(1015), "Near ahead frame must be retained"
    assert cache.has_frame(1020), "Newly added upcoming frame should be cached"


def test_reader_engine_generation_cancellation(qtbot):
    """Test that scrubbing increments generation token and discards stale tasks."""
    reader = DummyReader()
    cache = RingBufferCache(max_memory_mb=100.0, mode=CacheMode.PLAY_AHEAD)
    engine = ReaderEngine(reader, cache)

    initial_gen = engine.current_generation
    engine.request_prefetch(1, 100, current_frame=10)
    gen_after_first = engine.current_generation
    assert gen_after_first > initial_gen

    # Simulate rapid scrub to frame 50
    engine.request_prefetch(1, 100, current_frame=50)
    gen_after_scrub = engine.current_generation
    assert gen_after_scrub > gen_after_first

    # Simulate a stale callback from an older generation
    dummy_data = np.zeros((10, 10, 4), dtype=np.float32)
    engine._on_frame_loaded(
        timeline_frame=12,
        source_frame=12,
        data=dummy_data,
        source_id="",
        generation=gen_after_first,  # Old generation
    )
    # The stale frame must NOT be inserted into cache
    assert not cache.has_frame(12), "Stale prefetch task from older generation must be discarded"
    engine.thread_pool.waitForDone(2000)


def test_multi_source_sequence_resolver(qtbot):
    """Test timeline resolver across a cut sequence with two different source clips."""
    src_a = SourceItem(id="src_a", name="Shot A", path="synthetic_pattern", start_frame=1001, end_frame=1020)
    src_b = SourceItem(id="src_b", name="Shot B", path="synthetic_pattern", start_frame=2001, end_frame=2020)
    sources = {"src_a": src_a, "src_b": src_b}

    seq = SequenceView(
        id="seq_1",
        name="Cut Sequence",
        start_frame=1,
        clips=[
            SequenceClip(source_id="src_a", trim_in=1001, trim_out=1010),
            SequenceClip(source_id="src_b", trim_in=2001, trim_out=2010),
        ],
    )

    readers = {
        "src_a": DummyReader(),
        "src_b": DummyReader(),
    }

    def resolver(tf: int):
        src, sf = seq.resolve_frame(tf, sources)
        if src:
            return [(src.id, sf, readers[src.id])]
        return []

    cache = RingBufferCache(max_memory_mb=100.0, mode=CacheMode.PLAY_AHEAD)
    engine = ReaderEngine(None, cache)

    # Timeline frame 5 -> Shot A frame 1005
    res5 = resolver(5)
    assert len(res5) == 1
    assert res5[0][0] == "src_a"
    assert res5[0][1] == 1005

    # Timeline frame 15 -> Shot B frame 2005
    res15 = resolver(15)
    assert len(res15) == 1
    assert res15[0][0] == "src_b"
    assert res15[0][1] == 2005

    # Request prefetch around cut boundary (frame 8 to 14)
    engine.request_prefetch(1, 20, current_frame=9, resolver_fn=resolver)

    # Let the thread pool finish tasks
    engine.thread_pool.waitForDone(3000)

    # Verify both Shot A and Shot B frames were prefetched across the cut
    assert any(f in readers["src_a"].read_calls for f in [1009, 1010])
    assert any(f in readers["src_b"].read_calls for f in [2001, 2002])


def test_simd_color_conversion_in_disk_reader():
    """Verify SIMD cv2.cvtColor in DiskSequenceReader properly outputs 4-channel RGBA."""
    import cv2
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy image
        img_path = os.path.join(tmpdir, "test.1001.png")
        bgr = np.full((64, 64, 3), 180, dtype=np.uint8)
        cv2.imwrite(img_path, bgr)

        seq_info = SequenceInfo(
            directory=tmpdir,
            prefix="test.",
            separator="",
            padding=4,
            extension=".png",
            start_frame=1001,
            end_frame=1001,
            available_frames={1001},
            missing_frames=set(),
        )

        reader = DiskSequenceReader(seq_info)
        frame_data = reader.read_frame(1001)

        assert frame_data is not None
        assert frame_data.ndim == 3
        assert frame_data.shape[2] == 4  # RGBA
        # Alpha channel should be 1.0 (float) or 255 (uint8)
        assert frame_data[0, 0, 3] == 1.0 or frame_data[0, 0, 3] == 255
