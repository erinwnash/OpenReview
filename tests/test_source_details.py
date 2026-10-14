"""
Unit & Integration Tests for Source Media Details Panel and Metadata Extraction.
"""
import os
import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication

from openreview.core.metadata import extract_media_metadata
from openreview.ui.image_info_dialog import ImageInfoWidget, ImageInfoDialog
from openreview.ui.main_window import MainWindow


def test_extract_media_metadata(tmp_path):
    # Test non-existent file
    m_empty = extract_media_metadata("")
    assert m_empty["file_name"] == "Synthetic Stream"

    # Test synthetic video file
    vid_path = str(tmp_path / "metadata_test.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(vid_path, fourcc, 25.0, (160, 90))
    for _ in range(10):
        writer.write(np.zeros((90, 160, 3), dtype=np.uint8))
    writer.release()

    meta = extract_media_metadata(vid_path)
    assert meta["file_name"] == "metadata_test.mp4"
    assert meta["width"] == 160
    assert meta["height"] == 90
    assert meta["file_size_bytes"] > 0
    assert "file_size_str" in meta


def test_image_info_widget_dynamic_refresh(qtbot):
    info1 = {
        "file_path": "shot10.mp4",
        "media_type": "Video",
        "width": 1920,
        "height": 1080,
        "video_codec": "H.264 / AVC",
        "fps": 24.0,
    }
    w = ImageInfoWidget(info1)
    qtbot.addWidget(w)
    w.resize(480, 560)
    w.show()

    assert w.isVisible()
    assert w._scroll_area.widget() is not None

    # Test update_info dynamic refresh (verifying layout bug is resolved)
    info2 = {
        "file_path": "comp_v002.exr",
        "media_type": "EXR Sequence",
        "width": 3840,
        "height": 2160,
        "video_codec": "OpenEXR (DWAA)",
        "audio_codec": "AAC Stereo",
        "audio_sample_rate": "48000",
        "fps": 25.0,
    }
    w.update_info(info2)
    assert w._scroll_area.widget() is not None
    assert w._scroll_area.widget().height() > 100


def test_main_window_source_details_toggle(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.resize(1280, 720)
    win.show()

    # Starts hidden
    assert win.hud_source_details.isHidden()

    # Press 'I' shortcut to toggle
    win._on_toggle_source_details()
    assert win.hud_source_details.isVisible()
    assert win.hud_source_details.width() >= 440
    assert win.hud_source_details.height() >= 480

    # Toggle off
    win._on_toggle_source_details()
    assert win.hud_source_details.isHidden()
