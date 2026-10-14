"""
Ring-Buffer Frame Cache and RAM Pool Manager.
Provides bounded in-memory frame storage, lookahead prefetching, and LRU eviction.
"""
from __future__ import annotations

from enum import Enum
import ctypes
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple, Union, Any
import numpy as np
from PySide6.QtCore import QObject, Signal


def get_system_ram_stats_mb() -> Tuple[float, float]:
    """
    Detect total and currently available system RAM in megabytes.
    Returns (total_ram_mb, avail_ram_mb).
    """
    try:
        import psutil
        vm = psutil.virtual_memory()
        total_mb = float(vm.total) / (1024.0 * 1024.0)
        avail_mb = float(vm.available) / (1024.0 * 1024.0)
        if total_mb > 0:
            return total_mb, max(256.0, avail_mb)
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = float(stat.ullTotalPhys) / (1024.0 * 1024.0)
                avail_mb = float(stat.ullAvailPhys) / (1024.0 * 1024.0)
                if total_mb > 0:
                    return total_mb, max(256.0, avail_mb)
        except Exception:
            pass

    return 16384.0, 8192.0


def compute_dynamic_ram_budget_mb(
    used_cache_bytes: int = 0,
    reserve_ratio: float = 0.80,
    min_os_headroom_mb: float = 2048.0,
) -> float:
    """
    Compute safe RAM budget in MB based on currently available system RAM plus
    any memory already held by OpenReview's frame cache.
    Allocates up to `reserve_ratio` (default 80%) of usable RAM while preserving
    at least `min_os_headroom_mb` (scaled on low-RAM machines) for the OS and other apps.
    """
    total_mb, os_avail_mb = get_system_ram_stats_mb()
    used_cache_mb = max(0.0, float(used_cache_bytes) / (1024.0 * 1024.0))
    usable_mb = min(total_mb, os_avail_mb + used_cache_mb)

    effective_headroom = min(min_os_headroom_mb, total_mb * 0.20)
    max_after_headroom = max(256.0, usable_mb - effective_headroom)
    target_mb = min(usable_mb * reserve_ratio, max_after_headroom)

    if target_mb >= 1024.0:
        return float(round(target_mb, -2))
    return float(max(256.0, round(target_mb)))


def get_dynamic_gb_presets(total_ram_mb: Optional[float] = None) -> List[int]:
    """
    Generate power-of-two GB presets scaling dynamically up to system total RAM
    without restricting to 16 GB (e.g., 1, 2, 4, 8, 16, 32, 64, 128, 256+ GB).
    """
    if total_ram_mb is None:
        total_ram_mb, _ = get_system_ram_stats_mb()
    total_gb = max(8.0, total_ram_mb / 1024.0)

    presets: List[int] = []
    gb = 1
    while gb <= total_gb:
        presets.append(gb)
        gb *= 2

    # Ensure standard baseline presets exist for tests/low-spec machines
    for base_gb in (1, 2, 4, 8):
        if base_gb not in presets:
            presets.append(base_gb)
    presets.sort()
    return presets


class CacheMode(str, Enum):
    """Caching strategy modes for OpenReview."""
    OFF = "off"                    # Default: caching disabled, zero background prefetch
    PLAY_AHEAD = "play_ahead"      # Prefetch lookahead window ahead of playhead
    REGION = "region"              # Cache strictly within active In/Out region marks
    ALL = "all"                    # Full sequence cache


