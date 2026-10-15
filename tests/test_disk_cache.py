"""
Unit tests for DiskFrameCache and Two-Tier (RAM + Temp Drive) Caching.
"""
import os
import shutil
import tempfile
import numpy as np
import pytest

from openreview.core.cache import DiskFrameCache, RingBufferCache, CacheMode


def test_disk_frame_cache_put_get():
    temp_dir = os.path.join(tempfile.gettempdir(), "test_disk_cache_put_get")
    try:
        dc = DiskFrameCache(cache_dir=temp_dir, max_disk_mb=50.0, auto_cleanup=False)
        arr = np.ones((100, 100, 4), dtype=np.float32) * 1.5

        assert not dc.has("src1", 1001)
        dc.put("src1", 1001, arr)
        assert dc.has("src1", 1001)

        retrieved = dc.get("src1", 1001)
        assert retrieved is not None
        assert retrieved.shape == (100, 100, 4)
        # Verify float16 conversion preserved value within half-precision epsilon
        assert np.isclose(retrieved[50, 50, 0], 1.5, atol=1e-3)

        used_mb, max_mb, pct = dc.get_stats()
        assert used_mb > 0.0
        assert max_mb == 50.0
        assert pct > 0.0

        dc.delete("src1", 1001)
        assert not dc.has("src1", 1001)
        assert dc.get("src1", 1001) is None
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_disk_frame_cache_lru_eviction():
    temp_dir = os.path.join(tempfile.gettempdir(), "test_disk_cache_lru")
    try:
        # Budget = 0.5 MB (~512 KB)
        dc = DiskFrameCache(cache_dir=temp_dir, max_disk_mb=0.5, auto_cleanup=False)
        # Each float16 frame of (200, 200, 4) is 200*200*4*2 = 320,000 bytes (~0.3 MB)
        arr1 = np.full((200, 200, 4), 1.0, dtype=np.float16)
        arr2 = np.full((200, 200, 4), 2.0, dtype=np.float16)

        dc.put("src1", 1, arr1)
        assert dc.has("src1", 1)

        dc.put("src1", 2, arr2)
        assert dc.has("src1", 2)

        # Third frame should cause eviction of frame 1 (oldest access)
        arr3 = np.full((200, 200, 4), 3.0, dtype=np.float16)
        dc.put("src1", 3, arr3)

        used_mb, max_mb, _ = dc.get_stats()
        assert used_mb <= max_mb
        # Frame 1 was least recently accessed, so it should be evicted
        assert not dc.has("src1", 1)
        assert dc.has("src1", 3)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_ring_buffer_ram_spill_to_disk():
    # RAM Budget = 5 MB, Disk Budget = 100 MB
    temp_dir = os.path.join(tempfile.gettempdir(), "test_ring_buffer_spill")
    try:
        cache = RingBufferCache(
            max_memory_mb=5.0,
            mode=CacheMode.PLAY_AHEAD,
            enable_disk_cache=True,
            max_disk_mb=100.0,
            disk_cache_dir=temp_dir,
        )

        # 400x400 float32 4-channel = 2.56 MB per frame
        arr = np.zeros((400, 400, 4), dtype=np.float32)

        cache.update_playhead(1005)

        # Insert frame 1001, 1002, 1003 into RAM
        cache.put_source_frame("source_A", 1001, arr, write_to_disk=False)
        cache.put_source_frame("source_A", 1002, arr, write_to_disk=False)
        assert cache.has_source_frame_ram("source_A", 1001)
        assert cache.has_source_frame_ram("source_A", 1002)

        # Insert frame 1003 (exceeds 5MB RAM budget -> frame 1001 evicted from RAM and spilled to disk)
        cache.put_source_frame("source_A", 1003, arr, write_to_disk=False)

        # Frame 1001 should now be evicted from RAM but preserved on Temp Disk!
        assert not cache.has_source_frame_ram("source_A", 1001)
        assert cache.has_source_frame_disk("source_A", 1001)
        assert cache.has_source_frame("source_A", 1001)

        # Getting frame 1001 retrieves it seamlessly from disk cache
        retrieved = cache.get_source_frame("source_A", 1001)
        assert retrieved is not None
        assert retrieved.shape == (400, 400, 4)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_put_source_frame_disk_only():
    temp_dir = os.path.join(tempfile.gettempdir(), "test_disk_only")
    try:
        cache = RingBufferCache(
            max_memory_mb=10.0,
            mode=CacheMode.PLAY_AHEAD,
            enable_disk_cache=True,
            disk_cache_dir=temp_dir,
        )

        arr = np.ones((50, 50, 4), dtype=np.float32)
        # Put secondary source frame directly to disk
        cache.put_source_frame_disk_only("sec_src", 42, arr)

        # Must NOT be in RAM
        assert not cache.has_source_frame_ram("sec_src", 42)
        # Must be in Disk cache
        assert cache.has_source_frame_disk("sec_src", 42)
        assert cache.has_source_frame("sec_src", 42)

        # Query frame numbers
        assert 42 not in cache.get_source_cached_frames("sec_src")
        assert 42 in cache.get_source_disk_cached_frames("sec_src")
        assert 42 in cache.get_all_source_cached_frames("sec_src")

        # Clear specific source
        cache.clear_source("sec_src")
        assert not cache.has_source_frame("sec_src", 42)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_reader_background_disk_caching(qapp):
    import time
    from PySide6.QtCore import QCoreApplication
    from openreview.core.reader import ReaderEngine, CallableVirtualReader

    temp_dir = os.path.join(tempfile.gettempdir(), "test_reader_bg_cache")
    try:
        cache = RingBufferCache(
            max_memory_mb=10.0,
            mode=CacheMode.PLAY_AHEAD,
            enable_disk_cache=True,
            disk_cache_dir=temp_dir,
        )
        engine = ReaderEngine(reader=None, cache=cache)

        rdr = CallableVirtualReader(lambda f: np.ones((40, 40, 4), dtype=np.float32) * float(f))
        progress_events = []
        engine.background_progress.connect(lambda sid, c, t: progress_events.append((sid, c, t)))

        engine.queue_source_background_cache("bg_src_1", rdr, 1, 5)

        # Process events for up to 3 seconds until all 5 frames are disk cached
        t0 = time.time()
        while time.time() - t0 < 3.0:
            engine.thread_pool.waitForDone(50)
            QCoreApplication.processEvents()
            if cache.get_source_disk_cached_count("bg_src_1") >= 5:
                break

        assert cache.get_source_disk_cached_count("bg_src_1") == 5
        for f in range(1, 6):
            assert cache.has_source_frame_disk("bg_src_1", f)
            # RAM must NOT be consumed by background caching
            assert not cache.has_source_frame_ram("bg_src_1", f)

        # Confirm retrieval gets array directly from disk
        frame_3 = cache.get_source_frame("bg_src_1", 3)
        assert frame_3 is not None
        assert np.isclose(frame_3[0, 0, 0], 3.0, atol=1e-3)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
