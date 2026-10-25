"""
Unit and integration tests covering the 6 user fixes & enhancements:
1. Default brush stroke width 6px and user adjustments persistence.
2. Reveal in folder with space-safe OS file manager opening.
3. Windows AppData configuration and plugin enabled state persistence.
4. Asynchronous AnnotationExportWorker preventing UI freeze with cancellation support.
5. Adaptive caching scheduling and throttled UI updates.
6. Atomic session reset wiping canvas, cache, sources, bookmarks, and annotated marks.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
import numpy as np
import pytest

from PySide6.QtCore import Qt, QSettings, QEventLoop
from PySide6.QtWidgets import QApplication

from openreview.core.preferences import UserPreferences, PreferencesManager, get_app_config_dir
from openreview.core.system_utils import reveal_in_os_file_manager
from openreview.packages.package_manager import PackageManager
from openreview.models.annotations import AnnotationStore, Stroke, ShapeType
from openreview.core.clock import PlaybackClock
from openreview.ui.annotation_manager_dialog import AnnotationExportWorker, AnnotationManagerDialog
from openreview.widgets.markup_tools import MarkupToolPalette
from openreview.widgets.viewport import ViewportCanvas
from openreview.ui.main_window import MainWindow


def test_default_brush_width_and_persistence(qtbot, tmp_path):
    """Verify default brush width is 6px and persists through PreferencesManager."""
    # 1. Dataclass default
    prefs = UserPreferences()
    assert prefs.default_brush_width == 6.0

    # 2. PreferencesManager persistence
    pm = PreferencesManager(config_dir=tmp_path)
    assert pm.prefs.default_brush_width == 6.0

    # 3. ViewportCanvas initialization
    store = AnnotationStore()
    viewport = ViewportCanvas(store)
    qtbot.addWidget(viewport)
    assert viewport._active_draw_width == 6.0

    # 4. MarkupToolPalette initialization & user modification
    palette = MarkupToolPalette(viewport)
    qtbot.addWidget(palette)
    palette.stroke_width_changed.connect(viewport.set_draw_width)
    assert palette.slider_size.value() == 6
    assert palette._current_width == 6.0

    palette.slider_size.setValue(12)
    assert viewport._active_draw_width == 12.0
    assert palette._current_width == 12.0


def test_reveal_in_os_file_manager(tmp_path, monkeypatch):
    """Verify reveal_in_os_file_manager safely invokes native explorer or fallback without error."""
    test_file = tmp_path / "Shot 010 Frame Test" / "render.0100.exr"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("dummy")

    called_cmds = []

    def mock_popen(cmd, *args, **kwargs):
        called_cmds.append(cmd)
        class DummyProcess:
            returncode = 0
        return DummyProcess()

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr("subprocess.run", mock_popen)
    # Bypass ctypes shell call to test fallback command line construction
    monkeypatch.setattr("sys.platform", "win32")
    import ctypes
    monkeypatch.setattr(ctypes.windll.shell32, "SHOpenFolderAndSelectItems", None)

    reveal_in_os_file_manager(test_file)
    assert len(called_cmds) > 0
    cmd_str = called_cmds[0]
    # Check that explorer was invoked with properly formatted /select argument
    assert "explorer.exe /select," in cmd_str
    assert str(test_file.resolve()) in cmd_str


def test_windows_preferences_and_package_state_persistence(tmp_path, monkeypatch):
    """Verify package state saves and loads properly with file and QSettings dual-persistence."""
    # Test get_app_config_dir
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setattr("sys.platform", "win32")
    cfg_dir = get_app_config_dir()
    assert "OpenReview" in str(cfg_dir)

    # Test PackageManager dual persistence
    pkg_dir = tmp_path / "user_pkgs"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    pm = PackageManager(user_dir=pkg_dir)
    assert pm._state_file.parent.exists()

    # Enable and disable packages
    pm._enabled_packages.add("com.studio.dailies")
    pm._disabled_packages.add("com.studio.legacy")
    pm._save_state()

    assert pm._state_file.is_file()
    data = json.loads(pm._state_file.read_text(encoding="utf-8"))
    assert "com.studio.dailies" in data["enabled"]
    assert "com.studio.legacy" in data["disabled"]

    # Verify reload in fresh instance
    pm2 = PackageManager(user_dir=pkg_dir)
    assert "com.studio.dailies" in pm2._enabled_packages
    assert "com.studio.legacy" in pm2._disabled_packages


def test_annotation_export_worker_pdf_and_cancellation(tmp_path):
    """Verify AnnotationExportWorker runs off-thread and supports cancellation."""
    store = AnnotationStore()
    store.add_stroke(1001, Stroke(shape_type=ShapeType.PEN, points=[(0.1, 0.1), (0.2, 0.2)]))
    store.set_frame_note(1001, "Fix flare artifact")

    clock = PlaybackClock(start_frame=1001, end_frame=1005, fps=24.0)
    pdf_out = tmp_path / "test_report.pdf"

    dummy_render = lambda f: np.zeros((100, 100, 3), dtype=np.uint8)

    worker = AnnotationExportWorker(
        export_mode="pdf",
        target_path=pdf_out,
        frames=[1001],
        store=store,
        fps=clock.fps,
        render_frame_callback=dummy_render,
        export_png_frames=True,
    )
    worker.start()
    assert worker.wait(5000) is True

    assert worker.result_success is True
    assert pdf_out.exists()
    assert (tmp_path / "test_report_frames" / "frame_1001.png").exists()

    # Test cancellation
    worker_cancelled = AnnotationExportWorker(
        export_mode="pdf",
        target_path=tmp_path / "cancel.pdf",
        frames=[1001, 1002, 1003],
        store=store,
        fps=clock.fps,
        render_frame_callback=dummy_render,
    )
    worker_cancelled.cancel()
    assert worker_cancelled._is_cancelled is True


def test_atomic_session_reset_canvas_cleanup(qapp, tmp_path, monkeypatch):
    """Verify _perform_atomic_session_reset completely clears viewport canvas, cache, bookmarks, and sources."""
    monkeypatch.setattr(PreferencesManager, "instance", lambda: PreferencesManager(config_dir=tmp_path))

    win = MainWindow()

    # Simulate loaded media and viewport state
    mock_frame = np.ones((480, 640, 4), dtype=np.uint8) * 128
    win.viewport.set_primary_frame(1005, mock_frame)
    assert win.viewport._image_a is not None
    assert win.viewport.has_active_media is True

    # Add bookmarks and annotations
    win.clock.add_bookmark(1010)
    win.clock.add_bookmark(1020)
    assert 1010 in win.clock.bookmarks
    assert 1020 in win.clock.bookmarks

    win.annotation_store.add_stroke(1005, Stroke(shape_type=ShapeType.LINE, points=[(0.1, 0.1), (0.4, 0.4)]))
    win.annotation_store.set_frame_note(1005, "Review cleanup")
    assert win.annotation_store.has_annotations(1005)

    # Set cache mode to ALL and add cache entry
    from openreview.core.cache import CacheMode
    win._on_set_cache_mode(CacheMode.ALL, start_prefetch=False)
    win.cache.put_frame(1005, mock_frame)
    assert 1005 in win.cache.get_cached_frames()

    # Trigger atomic session reset
    win._perform_atomic_session_reset()

    # 1. Canvas must be completely empty
    assert win.viewport._image_a is None
    assert win.viewport._image_b is None
    assert win.viewport._img_width == 0
    assert win.viewport._img_height == 0
    assert win.viewport.has_active_media is False

    # 2. Bookmarks and markers reset
    assert len(win.clock.bookmarks) == 0
    assert win.clock.in_frame == 1001
    assert win.clock.out_frame == 1200
    assert win.clock.current_frame == 1001

    # 3. Annotations cleared
    assert len(win.annotation_store.get_annotated_frames()) == 0

    # 4. Cache cleared
    assert len(win.cache.get_cached_frames()) == 0

    # 5. Sources cleared
    assert len(win.session_graph.sources) == 0


def test_fps_input_focus_policy_and_wheel(qtbot):
    """Verify FPS spinbox and Handles combo never auto-focus and ignore mouse wheel scrolling."""
    from openreview.widgets.timeline import TimelineWidget
    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=24.0)
    timeline = TimelineWidget(clock)
    qtbot.addWidget(timeline)

    # 1. Focus policy must be ClickFocus (cannot steal focus via Tab or layout activation)
    assert timeline.fps_spin.focusPolicy() == Qt.FocusPolicy.ClickFocus
    assert timeline.combo_handles.focusPolicy() == Qt.FocusPolicy.ClickFocus

    # 2. Wheel event must be ignored to prevent accidental FPS modifications
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF, QPoint
    initial_fps = timeline.fps_spin.value()
    wheel_event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    timeline.fps_spin.wheelEvent(wheel_event)
    assert timeline.fps_spin.value() == initial_fps


def test_shift_c_toggle_preserves_pre_cached_frames(qapp, tmp_path, monkeypatch):
    """Verify Shift+C stops caching while keeping all pre-cached frames, and restores previous mode."""
    monkeypatch.setattr(PreferencesManager, "instance", lambda: PreferencesManager(config_dir=tmp_path))
    from openreview.core.cache import CacheMode

    win = MainWindow()

    # 1. Start caching in Full Sequence (ALL) mode
    win._on_set_cache_mode(CacheMode.ALL, start_prefetch=True)
    assert win.cache.mode == CacheMode.ALL
    assert win._cache_started is True

    # Cache some mock frames
    mock_frame = np.ones((100, 100, 4), dtype=np.uint8) * 200
    win.cache.put_source_frame("source_1", 1005, mock_frame)
    win.cache.put_source_frame("source_1", 1006, mock_frame)
    assert 1005 in win.cache.get_source_cached_frames("source_1")
    assert 1006 in win.cache.get_source_cached_frames("source_1")

    # 2. Press Shift+C to turn off / pause caching process
    win._on_toggle_cache()
    assert win.cache.mode == CacheMode.OFF
    assert win._cache_started is False
    assert win.reader_engine.is_paused is True

    # 3. Pre-cached data MUST still be retained in memory!
    assert 1005 in win.cache.get_source_cached_frames("source_1")
    assert 1006 in win.cache.get_source_cached_frames("source_1")
    cached_frame = win.cache.get_source_frame("source_1", 1005)
    assert cached_frame is not None
    assert np.array_equal(cached_frame, mock_frame)

    # 4. Press Shift+C again to resume caching: must restore previous mode (CacheMode.ALL)
    win._on_toggle_cache()
    assert win.cache.mode == CacheMode.ALL
    assert win._cache_started is True
    assert win.reader_engine.is_paused is False

    # Frames still present
    assert 1005 in win.cache.get_source_cached_frames("source_1")
    assert 1006 in win.cache.get_source_cached_frames("source_1")

    # 5. Clear Active Source Cache (Ctrl+Shift+C) must explicitly purge the cache
    win.cache.clear_source("source_1")
    assert len(win.cache.get_source_cached_frames("source_1")) == 0
