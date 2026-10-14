"""
Unit tests for RingBufferCache, CacheMode, and memory management.
"""
import pytest
import numpy as np
from openreview.core.cache import RingBufferCache, CacheMode


def test_cache_default_is_off():
    cache = RingBufferCache()
    assert cache.mode == CacheMode.OFF
    arr = np.zeros((10, 10, 4), dtype=np.float32)
    cache.put_frame(1001, arr)
    assert not cache.has_frame(1001)
    targets = cache.get_prefetch_targets(1001, 1200)
    assert targets == (0, -1)


def test_cache_put_and_get():
    cache = RingBufferCache(max_memory_mb=64.0, mode=CacheMode.PLAY_AHEAD)
    arr = np.zeros((100, 100, 4), dtype=np.float32)

    cache.put_frame(1001, arr)
    assert cache.has_frame(1001)
    retrieved = cache.get_frame(1001)
    assert retrieved is not None
    assert retrieved.shape == (100, 100, 4)


def test_cache_memory_stats():
    cache = RingBufferCache(max_memory_mb=100.0, mode=CacheMode.PLAY_AHEAD)
    # 1000x1000 float32 4-channel = 16 MB per frame
    arr = np.zeros((1000, 1000, 4), dtype=np.float32)

    cache.put_frame(1001, arr)
    used_mb, max_mb, pct = cache.get_memory_stats()
    assert 15.0 < used_mb < 17.0
    assert max_mb == 100.0
    assert 15.0 < pct < 17.0


def test_cache_eviction_when_budget_exceeded():
    # 10 MB budget
    cache = RingBufferCache(max_memory_mb=10.0, mode=CacheMode.PLAY_AHEAD)
    # 500x500 float32 4-channel = 4 MB per frame
    arr = np.zeros((500, 500, 4), dtype=np.float32)

    cache.update_playhead(1005)

    # Insert frame 1001, 1002, 1003, 1004 (4 MB * 4 = 16 MB > 10 MB)
    cache.put_frame(1001, arr)
    cache.put_frame(1002, arr)
    cache.put_frame(1003, arr)
    cache.put_frame(1004, arr)

    used_mb, max_mb, _ = cache.get_memory_stats()
    # Memory must stay under budget
    assert used_mb <= max_mb

    # Frame 1001 is furthest from playhead 1005, so it should be evicted first
    assert not cache.has_frame(1001)
    # Frame 1004 is closest to playhead 1005, so it should be retained
    assert cache.has_frame(1004)


def test_cache_prefetch_targets():
    cache = RingBufferCache(lookahead_frames=20, lookbehind_frames=5, mode=CacheMode.PLAY_AHEAD)
    cache.update_playhead(1050)
    start_target, end_target = cache.get_prefetch_targets(1001, 1200)
    assert start_target == 1045
    assert end_target == 1070


def test_cache_region_mode():
    cache = RingBufferCache(mode=CacheMode.REGION)
    cache.set_region_bounds(1010, 1030)

    # Prefetch targets must be strictly within in_frame to out_frame
    start_target, end_target = cache.get_prefetch_targets(1001, 1200, in_frame=1010, out_frame=1030)
    assert start_target == 1010
    assert end_target == 1030

    arr = np.zeros((10, 10, 4), dtype=np.float32)
    # Frame inside region is cached
    cache.put_frame(1015, arr)
    assert cache.has_frame(1015)

    # Frame outside region is NOT cached (unless playhead)
    cache.put_frame(1005, arr)
    assert not cache.has_frame(1005)

