import os
import json
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from openreview.models.session import (
    OpenReviewSession,
    ViewportSessionState,
    ColorSessionState,
    MatteSessionState,
)
from openreview.ui.main_window import MainWindow


def test_session_serialization_roundtrip(tmp_path):
    sess = OpenReviewSession(
        media_path="/path/to/shot.0100.exr",
        media_type="sequence",
        start_frame=100,
        end_frame=250,
        in_frame=120,
        out_frame=200,
        current_frame=150,
        fps=29.97,
        loop_mode="ping_pong",
        bookmarks=[110, 150, 190],
        background_mode="checker",
        viewport=ViewportSessionState(
            zoom=2.5,
            pan_x=120.0,
            pan_y=-45.0,
            flip_x=True,
            flip_y=False,
            rotation=90,
            pixel_aspect_ratio=2.0,
            texture_filtering="nearest",
        ),
        color=ColorSessionState(
            exposure_ev=1.5,
            gamma=0.9,
            channel_mode=1,
            input_space=1,
            view_transform=1,
        ),
        matte=MatteSessionState(
            ratio=2.35,
            opacity=0.75,
        ),
        annotations={"150": [{"type": "pen", "points": [[0.1, 0.2], [0.3, 0.4]]}]},
    )

    save_path = tmp_path / "test_session.ovr"
    sess.save_to_file(save_path)
    assert save_path.exists()

    loaded = OpenReviewSession.load_from_file(save_path)
    assert loaded.media_path == "/path/to/shot.0100.exr"
    assert loaded.start_frame == 100
    assert loaded.end_frame == 250
    assert loaded.in_frame == 120
    assert loaded.out_frame == 200
    assert loaded.current_frame == 150
    assert loaded.fps == 29.97
    assert loaded.loop_mode == "ping_pong"
    assert loaded.bookmarks == [110, 150, 190]
    assert loaded.background_mode == "checker"

    assert loaded.viewport.zoom == 2.5
    assert loaded.viewport.flip_x is True
    assert loaded.viewport.rotation == 90
    assert loaded.viewport.pixel_aspect_ratio == 2.0
    assert loaded.viewport.texture_filtering == "nearest"

    assert loaded.color.exposure_ev == 1.5
    assert loaded.color.gamma == 0.9
    assert loaded.color.channel_mode == 1

    assert loaded.matte.ratio == 2.35
    assert loaded.matte.opacity == 0.75
    assert "150" in loaded.annotations


def test_main_window_session_apply(qapp, tmp_path):
    win = MainWindow()

    sess = OpenReviewSession(
        media_path=None,
        media_type="none",
        start_frame=1,
        end_frame=50,
        in_frame=5,
        out_frame=40,
        current_frame=20,
        fps=48.0,
        loop_mode="loop",
        bookmarks=[10, 20, 30],
        background_mode="grey50",
        viewport=ViewportSessionState(
            zoom=1.5,
            pan_x=10.0,
            pan_y=20.0,
            flip_x=True,
            flip_y=True,
            rotation=180,
            pixel_aspect_ratio=1.333,
        ),
        color=ColorSessionState(
            exposure_ev=0.5,
            gamma=1.2,
            channel_mode=2,
        ),
        matte=MatteSessionState(
            ratio=1.85,
            opacity=0.5,
        ),
    )

    save_path = tmp_path / "workspace.ovr"
    sess.save_to_file(save_path)

    win._apply_session(sess)

    assert win.clock.start_frame == 1
    assert win.clock.end_frame == 50
    assert win.clock.in_frame == 5
    assert win.clock.out_frame == 40
    assert win.clock.current_frame == 20
    assert win.clock.fps == 48.0
    assert win.clock.bookmarks == {10, 20, 30}

    assert win.viewport.flip_x is True
    assert win.viewport.flip_y is True
    assert win.viewport.rotation == 180
    assert abs(win.viewport.pixel_aspect_ratio - 1.333) < 0.001
    assert win.viewport.background_mode == "grey50"

    assert abs(win.top_bar.exposure_ev - 0.5) < 0.01
    assert abs(win.top_bar.gamma - 1.2) < 0.01
    assert win.top_bar.channel_mode == 2

    assert abs(win.viewport.matte_ratio - 1.85) < 0.01
    assert abs(win.viewport.matte_opacity - 0.5) < 0.01

    # Test building current session matches state
    built = win._build_current_session()
    assert built.start_frame == 1
    assert built.current_frame == 20
    assert built.viewport.rotation == 180
    assert set(built.bookmarks) == {10, 20, 30}

    win.close()
