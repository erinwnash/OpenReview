"""
Tests for comprehensive VFX metadata extraction, OpenEXR specifications,
metadata table search filter, clipboard copying, JSON export, and dynamic per-frame updates.
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock
import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence, QKeyEvent
from PySide6.QtWidgets import QApplication

from openreview.core.metadata import extract_media_metadata
from openreview.ui.image_info_dialog import ImageInfoWidget, ImageInfoDialog, MetaTableWidget


def _create_synthetic_exr(filepath: str, width: int = 64, height: int = 48):
    """Helper to create a valid synthetic OpenEXR file with header attributes."""
    import OpenEXR
    import Imath

    header = OpenEXR.Header(width, height)
    header["dataWindow"] = Imath.Box2i(Imath.V2i(0, 0), Imath.V2i(width - 1, height - 1))
    header["displayWindow"] = Imath.Box2i(Imath.V2i(0, 0), Imath.V2i(width - 1, height - 1))
    header["compression"] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)
    header["pixelAspectRatio"] = 1.0

    zero_chan = np.zeros((height, width), dtype=np.float32).tobytes()
    out = OpenEXR.OutputFile(filepath, header)
    out.writePixels({"R": zero_chan, "G": zero_chan, "B": zero_chan})
    out.close()


def test_exr_metadata_extraction(tmp_path):
    exr_file = str(tmp_path / "shot_010.0050.exr")
    _create_synthetic_exr(exr_file, width=120, height=80)

    meta = extract_media_metadata(exr_file)
    assert meta["width"] == 120
    assert meta["height"] == 80
    assert "exr_details" in meta
    exr = meta["exr_details"]
    assert exr["compression"] == "ZIP_COMPRESSION"
    assert tuple(exr["display_window"]) == (0, 0, 119, 79)
    assert tuple(exr["data_window"]) == (0, 0, 119, 79)
    assert len(exr["channels"]) == 3

    # Check all_metadata_tags aggregation
    tags = meta.get("all_metadata_tags", {})
    assert "exr:displayWindow" in tags
    assert "exr:dataWindow" in tags
    assert "exr:compression" in tags
    assert "exr:channels" in tags


def test_sequence_pattern_resolution(tmp_path):
    exr_file = str(tmp_path / "render.0101.exr")
    _create_synthetic_exr(exr_file, width=64, height=36)

    # Resolve using hash pattern
    meta = extract_media_metadata(str(tmp_path / "render.####.exr"))
    assert meta["width"] == 64
    assert meta["height"] == 36
    assert tuple(meta["exr_details"]["display_window"]) == (0, 0, 63, 35)

    # Resolve using printf pattern
    meta_printf = extract_media_metadata(str(tmp_path / "render.%04d.exr"))
    assert meta_printf["width"] == 64
    assert meta_printf["height"] == 36


def test_image_info_widget_exr_card_and_table(qtbot, monkeypatch):
    sample_info = {
        "file_name": "comp_v01.0024.exr",
        "file_path": "/vfx/shots/sh01/comp_v01.0024.exr",
        "file_dir": "/vfx/shots/sh01",
        "media_type": "OpenEXR Image Sequence",
        "width": 3840,
        "height": 2160,
        "pixel_aspect": 1.0,
        "start_frame": 1001,
        "end_frame": 1100,
        "current_frame": 1024,
        "fps": 24.0,
        "exr_details": {
            "display_window": (0, 0, 3839, 2159),
            "data_window": (-50, -20, 3889, 2179),
            "compression": "PIZ",
            "line_order": "INCREASING_Y",
            "pixel_aspect": 1.0,
            "channels": [
                {"name": "R", "type": "HALF"},
                {"name": "G", "type": "HALF"},
                {"name": "B", "type": "HALF"},
                {"name": "A", "type": "HALF"},
                {"name": "depth.Z", "type": "FLOAT"},
            ],
            "layers": ["RGBA", "depth"],
            "cryptomatte_layers": ["crypto_asset"],
            "attributes": {
                "camera": "Arri Alexa Mini LF",
                "ISO": "800",
                "lens": "Panavision 50mm",
            },
        },
        "all_metadata_tags": {
            "camera": "Arri Alexa Mini LF",
            "ISO": "800",
            "lens": "Panavision 50mm",
            "exr:compression": "PIZ",
            "exr:dataWindow": "[-50, -20] -> [3889, 2179] (3940x2200)",
            "exr:displayWindow": "[0, 0] -> [3839, 2159] (3840x2160)",
            "exr:lineOrder": "INCREASING_Y",
            "exr:pixelAspectRatio": "1.0000",
            "exr:channels": "5 channels (R, G, B, A, depth.Z)",
            "exr:layers": "RGBA, depth",
            "exr:cryptomatte_layers": "crypto_asset",
        },
    }

    clipboard_mock = MagicMock()
    monkeypatch.setattr(QApplication, "clipboard", lambda: clipboard_mock)

    widget = ImageInfoWidget(sample_info)
    qtbot.addWidget(widget)

    # 1. Verify table exists and has rows
    assert widget.meta_table is not None
    assert widget.filter_edit is not None
    assert widget.meta_table.rowCount() == len(sample_info["all_metadata_tags"])

    # 2. Test search filter
    widget.filter_edit.setText("camera")
    visible_rows = [
        r for r in range(widget.meta_table.rowCount())
        if not widget.meta_table.isRowHidden(r)
    ]
    assert len(visible_rows) == 1
    k_item = widget.meta_table.item(visible_rows[0], 0)
    assert k_item.text() == "camera"
    assert "1/" in widget.tag_grp.title()

    # Clear filter
    widget.filter_edit.clear()
    all_visible = [
        r for r in range(widget.meta_table.rowCount())
        if not widget.meta_table.isRowHidden(r)
    ]
    assert len(all_visible) == widget.meta_table.rowCount()

    # 3. Test Copy All
    widget.btn_copy.click()
    assert clipboard_mock.setText.called
    text_copied = clipboard_mock.setText.call_args[0][0]
    assert "=== OpenReview Source Media Details ===" in text_copied
    assert "Arri Alexa Mini LF" in text_copied

    # 4. Test Table Selection and Ctrl+C copy
    clipboard_mock.reset_mock()
    widget.meta_table.selectRow(0)
    key_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier,
    )
    widget.meta_table.keyPressEvent(key_event)
    assert clipboard_mock.setText.called
    row_copied = clipboard_mock.setText.call_args[0][0]
    assert ":" in row_copied


def test_image_info_export_json(tmp_path, qtbot, monkeypatch):
    sample_info = {
        "file_name": "plate_v01.0001.exr",
        "width": 1920,
        "height": 1080,
        "all_metadata_tags": {
            "iso": "400",
            "fps": "24",
        },
    }
    widget = ImageInfoWidget(sample_info)
    qtbot.addWidget(widget)

    target_json = str(tmp_path / "exported_meta.json")
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (target_json, "JSON Files (*.json)"))

    widget._on_export_json()
    assert os.path.exists(target_json)

    with open(target_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["width"] == 1920
    assert data["all_metadata_tags"]["iso"] == "400"


def test_image_info_dynamic_update(qtbot):
    info_f1 = {
        "file_name": "shot.0001.exr",
        "current_frame": 1,
        "all_metadata_tags": {"frame_id": "1", "speed": "normal"},
    }
    widget = ImageInfoWidget(info_f1)
    qtbot.addWidget(widget)

    assert widget.meta_table.rowCount() == 2
    assert widget.meta_table.item(0, 1).text() in ("1", "normal")

    info_f2 = {
        "file_name": "shot.0002.exr",
        "current_frame": 2,
        "all_metadata_tags": {"frame_id": "2", "speed": "fast", "shutter": "1/48"},
    }
    widget.update_info(info_f2)
    assert widget.meta_table.rowCount() == 3


def test_image_info_group_order(qtbot):
    sample_info = {
        "file_name": "comp.0001.exr",
        "all_metadata_tags": {"camera": "Alexa", "iso": "800"},
        "exr_details": {"compression": "ZIP_COMPRESSION", "display_window": (0, 0, 1919, 1079)},
    }
    widget = ImageInfoWidget(sample_info)
    qtbot.addWidget(widget)

    # Inspect QGroupBox children inside the scroll widget
    content_w = widget._scroll_area.widget()
    from PySide6.QtWidgets import QGroupBox
    groups = content_w.findChildren(QGroupBox)
    titles = [g.title() for g in groups]

    assert len(titles) >= 4
    assert titles[0] == "Source File / Media Container"
    assert "Embedded Metadata" in titles[1] and "Header Attributes" in titles[1]
    assert titles[2] == "OpenEXR Specifications"
    assert titles[3] == "Video & Codec Specifications"
