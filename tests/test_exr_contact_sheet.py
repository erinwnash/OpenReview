"""
Tests for Multi-Channel EXR Contact Sheet Engine and Pass Review Tools.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from openreview.core.exr_contact_sheet import (
    get_contact_sheet_grid,
    auto_normalize_depth_pass,
    draw_contact_sheet_badges,
    build_exr_contact_sheet,
    hit_test_contact_sheet,
    extract_exr_detailed_metadata,
)
from openreview.widgets.hud_layers import HUDLayersWidget


def test_contact_sheet_grid_dimensions():
    assert get_contact_sheet_grid(1) == (1, 1)
    assert get_contact_sheet_grid(2) == (1, 2)
    assert get_contact_sheet_grid(3) == (2, 2)
    assert get_contact_sheet_grid(4) == (2, 2)
    assert get_contact_sheet_grid(5) == (2, 3)
    assert get_contact_sheet_grid(6) == (2, 3)
    assert get_contact_sheet_grid(8) == (3, 3)
    assert get_contact_sheet_grid(9) == (3, 3)
    assert get_contact_sheet_grid(12) == (3, 4)
    assert get_contact_sheet_grid(16) == (4, 4)


def test_auto_normalize_depth_pass():
    # Synthetic depth pass with high dynamic range values (e.g. 10.0 to 110.0)
    raw_depth = np.full((100, 100), 10.0, dtype=np.float32)
    raw_depth[20:80, 20:80] = 110.0

    normalized = auto_normalize_depth_pass(raw_depth)
    assert normalized.shape == (100, 100, 4)
    assert normalized.dtype == np.float32

    # Background should be normalized near 0.0, inner square near 1.0
    assert np.isclose(normalized[0, 0, 0], 0.0, atol=1e-3)
    assert np.isclose(normalized[50, 50, 0], 1.0, atol=1e-3)
    assert np.isclose(normalized[50, 50, 3], 1.0)  # Alpha opaque


def test_build_contact_sheet_and_hit_testing(qtbot):
    # Create 4 synthetic layer passes
    h, w = 180, 320
    beauty = np.ones((h, w, 4), dtype=np.float32)
    ao = np.full((h, w, 4), 0.5, dtype=np.float32)
    normal = np.full((h, w, 4), 0.8, dtype=np.float32)
    depth = np.full((h, w, 4), 50.0, dtype=np.float32)

    layer_frames = {
        "beauty": beauty,
        "A_O": ao,
        "normal_CAMERA": normal,
        "depth.Z": depth,
    }

    comp, tile_map = build_exr_contact_sheet(
        layer_frames,
        base_w=640,
        base_h=360,
        auto_depth=True,
        draw_labels=True,
    )

    assert comp.ndim == 3 and comp.shape[2] == 4
    assert len(tile_map) == 4
    assert set(tile_map.keys()) == {"beauty", "A_O", "normal_CAMERA", "depth.Z"}

    # Hit test inside beauty tile
    bx, by, bw, bh = tile_map["beauty"]
    hit = hit_test_contact_sheet(bx + bw // 2, by + bh // 2, tile_map)
    assert hit == "beauty"

    # Hit test inside normal_CAMERA tile
    nx, ny, nw, nh = tile_map["normal_CAMERA"]
    hit_norm = hit_test_contact_sheet(nx + nw // 2, ny + nh // 2, tile_map)
    assert hit_norm == "normal_CAMERA"

    # Hit test outside canvas
    assert hit_test_contact_sheet(-10, -10, tile_map) is None


def test_hud_layers_widget_controls_and_signals(qtbot):
    widget = HUDLayersWidget()
    qtbot.addWidget(widget)

    passes = ["beauty", "A_O", "diffuse", "specular", "normal_CAMERA", "crypto_asset"]
    widget.refresh_list(passes)

    # 1. Test Search Filter
    assert widget.list_layers.count() == 6
    widget.search_input.setText("norm")
    visible_items = [
        widget.list_layers.item(i).text()
        for i in range(widget.list_layers.count())
        if not widget.list_layers.item(i).isHidden()
    ]
    assert visible_items == ["normal_CAMERA"]

    widget.search_input.clear()
    visible_items_all = [
        widget.list_layers.item(i).text()
        for i in range(widget.list_layers.count())
        if not widget.list_layers.item(i).isHidden()
    ]
    assert len(visible_items_all) == 6

    # 2. Test Contact Sheet Toggle Signal
    with qtbot.waitSignal(widget.contact_sheet_toggled, timeout=1000) as blocker:
        widget.btn_contact_sheet.click()
    assert blocker.args == [True]

    # 3. Test View Single Signal
    with qtbot.waitSignal(widget.view_single_requested, timeout=1000):
        widget.btn_view_single.click()

    # 4. Test Export Contact Sheet Signal
    with qtbot.waitSignal(widget.export_contact_sheet_requested, timeout=1000):
        widget.btn_export.click()

    # 5. Test Channel Solo Signal
    with qtbot.waitSignal(widget.channel_mode_requested, timeout=1000) as blocker:
        widget._chan_btns[1].click()  # Solo Red
    assert blocker.args == [1]

    # 6. Test Auto-Depth Signal
    with qtbot.waitSignal(widget.auto_depth_toggled, timeout=1000) as blocker:
        widget.btn_auto_depth.click()
    assert blocker.args == [True]

    # 7. Test Metadata Signal
    with qtbot.waitSignal(widget.metadata_requested, timeout=1000):
        widget.btn_info.click()
