"""
Tests for Canvas Empty State, Close Session Purge, Quick Grade HUD,
Photoshop-style Floating HUD Resizing, and Frame-Accurate Playback Timing.
"""
import pytest
import numpy as np
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QSizeGrip, QWidget
from openreview.ui.main_window import MainWindow
from openreview.core.clock import PlaybackClock
from openreview.core.cache import CacheMode
from openreview.widgets.floating_hud import FloatingHUDCard


def test_empty_canvas_state_on_startup(qtbot):
    """Verify canvas starts clean without default colorbars and with empty state label."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.reader is None
    assert window.viewport._image_a is None
    assert window.viewport._texture_a is None
    assert window.resolution_status_label.text() == "No Media"


def test_close_session_clears_everything(qtbot):
    """Verify Close Session completely purges canvas, textures, cache, annotations, audio."""
    window = MainWindow()
    qtbot.addWidget(window)

    # 1. Put some dummy data in canvas, cache, annotations, and bookmarks
    dummy_frame = np.ones((64, 64, 4), dtype=np.float32)
    window.viewport.set_primary_frame(1050, dummy_frame)
    window.cache.set_mode(CacheMode.ALL)
    window.cache.put_frame(1050, dummy_frame)
    window.clock.set_bookmarks([1010, 1020])
    window.clock.set_in_out(1015, 1080)
    window.top_bar.spin_exposure.setValue(2.0)

    assert window.viewport._image_a is not None
    assert window.cache.has_frame(1050)
    assert len(window.clock.bookmarks) == 2

    # 2. Invoke close session without prompt dialog
    window._on_close_session(prompt=False)

    # 3. Verify total canvas and session purge
    assert window.reader is None
    assert window.viewport._image_a is None
    assert window.viewport._texture_a is None
    assert len(window.cache.get_cached_frames()) == 0
    assert len(window.clock.bookmarks) == 0
    assert window.clock.start_frame == 1001
    assert window.clock.end_frame == 1200
    assert window.clock.in_frame == 1001
    assert window.top_bar.gain == 1.0
    assert window.top_bar.exposure_ev == 0.0
    assert window.resolution_status_label.text() == "No Media"


def test_floating_hud_resizing_and_size_grip(qtbot):
    """Test Photoshop-style border dragging and QSizeGrip resizing on FloatingHUDCard."""
    content = QWidget()
    hud = FloatingHUDCard("Test HUD", content)
    qtbot.addWidget(hud)
    hud.resize(300, 150)
    hud.show()

    # 1. SizeGrip presence
    assert hud.size_grip is not None
    assert isinstance(hud.size_grip, QSizeGrip)

    # 2. Resize zone detection
    assert hud._get_resize_zone(QPoint(2, 50)) == "left"
    assert hud._get_resize_zone(QPoint(298, 50)) == "right"
    assert hud._get_resize_zone(QPoint(150, 2)) == "top"
    assert hud._get_resize_zone(QPoint(150, 148)) == "bottom"
    assert hud._get_resize_zone(QPoint(298, 148)) == "bottom_right"

    # 3. Simulate border drag resizing
    initial_w = hud.width()
    hud._resize_zone = "right"
    hud._resize_start_pos = QPoint(300, 150)
    hud._resize_start_geom = hud.geometry()

    # Move mouse 50px to the right
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent
    move_ev = QMouseEvent(
        QEvent.Type.MouseMove,
        QPoint(350, 150),
        QPoint(350, 150),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    hud.mouseMoveEvent(move_ev)
    assert hud.width() == initial_w + 50

    # Release
    release_ev = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPoint(350, 150),
        QPoint(350, 150),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    hud.mouseReleaseEvent(release_ev)
    assert hud._resize_zone == "none"


def test_frame_accurate_playback_clock_timing(qtbot):
    """Test that PlaybackClock defaults to play_all_frames and advances frame-by-frame with PreciseTimer."""
    clock = PlaybackClock(start_frame=1, end_frame=100, fps=24.0)
    assert clock.play_all_frames is True

    # High precision timer check
    assert clock._timer.timerType() == Qt.TimerType.PreciseTimer

    # Test advancing frames in play_all_frames mode
    clock.set_current_frame(1)
    clock.play()
    assert clock.is_playing is True

    # Simulate elapsed time of 1 frame (41.67ms = 41_666_667 ns)
    clock._last_tick_time_ns = 0
    clock._accumulated_ns = 0.0
    frame_ns = 1_000_000_000.0 / 24.0

    # Advance clock by 1 frame duration
    clock._accumulated_ns = frame_ns + 1000
    clock._on_tick()

    # Must advance exactly 1 frame without dropping
    assert clock.current_frame == 2

    # If delay occurs (e.g. 2.5 frame durations backlog), play_all_frames still advances 1 frame cleanly
    clock._accumulated_ns = frame_ns * 2.5
    clock._on_tick()
    assert clock.current_frame == 3

    # Clamping prevents catchup surge
    assert clock._accumulated_ns <= frame_ns

    clock.pause()
    assert clock.is_playing is False
