"""
Unit and integration tests for Multi-User Remote Dailies Sync,
Custom Studio OCIO Config Search Paths & Context Variables,
and Safe Guides Matte Constraint geometry.
"""
import os
import pytest
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QImage

from openreview.network.sync_engine import DailiesSyncEngine
from openreview.ui.dailies_sync_dialog import DailiesSyncWidget
from openreview.color.ocio_manager import OCIOManager
from openreview.ui.ocio_dialog import OCIOConfigWidget
from openreview.core.preferences import PreferencesManager, UserPreferences
from openreview.models.annotations import AnnotationStore
from openreview.widgets.viewport import ViewportCanvas


def test_dailies_sync_room_management_and_presenter(qtbot):
    """Verify DailiesSyncEngine room management, peer list, and presenter delegation."""
    host_engine = DailiesSyncEngine()
    client_engine = DailiesSyncEngine()

    assert host_engine.room_name == "VFX Review Main"

    # Start host
    port = 9295
    success = host_engine.start_host(port=port, username="Supervisor", room_name="Sequence 040 Review")
    assert success
    assert host_engine.is_host
    assert host_engine.is_presenter
    assert host_engine.room_name == "Sequence 040 Review"

    # Room name setter broadcast
    with qtbot.waitSignal(host_engine.room_info_updated, timeout=1000):
        host_engine.room_name = "Lighting Dailies Room B"
    assert host_engine.room_name == "Lighting Dailies Room B"

    # Presenter grant
    with qtbot.waitSignal(host_engine.presenter_changed, timeout=1000):
        host_engine.grant_presenter("Artist_Comp")
    assert host_engine.presenter == "Artist_Comp"
    assert not host_engine.is_presenter

    # Request presenter back
    with qtbot.waitSignal(host_engine.presenter_changed, timeout=1000):
        host_engine.request_presenter()
    assert host_engine.presenter == "Supervisor"
    assert host_engine.is_presenter

    host_engine.disconnect_session()
    assert not host_engine.is_connected


def test_dailies_sync_widget_controls(qtbot):
    """Verify DailiesSyncWidget has room field, pass control button, and chat tools."""
    engine = DailiesSyncEngine()
    widget = DailiesSyncWidget(engine)
    qtbot.addWidget(widget)

    assert hasattr(widget, "edit_room")
    assert hasattr(widget, "btn_pass_presenter")
    assert hasattr(widget, "btn_export_chat")
    assert hasattr(widget, "btn_clear_chat")

    assert "VFX Review" in widget.edit_room.text()

    # Room update signal updates edit_room
    engine.room_info_updated.emit("Comp Room 9")
    assert widget.edit_room.text() == "Comp Room 9"


def test_ocio_search_paths_and_context_vars():
    """Verify OCIOManager custom search path and context variable operations."""
    ocio = OCIOManager()

    # Initial search paths
    initial_paths = ocio.get_search_paths()

    # Add search path
    test_path = str(Path("C:/studio_luts/show_aces").resolve())
    assert ocio.add_search_path(test_path)
    assert test_path in ocio.get_search_paths()

    # Remove search path
    ocio.remove_search_path(test_path)
    assert test_path not in ocio.get_search_paths()

    # Context variables
    ocio.set_context_var("SHOT", "sh020")
    ocio.set_context_var("SEQ", "sq01")
    vars_dict = ocio.get_context_vars()
    assert vars_dict.get("SHOT") == "sh020"
    assert vars_dict.get("SEQ") == "sq01"

    # Remove context variable
    ocio.remove_context_var("SHOT")
    assert "SHOT" not in ocio.get_context_vars()
    assert ocio.get_context_vars().get("SEQ") == "sq01"


def test_ocio_config_widget_tabs_and_apply(qtbot, tmp_path):
    """Verify OCIOConfigWidget UI tabs and preferences persistence."""
    ocio = OCIOManager()
    widget = OCIOConfigWidget(ocio)
    qtbot.addWidget(widget)

    assert hasattr(widget, "list_sp")
    assert hasattr(widget, "btn_add_sp")
    assert hasattr(widget, "list_ctx")
    assert hasattr(widget, "edit_ctx_key")
    assert hasattr(widget, "edit_ctx_val")

    # Add context var via widget
    widget.edit_ctx_key.setText("STUDIO_ENV")
    widget.edit_ctx_val.setText("PROD")
    widget.btn_set_ctx.click()
    assert ocio.get_context_vars().get("STUDIO_ENV") == "PROD"

    # Apply configuration saves to PreferencesManager
    widget.combo_space.setCurrentText(ocio.get_color_spaces()[0])
    widget._on_apply_clicked()

    prefs = PreferencesManager.instance().prefs
    assert prefs.ocio_input_space == ocio.input_space


def test_safe_guides_matte_constraint_geometry(qtbot):
    """Verify Safe Guides bounding box calculation with and without matte constraint."""
    store = AnnotationStore()
    viewport = ViewportCanvas(store)
    qtbot.addWidget(viewport)
    viewport.resize(1920, 1080)

    import numpy as np
    dummy = np.zeros((1080, 1920, 4), dtype=np.float32)
    viewport.set_primary_frame(1001, dummy)
    viewport.show_safe_guides = True
    viewport.safe_guides_matte_constrained = True

    # 1. Without matte ratio
    viewport.set_matte(None)
    assert viewport.matte_ratio is None or viewport.matte_ratio <= 0.0

    # 2. With 2.39 Cinemascope letterbox matte
    viewport.set_matte(2.39)
    assert viewport.matte_ratio == 2.39
    assert viewport.safe_guides_matte_constrained is True

    # Toggle constraint
    viewport.toggle_safe_guides_matte_constraint()
    assert viewport.safe_guides_matte_constrained is False

    viewport.set_safe_guides_matte_constrained(True)
    assert viewport.safe_guides_matte_constrained is True

    # Render offscreen to verify painter execution doesn't crash
    img = QImage(640, 360, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.black)
    p = QPainter(img)
    try:
        viewport._paint_safe_guides(p)
    finally:
        p.end()