class RingBufferCache(QObject):
    """
    Thread-safe RAM ring buffer for image review frames.
    - Adapts RAM usage dynamically to system RAM availability or a configured budget.
    - Supports multiple cache modes: OFF (default), PLAY_AHEAD, REGION (In/Out only), and ALL.
    - Evicts frames furthest from the current playhead or outside In/Out marks.
    - Generates cache status bitmasks and utilization percentages for the UI.
    """

    cache_changed = Signal()  # Emitted when cached frame set changes
    memory_usage_changed = Signal(float, float)  # used_mb, max_mb
    mode_changed = Signal(str)  # Emitted when cache mode changes ('off', 'play_ahead', 'region', 'all')

    def __init__(
        self,
        max_memory_mb: Optional[float] = None,
        lookahead_frames: int = 48,
        lookbehind_frames: int = 16,
        mode: CacheMode = CacheMode.OFF,
        auto_memory_budget: bool = False,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._auto_memory_budget = bool(auto_memory_budget or max_memory_mb is None)
        self._last_auto_refresh_ts: float = 0.0
        initial_mb = (
            compute_dynamic_ram_budget_mb(0)
            if max_memory_mb is None
            else max(128.0, float(max_memory_mb))
        )
        self._max_memory_bytes = int(initial_mb * 1024 * 1024)
        self._lookahead = lookahead_frames
        self._lookbehind = lookbehind_frames
        self._current_playhead = 1001
        self._in_frame: Optional[int] = None
        self._out_frame: Optional[int] = None

        self._lock = threading.Lock()
        self._active_source_id: Optional[str] = None
        # Tier 1 Storage: Primary display RGBA textures for real-time playback
        # Storage: (source_id, frame) or int frame -> np.ndarray
        self._frames: Dict[Any, Any] = {}
        self._frame_bytes: Dict[Any, int] = {}
        self._frame_mtimes: Dict[Any, float] = {}
        self._used_bytes: int = 0

        # Tier 2 Storage: Lazy raw multi-channel / pass layer cache
        # Storage: (source_id, frame, layer_name) -> np.ndarray
        self._layer_cache: Dict[Tuple[str, int, str], np.ndarray] = {}
        self._layer_bytes: Dict[Tuple[str, int, str], int] = {}
        self._layer_used_bytes: int = 0
        self._max_layer_memory_bytes: int = int(self._max_memory_bytes * 0.5)  # 50% budget for raw layers

    # --------------------------------------------------------------------------
    # Configuration
    # --------------------------------------------------------------------------
    @property
    def mode(self) -> CacheMode:
        return self._mode

    @property
    def auto_memory_budget(self) -> bool:
        return self._auto_memory_budget

    @property
    def max_memory_mb(self) -> float:
        with self._lock:
            return self._max_memory_bytes / (1024.0 * 1024.0)

    def _refresh_auto_budget_locked(self, force: bool = False) -> None:
        """Recalculate memory budget from live available system RAM while lock is held."""
        if not self._auto_memory_budget:
            return
        now = time.monotonic()
        if not force and (now - self._last_auto_refresh_ts) < 1.0:
            return
        self._last_auto_refresh_ts = now
        new_mb = compute_dynamic_ram_budget_mb(self._used_bytes)
        self._max_memory_bytes = int(max(128.0, new_mb) * 1024 * 1024)
        self._max_layer_memory_bytes = int(self._max_memory_bytes * 0.5)

    def refresh_auto_budget(self) -> float:
        """Force an immediate refresh of the dynamic available RAM budget and return max_mb."""
        with self._lock:
            self._refresh_auto_budget_locked(force=True)
            self._evict_if_needed(self._current_playhead)
            max_mb = self._max_memory_bytes / (1024.0 * 1024.0)
        self._emit_status()
        return max_mb

    def set_auto_memory_budget(self, enabled: bool = True) -> float:
        """Enable or disable dynamic system available RAM budget."""
        with self._lock:
            self._auto_memory_budget = bool(enabled)
            if self._auto_memory_budget:
                self._refresh_auto_budget_locked(force=True)
                self._evict_if_needed(self._current_playhead)
            max_mb = self._max_memory_bytes / (1024.0 * 1024.0)
        self._emit_status()
        return max_mb

    def set_active_source(self, source_id: Optional[str]) -> None:
        """Set the active source context for single-frame lookup/store."""
        self._active_source_id = source_id

    def set_mode(self, mode: CacheMode | str) -> None:
        """Update caching operational mode."""
        if isinstance(mode, str):
            mode = CacheMode(mode)
        if self._mode != mode:
            self._mode = mode
            if self._mode == CacheMode.OFF:
                self.clear()
            else:
                self._emit_status()
            self.mode_changed.emit(self._mode.value)

    def set_region_bounds(self, in_frame: int, out_frame: int) -> None:
        """Inform the cache of the active In/Out region marks."""
        self._in_frame = in_frame
        self._out_frame = out_frame
        if self._mode == CacheMode.REGION:
            with self._lock:
                self._evict_if_needed(self._current_playhead)
            self._emit_status()

    def set_max_memory_mb(self, mb: float, auto: bool = False) -> None:
        """Update maximum memory budget in megabytes."""
        with self._lock:
            self._auto_memory_budget = bool(auto)
            self._max_memory_bytes = int(max(128.0, mb) * 1024 * 1024)
            self._max_layer_memory_bytes = int(self._max_memory_bytes * 0.5)
            self._evict_if_needed(self._current_playhead)
        self._emit_status()

    def set_prefetch_range(self, lookahead: int, lookbehind: int) -> None:
        """Configure how many frames to prefetch ahead and behind the playhead."""
        self._lookahead = max(1, lookahead)
        self._lookbehind = max(0, lookbehind)

    # --------------------------------------------------------------------------
    # Source-Level Cache Access
    # --------------------------------------------------------------------------
    def get_source_frame(self, source_id: str, frame: int) -> Optional[np.ndarray]:
        """Retrieve a cached frame for a specific input source."""
        if self._mode == CacheMode.OFF or not source_id:
            return None
        with self._lock:
            return self._frames.get((source_id, frame))

    def has_source_frame(self, source_id: str, frame: int) -> bool:
        """Check if a specific source frame is already in RAM cache."""
        if self._mode == CacheMode.OFF or not source_id:
            return False
        with self._lock:
            return (source_id, frame) in self._frames

    def put_source_frame(self, source_id: str, frame: int, image_data: np.ndarray, mtime: Optional[float] = None) -> None:
        """Store a frame for a specific source into the shared RAM pool."""
        if self._mode == CacheMode.OFF or not source_id or image_data is None:
            return

        byte_size = image_data.nbytes if isinstance(image_data, np.ndarray) else 0
        if byte_size == 0:
            return

        # In Region mode, do not cache frames outside [in_frame, out_frame] unless it's playhead
        if self._mode == CacheMode.REGION and self._in_frame is not None and self._out_frame is not None:
            if not (self._in_frame <= frame <= self._out_frame) and frame != self._current_playhead:
                return

        key = (source_id, frame)
        with self._lock:
            if key in self._frames:
                self._used_bytes -= self._frame_bytes[key]

            self._frames[key] = image_data
            self._frame_bytes[key] = byte_size
            self._frame_mtimes[key] = float(mtime) if mtime is not None else time.time()
            self._used_bytes += byte_size

            self._refresh_auto_budget_locked()
            self._evict_if_needed(self._current_playhead)

        self._emit_status()

    # --------------------------------------------------------------------------
    # Tier 2: Multi-Channel Layer Cache Access
    # --------------------------------------------------------------------------
    def get_layer_frame(self, source_id: str, frame: int, layer: str) -> Optional[np.ndarray]:
        """Retrieve a cached multi-channel layer frame."""
        if self._mode == CacheMode.OFF or not source_id or not layer:
            return None
        with self._lock:
            return self._layer_cache.get((source_id, frame, layer))

    def has_layer_frame(self, source_id: str, frame: int, layer: str) -> bool:
        """Check if a specific multi-channel layer frame is in Tier-2 RAM cache."""
        if self._mode == CacheMode.OFF or not source_id or not layer:
            return False
        with self._lock:
            return (source_id, frame, layer) in self._layer_cache

    def put_layer_frame(self, source_id: str, frame: int, layer: str, image_data: np.ndarray) -> None:
        """Store a multi-channel layer frame into Tier-2 RAM cache."""
        if self._mode == CacheMode.OFF or not source_id or not layer or image_data is None:
            return

        byte_size = image_data.nbytes if isinstance(image_data, np.ndarray) else 0
        if byte_size == 0:
            return

        key = (source_id, frame, layer)
        with self._lock:
            if key in self._layer_cache:
                self._layer_used_bytes -= self._layer_bytes[key]

            self._layer_cache[key] = image_data
            self._layer_bytes[key] = byte_size
            self._layer_used_bytes += byte_size

            # Evict from layer cache if exceeded
            while self._layer_used_bytes > self._max_layer_memory_bytes and self._layer_cache:
                oldest_k = next(iter(self._layer_cache))
                b = self._layer_bytes.pop(oldest_k, 0)
                self._layer_cache.pop(oldest_k, None)
                self._layer_used_bytes -= b

    def clear_layer_cache(self) -> None:
        """Clear Tier-2 multi-channel layer cache."""
        with self._lock:
            self._layer_cache.clear()
            self._layer_bytes.clear()
            self._layer_used_bytes = 0

    def clear_source(self, source_id: str) -> None:
        """Clear cached frames for a specific source only."""
        if not source_id:
            return
        with self._lock:
            keys_to_remove = [k for k in self._frames.keys() if isinstance(k, tuple) and k[0] == source_id]
            for k in keys_to_remove:
                self._used_bytes -= self._frame_bytes.pop(k, 0)
                self._frames.pop(k, None)
                self._frame_mtimes.pop(k, None)

            layer_keys = [k for k in self._layer_cache.keys() if k[0] == source_id]
            for k in layer_keys:
                self._layer_used_bytes -= self._layer_bytes.pop(k, 0)
                self._layer_cache.pop(k, None)
        self._emit_status()

    def clear_source_frame(self, source_id: str, frame: int) -> None:
        """Clear a specific frame from cache for a given source."""
        key = (source_id, frame)
        with self._lock:
            if key in self._frames:
                self._used_bytes -= self._frame_bytes.pop(key, 0)
                self._frames.pop(key, None)
                self._frame_mtimes.pop(key, None)
        self._emit_status()

    def get_source_frame_mtime(self, source_id: str, frame: int) -> Optional[float]:
        """Return the stored file modification timestamp for a cached source frame."""
        key = (source_id, frame)
        with self._lock:
            return self._frame_mtimes.get(key)

    def get_source_cached_frames(self, source_id: str) -> Set[int]:
        """Return the set of cached frame numbers for a specific source."""
        if not source_id:
            return set()
        with self._lock:
            return {k[1] for k in self._frames.keys() if isinstance(k, tuple) and k[0] == source_id}

    # --------------------------------------------------------------------------
    # Timeline & Compatibility Cache Access
    # --------------------------------------------------------------------------
    def get_frame(self, frame: int) -> Optional[Any]:
        """Retrieve a frame if present in RAM cache, else return None."""
        if self._mode == CacheMode.OFF:
            return None
        with self._lock:
            if self._active_source_id:
                res = self._frames.get((self._active_source_id, frame))
                if res is not None:
                    return res
            return self._frames.get(frame)

    def has_frame(self, frame: int) -> bool:
        """Check if frame exists in cache."""
        with self._lock:
            if self._active_source_id and (self._active_source_id, frame) in self._frames:
                return True
            return frame in self._frames

    def put_frame(self, frame: int, image_data: Union[np.ndarray, tuple]) -> None:
        """Store a frame array or (primary, reference) tuple into the cache."""
        if self._mode == CacheMode.OFF:
            return

        if isinstance(image_data, np.ndarray):
            byte_size = image_data.nbytes
        elif isinstance(image_data, tuple):
            byte_size = sum(x.nbytes for x in image_data if isinstance(x, np.ndarray))
        else:
            return

        # In Region mode, do not cache frames outside [in_frame, out_frame] unless it's playhead
        if self._mode == CacheMode.REGION and self._in_frame is not None and self._out_frame is not None:
            if not (self._in_frame <= frame <= self._out_frame) and frame != self._current_playhead:
                return

        key = (self._active_source_id, frame) if self._active_source_id else frame
        with self._lock:
            if key in self._frames:
                self._used_bytes -= self._frame_bytes[key]

            self._frames[key] = image_data
            self._frame_bytes[key] = byte_size
            self._used_bytes += byte_size

            self._refresh_auto_budget_locked()
            self._evict_if_needed(self._current_playhead)

        self._emit_status()

    def clear(self) -> None:
        """Clear all cached frames from memory."""
        with self._lock:
            self._frames.clear()
            self._frame_bytes.clear()
            self._frame_mtimes.clear()
            self._used_bytes = 0
            self._layer_cache.clear()
            self._layer_bytes.clear()
            self._layer_used_bytes = 0
        self._emit_status()

    def update_playhead(self, playhead: int) -> None:
        """Inform the cache of the current playhead position to prioritize prefetch/retention."""
        self._current_playhead = playhead

    def get_cached_frames(self) -> Set[int]:
        """Return cached frame numbers for the active source context or flat keys."""
        with self._lock:
            out = set()
            for k in self._frames.keys():
                if isinstance(k, tuple):
                    if not self._active_source_id or k[0] == self._active_source_id:
                        out.add(k[1])
                elif isinstance(k, int):
                    out.add(k)
            return out

    def get_prefetch_targets(
        self,
        start_frame: int,
        end_frame: int,
        in_frame: Optional[int] = None,
        out_frame: Optional[int] = None,
    ) -> Tuple[int, int]:
        """
        Get the desired prefetch window [window_start, window_end] clamped to sequence bounds.
        Returns (0, -1) when caching is OFF.
        """
        if self._mode == CacheMode.OFF:
            return 0, -1

        inf = in_frame if in_frame is not None else (self._in_frame if self._in_frame is not None else start_frame)
        outf = out_frame if out_frame is not None else (self._out_frame if self._out_frame is not None else end_frame)

        if self._mode == CacheMode.REGION:
            # Cache In and Out region only
            return max(start_frame, inf), min(end_frame, outf)

        if self._mode == CacheMode.ALL:
            return start_frame, end_frame

        # CacheMode.PLAY_AHEAD (Lookahead around current playhead)
        window_start = max(start_frame, self._current_playhead - self._lookbehind)
        window_end = min(end_frame, self._current_playhead + self._lookahead)
        return window_start, window_end

    def get_memory_stats(self) -> Tuple[float, float, float]:
        """Return (used_mb, max_mb, percent_used)."""
        with self._lock:
            used_mb = self._used_bytes / (1024.0 * 1024.0)
            max_mb = self._max_memory_bytes / (1024.0 * 1024.0)
            pct = (self._used_bytes / self._max_memory_bytes) * 100.0 if self._max_memory_bytes > 0 else 0.0
            return used_mb, max_mb, pct

    # --------------------------------------------------------------------------
    # Internal Eviction
    # --------------------------------------------------------------------------
    def _evict_if_needed(self, playhead: int) -> None:
        """Must be called while self._lock is acquired."""
        if self._used_bytes <= self._max_memory_bytes:
            return

        def _get_frame_num(key: Any) -> int:
            if isinstance(key, tuple):
                return key[1]
            return int(key)

        def _is_active_source(key: Any) -> bool:
            if isinstance(key, tuple) and self._active_source_id:
                return key[0] == self._active_source_id
            return True

        def _eviction_priority(k: Any) -> tuple:
            f = _get_frame_num(k)
            # 1. Out of region frames evicted first in REGION mode
            in_region = 1
            if self._mode == CacheMode.REGION and self._in_frame is not None and self._out_frame is not None:
                in_region = 0 if (self._in_frame <= f <= self._out_frame) else 1

            # 2. Inactive source frames evicted before active source
            is_active = 0 if _is_active_source(k) else 1

            # 3. Directional distance: frames behind playhead evicted before upcoming lookahead frames
            diff = f - playhead
            if diff < 0:
                dist_score = 100000 + abs(diff)  # Behind playhead: high priority to evict
            else:
                dist_score = diff                # Ahead of playhead: evict furthest ahead first

            return (in_region, is_active, dist_score)

        candidates = sorted(
            self._frames.keys(),
            key=_eviction_priority,
            reverse=True,
        )

        for k in candidates:
            if self._used_bytes <= self._max_memory_bytes:
                break
            frame_num = _get_frame_num(k)
            # Do not evict the exact current playhead frame of active source if possible
            if frame_num == playhead and _is_active_source(k) and len(self._frames) > 1:
                continue

            b = self._frame_bytes.pop(k, 0)
            self._frames.pop(k, None)
            self._used_bytes -= b

    def _emit_status(self) -> None:
        used_mb, max_mb, _ = self.get_memory_stats()
        self.cache_changed.emit()
        self.memory_usage_changed.emit(used_mb, max_mb)
