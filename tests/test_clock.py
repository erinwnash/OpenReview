"""
Unit tests for PlaybackClock.
"""
import pytest
from openreview.core.clock import PlaybackClock


def test_clock_initial_state(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=24.0)
    assert clock.current_frame == 1001
    assert clock.start_frame == 1001
    assert clock.end_frame == 1100
    assert clock.in_frame == 1001
    assert clock.out_frame == 1100
    assert clock.fps == 24.0
    assert not clock.is_playing


def test_clock_step_forward_and_backward(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100)
    
    clock.step_forward(1)
    assert clock.current_frame == 1002

    clock.step_forward(10)
    assert clock.current_frame == 1012

    clock.step_backward(2)
    assert clock.current_frame == 1010

    clock.first_frame()
    assert clock.current_frame == 1001

    clock.last_frame()
    assert clock.current_frame == 1100


def test_clock_in_out_boundaries(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100)
    clock.set_in_out(1020, 1080)
    assert clock.in_frame == 1020
    assert clock.out_frame == 1080

    clock.set_frame(1080)
    clock.step_forward(1)
    # Should wrap to in_frame
    assert clock.current_frame == 1020

    clock.step_backward(1)
    # Should wrap to out_frame
    assert clock.current_frame == 1080


def test_clock_play_pause(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=60.0)
    clock.play()
    assert clock.is_playing

    clock.pause()
    assert not clock.is_playing

    clock.toggle_playback()
    assert clock.is_playing
    clock.toggle_playback()
    assert not clock.is_playing


def test_clock_clear_in_out(qtbot):
    clock = PlaybackClock(start_frame=1001, end_frame=1100)
    clock.set_in_out(1020, 1080)
    assert clock.in_frame == 1020
    assert clock.out_frame == 1080

    clock.clear_in_out()
    assert clock.in_frame == 1001
    assert clock.out_frame == 1100


def test_clock_shuttle_forward_tiers(qtbot):
    clock = PlaybackClock(start_frame=1, end_frame=100, fps=24.0)
    assert not clock.is_playing
    assert clock.shuttle_speed == 1.0

    # First press of L starts playback at 1x
    clock.shuttle_forward()
    assert clock.is_playing
    assert clock.shuttle_speed == 1.0

    # Subsequent presses accelerate: 2x -> 4x -> 8x
    clock.shuttle_forward()
    assert clock.shuttle_speed == 2.0

    clock.shuttle_forward()
    assert clock.shuttle_speed == 4.0

    clock.shuttle_forward()
    assert clock.shuttle_speed == 8.0

    # Capped at 8x
    clock.shuttle_forward()
    assert clock.shuttle_speed == 8.0


def test_clock_shuttle_reverse_and_stop(qtbot):
    clock = PlaybackClock(start_frame=1, end_frame=100, fps=24.0)

    # First press of J starts reverse playback at -1x
    clock.shuttle_reverse()
    assert clock.is_playing
    assert clock.shuttle_speed == -1.0

    # Accelerate in reverse: -2x -> -4x -> -8x
    clock.shuttle_reverse()
    assert clock.shuttle_speed == -2.0

    clock.shuttle_reverse()
    assert clock.shuttle_speed == -4.0

    clock.shuttle_reverse()
    assert clock.shuttle_speed == -8.0

    # Stop resets to 1x and pauses
    clock.shuttle_stop()
    assert not clock.is_playing
    assert clock.shuttle_speed == 1.0


def test_clock_loop_mode_cycle(qtbot):
    clock = PlaybackClock(start_frame=1, end_frame=100)
    assert clock.loop_mode == "cycle"

    next_mode = clock.cycle_loop_mode()
    assert next_mode == "ping-pong"
    assert clock.loop_mode == "ping-pong"

    next_mode = clock.cycle_loop_mode()
    assert next_mode == "once"
    assert clock.loop_mode == "once"

    next_mode = clock.cycle_loop_mode()
    assert next_mode == "cycle"
    assert clock.loop_mode == "cycle"

