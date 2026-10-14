"""
Performance & Integration Tests for Fast Video Playback Pipeline.
Verifies asynchronous lookahead prefetching, non-blocking frame delivery,
and native uint8 RGBA8 texture upload for smooth real-time playback.
"""
import os
import cv2
import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from openreview.core.video_reader import VideoMediaReader
from openreview.widgets.viewport import ViewportCanvas


def test_video_reader_lookahead_performance(tmp_path):
    vid_path = str(tmp_path / "speed_test.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(vid_path, fourcc, 25.0, (320, 180))
    for i in range(30):
        img = np.zeros((180, 320, 3), dtype=np.uint8)
        img[:, :] = (i * 8, 120, 180)
        writer.write(img)
    writer.release()

    reader = VideoMediaReader(vid_path, buffer_size=16)
    assert reader.total_frames >= 30

    # Sequential playback: Frames should be served near-instantly from lookahead buffer
    times = []
    for f in range(1, 16):
        t0 = time.perf_counter()
        data = reader.read_frame(f)
        dt = (time.perf_counter() - t0) * 1000.0
        times.append(dt)
        assert data is not None
        assert data.dtype == np.uint8
        assert data.shape == (180, 320, 4)

    avg_ms = sum(times) / len(times)
    # Average read time during sequential streaming must be well under 25ms budget
    assert avg_ms < 25.0

    # Random Seek test
    t_seek0 = time.perf_counter()
    seek_data = reader.read_frame(25)
    t_seek = (time.perf_counter() - t_seek0) * 1000.0
    assert seek_data is not None
    assert seek_data.shape == (180, 320, 4)

    # Next frame after seek should continue smoothly
    next_data = reader.read_frame(26)
    assert next_data is not None

    reader.close()


def test_viewport_uint8_rgba8_unorm_upload(qtbot):
    viewport = ViewportCanvas()
    qtbot.addWidget(viewport)
    viewport.resize(640, 360)
    viewport.show()

    test_frame = np.full((180, 320, 4), 200, dtype=np.uint8)
    viewport.set_primary_frame(1, test_frame)

    assert viewport._image_a is not None
    assert viewport._image_a.dtype == np.uint8

    # Trigger texture upload
    viewport._upload_texture_a()
    assert viewport._texture_a is not None
    assert viewport._texture_a.isCreated()
    assert viewport._texture_a.width() == 320
    assert viewport._texture_a.height() == 180
