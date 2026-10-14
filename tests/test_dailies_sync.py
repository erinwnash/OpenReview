"""
Unit and Integration Tests for Multi-User Remote Dailies Sync.
Covers DailiesSyncEngine networking protocol, host/client messaging,
synchronized playback, collaborative markup strokes, remote color grading,
group dailies chat, DailiesSyncDialog UI, and MainWindow integration.
"""
from __future__ import annotations

import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QCoreApplication

from openreview.network.sync_engine import DailiesSyncEngine
from openreview.ui.dailies_sync_dialog import DailiesSyncDialog
from openreview.models.annotations import Stroke, ShapeType
from openreview.ui.main_window import MainWindow


def test_sync_engine_host_and_client_connection(qtbot):
    """Test starting a host server and connecting a client."""
    host_engine = DailiesSyncEngine()
    client_engine = DailiesSyncEngine()

    port = 19182
    assert host_engine.start_host(port=port, username="Supervisor") is True
    assert host_engine.is_connected is True
    assert host_engine.is_host is True
    assert host_engine.is_presenter is True
    assert host_engine.mode == "host"

    # Client joins host
    assert client_engine.join_host(host="127.0.0.1", port=port, username="LeadArtist") is True

    # Process events to allow TCP handshake
    def _check_connected():
        assert client_engine.is_connected is True
        assert client_engine.mode == "client"

    qtbot.waitUntil(_check_connected, timeout=3000)

    # Clean up
    client_engine.disconnect_session()
    host_engine.disconnect_session()
    assert client_engine.is_connected is False
    assert host_engine.is_connected is False


def test_sync_engine_broadcast_and_reception(qtbot):
    """Test packet transmission across network: playback, color, stroke, note, chat."""
    host_engine = DailiesSyncEngine()
    client_engine = DailiesSyncEngine()

    port = 19183
    host_engine.start_host(port=port, username="Director")
    client_engine.join_host(host="127.0.0.1", port=port, username="CompArtist")

    qtbot.waitUntil(lambda: client_engine.is_connected and len(host_engine._client_sockets) > 0, timeout=3000)

    # 1. Test Playback Sync
    received_playback = []
    client_engine.remote_playback_received.connect(lambda p: received_playback.append(p))

    host_engine.broadcast_playback(frame=1042, is_playing=True, fps=24.0, shuttle_speed=1.0)
    qtbot.waitUntil(lambda: len(received_playback) > 0, timeout=3000)
    assert received_playback[0]["frame"] == 1042
    assert received_playback[0]["is_playing"] is True

    # 2. Test Color Grade Sync
    received_color = []
    client_engine.remote_color_received.connect(lambda p: received_color.append(p))

    host_engine.broadcast_color(exposure_ev=1.5, gamma=1.2, channel_mode=0, input_space=1, view_transform=0)
    qtbot.waitUntil(lambda: len(received_color) > 0, timeout=3000)
    assert abs(received_color[0]["exposure_ev"] - 1.5) < 0.01
    assert abs(received_color[0]["gamma"] - 1.2) < 0.01

    # 3. Test Collaborative Stroke Sync
    received_strokes = []
    client_engine.remote_stroke_received.connect(lambda f, s: received_strokes.append((f, s)))

    stroke = Stroke(
        shape_type=ShapeType.CIRCLE,
        points=[(0.2, 0.3), (0.4, 0.5)],
        color=(255, 0, 0, 255),
        width=4.0,
    )
    host_engine.broadcast_stroke(frame=1050, stroke_dict=stroke.to_dict())
    qtbot.waitUntil(lambda: len(received_strokes) > 0, timeout=3000)
    f, s_data = received_strokes[0]
    assert f == 1050
    restored_stroke = Stroke.from_dict(s_data)
    assert restored_stroke.shape_type == ShapeType.CIRCLE
    assert restored_stroke.color == (255, 0, 0, 255)

    # 4. Test Frame Note Sync
    received_notes = []
    client_engine.remote_note_received.connect(lambda f, n: received_notes.append((f, n)))

    host_engine.broadcast_note(frame=1050, note="Fix edge chatter on foreground matte")
    qtbot.waitUntil(lambda: len(received_notes) > 0, timeout=3000)
    assert received_notes[0] == (1050, "Fix edge chatter on foreground matte")

    # 5. Test Dailies Chat Sync
    received_chat = []
    client_engine.chat_message_received.connect(lambda s, m: received_chat.append((s, m)))

    host_engine.broadcast_chat("Welcome to dailies review team!")
    qtbot.waitUntil(lambda: len(received_chat) > 0, timeout=3000)
    assert received_chat[0] == ("Director", "Welcome to dailies review team!")

    # Clean up
    client_engine.disconnect_session()
    host_engine.disconnect_session()


