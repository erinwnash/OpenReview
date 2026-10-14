import pytest
from openreview.core.clock import PlaybackClock
from openreview.models.annotations import AnnotationStore, ShapeType, Stroke


def test_bookmark_operations():
    clock = PlaybackClock(start_frame=1, end_frame=100)
    assert len(clock.bookmarks) == 0

    # Toggle bookmark at current frame
    clock.set_frame(15)
    added = clock.toggle_bookmark()
    assert added is True
    assert 15 in clock.bookmarks

    # Toggle off
    removed = clock.toggle_bookmark()
    assert removed is False
    assert 15 not in clock.bookmarks

    # Add specific frames
    clock.add_bookmark(20)
    clock.add_bookmark(50)
    clock.add_bookmark(80)
    assert clock.bookmarks == {20, 50, 80}

    # Clear all bookmarks
    clock.clear_all_bookmarks()
    assert len(clock.bookmarks) == 0


def test_marker_jumping():
    clock = PlaybackClock(start_frame=1, end_frame=100)
    clock.set_bookmarks([10, 30, 70])
    clock.set_frame(1)

    # Next marker
    nxt = clock.next_marker(direction=1)
    assert nxt == 10
    assert clock.current_frame == 10

    nxt = clock.next_marker(direction=1)
    assert nxt == 30
    assert clock.current_frame == 30

    nxt = clock.next_marker(direction=1)
    assert nxt == 70
    assert clock.current_frame == 70

    # Wrap forward
    nxt = clock.next_marker(direction=1)
    assert nxt == 10
    assert clock.current_frame == 10

    # Previous marker (wrap backward)
    prv = clock.next_marker(direction=-1)
    assert prv == 70
    assert clock.current_frame == 70

    prv = clock.next_marker(direction=-1)
    assert prv == 30
    assert clock.current_frame == 30


def test_combined_marker_navigation_with_annotations():
    clock = PlaybackClock(start_frame=1, end_frame=100)
    clock.set_bookmarks([10, 50])
    extra_annotated = {25, 75}

    clock.set_frame(1)

    # 1 -> 10 (bookmark)
    assert clock.next_marker(extra_markers=extra_annotated, direction=1) == 10
    # 10 -> 25 (annotation)
    assert clock.next_marker(extra_markers=extra_annotated, direction=1) == 25
    # 25 -> 50 (bookmark)
    assert clock.next_marker(extra_markers=extra_annotated, direction=1) == 50
    # 50 -> 75 (annotation)
    assert clock.next_marker(extra_markers=extra_annotated, direction=1) == 75
    # 75 -> wrap to 10
    assert clock.next_marker(extra_markers=extra_annotated, direction=1) == 10


def test_range_clearing_and_boundary_marking():
    clock = PlaybackClock(start_frame=1001, end_frame=1100)
    clock.set_in_out(1020, 1080)
    assert clock.in_frame == 1020
    assert clock.out_frame == 1080

    clock.clear_in_mark()
    assert clock.in_frame == 1001
    assert clock.out_frame == 1080

    clock.set_in_mark(1030)
    clock.clear_out_mark()
    assert clock.in_frame == 1030
    assert clock.out_frame == 1100

    clock.mark_sequence_boundaries()
    assert clock.in_frame == 1001
    assert clock.out_frame == 1100