def test_dailies_sync_dialog_ui(qtbot):
    """Test DailiesSyncDialog controls, host setup, and chat input."""
    engine = DailiesSyncEngine()
    dlg = DailiesSyncDialog(engine)
    qtbot.addWidget(dlg)

    # Test initial tab layout
    assert dlg.tabs.count() == 2
    assert dlg.tabs.tabText(0) == "Session & Participants"
    assert dlg.tabs.tabText(1) == "Review Chat"

    # Check Host fields
    assert dlg.spin_port.value() == 9090
    assert dlg.btn_connect.text() == "Start Hosting"

    # Start host from UI
    dlg.edit_user.setText("VFX_Super")
    dlg.spin_port.setValue(19184)
    dlg.btn_connect.click()

    assert engine.is_connected is True
    assert engine.is_host is True
    assert engine.username == "VFX_Super"
    assert "Host" in dlg.lbl_status.text()
    assert dlg.btn_connect.text() == "Disconnect"

    # Test Chat sending
    dlg.edit_message.setText("Please review shot 020")
    dlg.btn_send_chat.click()
    assert dlg.edit_message.text() == ""
    assert "Please review shot 020" in dlg.txt_chat_history.toPlainText()

    # Disconnect from UI
    dlg.btn_connect.click()
    assert engine.is_connected is False
    assert "Offline" in dlg.lbl_status.text()


def test_main_window_sync_integration(qtbot):
    """Test MainWindow synchronization handlers and UI status indicators."""
    win = MainWindow()
    qtbot.addWidget(win)

    # 1. Status indicator
    assert "Sync: Offline" in win.sync_status_label.text()

    win.sync_engine.start_host(port=19185, username="Presenter")
    win._on_sync_status_changed(True, "Hosting Dailies on port 19185")
    assert "Sync: Host [Presenter]" in win.sync_status_label.text()

    # 2. Remote playback handler
    win.clock.set_frame(1001)
    win.clock.pause()
    win._on_remote_playback({"frame": 1088, "is_playing": False, "fps": 24.0})
    assert win.clock.current_frame == 1088

    # 3. Remote color grade handler
    win._on_remote_color({"exposure_ev": 1.25, "gamma": 1.5, "channel_mode": 0})
    assert abs(win.top_bar.exposure_ev - 1.25) < 0.01
    assert abs(win.top_bar.gamma - 1.5) < 0.01

    # 4. Remote stroke handler
    stroke = Stroke(shape_type=ShapeType.LINE, points=[(0.1, 0.1), (0.9, 0.9)], width=2.0)
    win._on_remote_stroke(1088, stroke.to_dict())
    strokes = win.annotation_store.get_strokes(1088)
    assert len(strokes) >= 1
    assert strokes[-1].shape_type == ShapeType.LINE

    # 5. Remote note handler
    win._on_remote_note(1088, "Check lens distortion alignment")
    assert win.annotation_store.get_frame_note(1088) == "Check lens distortion alignment"

    # 6. Remote clear handler
    win._on_remote_clear_annotations(1088)
    assert len(win.annotation_store.get_strokes(1088)) == 0

    # Cleanup
    win.sync_engine.disconnect_session()
    win._on_sync_status_changed(False, "Disconnected")
    assert "Sync: Offline" in win.sync_status_label.text()
