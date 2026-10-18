"""
Pieces the Roubo integration relies on: the get_annotations control call, the
optional shared tokens on the control port and the dailies room, and keeping
each media's notes apart when the reviewer opens another.
"""
from __future__ import annotations

import json

import pytest

from openreview.models.annotation_stash import PerMediaAnnotations
from openreview.models.annotations import AnnotationStore, ShapeType, Stroke
from openreview.network.ipc_server import IpcServer
from openreview.network.sync_engine import DailiesSyncEngine


class _Clock:
    start_frame = 1001


class _Reader:
    def __init__(self, width=None, cached=None):
        if width is not None:
            self.width = width
        if cached is not None:
            self._cached_width = cached


class _Window:
    def __init__(self, store, reader=None):
        self.annotation_store = store
        self.clock = _Clock()
        self.reader = reader


def _pen(*points):
    return Stroke(shape_type=ShapeType.PEN, points=list(points), color=(255, 0, 0, 255), width=4.0)


def _call(server, method, **params):
    return server._handle_rpc_request({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


@pytest.fixture
def store(qtbot):
    return AnnotationStore()


# ---- get_annotations -------------------------------------------------------

def test_get_annotations_reports_strokes_and_notes_by_frame(qtbot, store):
    store.add_stroke(1010, _pen((0.1, 0.1), (0.5, 0.5)))
    store.add_stroke(1010, Stroke(shape_type=ShapeType.ARROW, points=[(0.2, 0.2), (0.8, 0.3)]))
    store.set_frame_note(1020, "soften the edge")
    server = IpcServer(main_window=_Window(store, _Reader(width=2048)))

    result = _call(server, "get_annotations")["result"]

    assert result["firstFrame"] == 1001
    assert result["frameWidthPx"] == 2048
    assert [f["frame"] for f in result["frames"]] == [1010, 1020]
    first, second = result["frames"]
    assert [s["shape_type"] for s in first["strokes"]] == ["pen", "arrow"]
    assert first["strokes"][0]["color"] == [255, 0, 0, 255]
    assert first["strokes"][0]["width"] == 4.0
    assert second["strokes"] == [] and second["note"] == "soften the edge"
    json.dumps(result)  # must survive the wire


def test_get_annotations_with_nothing_drawn(qtbot, store):
    server = IpcServer(main_window=_Window(store))
    assert _call(server, "get_annotations")["result"]["frames"] == []


def test_get_annotations_without_a_window_is_empty_not_an_error(qtbot):
    server = IpcServer(main_window=None)
    assert _call(server, "get_annotations")["result"] == {"firstFrame": 1, "frameWidthPx": 1920, "frames": []}


@pytest.mark.parametrize(
    "reader, expected",
    [(_Reader(width=3840), 3840), (_Reader(cached=2560), 2560), (_Reader(), 1920), (None, 1920)],
)
def test_media_width_comes_from_the_reader(qtbot, store, reader, expected):
    server = IpcServer(main_window=_Window(store, reader))
    assert _call(server, "get_annotations")["result"]["frameWidthPx"] == expected


# ---- control token ---------------------------------------------------------

def test_control_port_is_open_when_no_token_is_set(qtbot, store, monkeypatch):
    monkeypatch.delenv("OPENREVIEW_CONTROL_TOKEN", raising=False)
    server = IpcServer(main_window=_Window(store))
    assert _call(server, "ping")["result"]["status"] == "pong"


def test_control_port_refuses_calls_without_the_token(qtbot, store, monkeypatch):
    monkeypatch.setenv("OPENREVIEW_CONTROL_TOKEN", "s3cret-token")
    server = IpcServer(main_window=_Window(store))
    for params in ({}, {"token": "wrong"}, {"token": 123}):
        reply = _call(server, "ping", **params)
        assert "result" not in reply
        assert reply["error"]["code"] == -32001 and reply["error"]["message"] == "Unauthorized"
    # ...for every method, not only ping.
    assert _call(server, "get_annotations")["error"]["code"] == -32001


def test_control_port_accepts_the_right_token(qtbot, store, monkeypatch):
    monkeypatch.setenv("OPENREVIEW_CONTROL_TOKEN", "s3cret-token")
    server = IpcServer(main_window=_Window(store))
    assert _call(server, "ping", token="s3cret-token")["result"]["status"] == "pong"
    assert _call(server, "get_annotations", token="s3cret-token")["result"]["frames"] == []


# ---- per-media notes -------------------------------------------------------

def test_notes_stay_with_the_media_they_were_drawn_on(qtbot, store):
    stash = PerMediaAnnotations(store)
    stash.switch_to("a.mov")
    store.add_stroke(1010, _pen((0.1, 0.1), (0.4, 0.4)))
    store.set_frame_note(1010, "version A note")

    stash.switch_to("b.mov")
    assert store.get_annotated_frames() == []  # B starts clean: A's notes are not B's

    store.add_stroke(1010, _pen((0.6, 0.6), (0.9, 0.9)))
    stash.switch_to("a.mov")
    assert store.get_frame_note(1010) == "version A note"
    assert len(store.get_strokes(1010)) == 1
    assert store.get_strokes(1010)[0].points[0] == (0.1, 0.1)

    stash.switch_to("b.mov")
    assert len(store.get_strokes(1010)) == 1
    assert store.get_strokes(1010)[0].points[0] == (0.6, 0.6)


def test_what_was_drawn_before_the_first_media_belongs_to_it(qtbot, store):
    store.add_stroke(5, _pen((0.1, 0.1)))
    stash = PerMediaAnnotations(store)
    stash.switch_to("first.mov")
    assert store.get_annotated_frames() == [5]


def test_switching_to_the_same_media_changes_nothing_and_reset_forgets(qtbot, store):
    stash = PerMediaAnnotations(store)
    stash.switch_to("a.mov")
    store.add_stroke(1, _pen((0.1, 0.1)))
    stash.switch_to("a.mov")
    assert store.get_annotated_frames() == [1]
    stash.reset()
    assert stash.current is None
    stash.switch_to("b.mov")  # adopts the store as it is, like a first media
    assert store.get_annotated_frames() == [1]


def test_main_window_keeps_notes_per_media_through_the_real_loader(qtbot, tmp_path):
    """The wrapper around _load_path: open A, draw, open B (clean), come back to A (restored)."""
    import shutil
    from pathlib import Path

    from openreview.ui.main_window import MainWindow

    src = Path(__file__).parent / "sample_media"
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        for n in (1001, 1002):
            shutil.copy(src / f"sh010_comp_v002.{n}.png", folder / f"{name}.{n}.png")

    win = MainWindow()
    qtbot.addWidget(win)
    a, b = str(tmp_path / "a" / "a.1001.png"), str(tmp_path / "b" / "b.1001.png")

    win._load_path(a)
    win.annotation_store.add_stroke(1001, _pen((0.1, 0.1), (0.5, 0.5)))
    win.annotation_store.set_frame_note(1002, "note on A")

    win._load_path(b)
    assert win.annotation_store.get_annotated_frames() == []
    server = IpcServer(main_window=win)
    assert _call(server, "get_annotations")["result"]["frames"] == []  # what the Roubo launcher would send for B: nothing

    win._load_path(a)
    result = _call(server, "get_annotations")["result"]
    assert result["firstFrame"] == 1001
    assert [(f["frame"], len(f["strokes"]), f["note"]) for f in result["frames"]] == [(1001, 1, ""), (1002, 0, "note on A")]


# ---- dailies room token ----------------------------------------------------

class _FakeSocket:
    """Stands in for a QTcpSocket on the host: records disconnects, swallows writes."""

    def __init__(self):
        self.disconnected = False

    def disconnectFromHost(self):
        self.disconnected = True

    def __getattr__(self, name):
        return lambda *a, **k: None


def _host(qtbot):
    engine = DailiesSyncEngine()
    engine._mode = "host"
    return engine


def _join(token=None):
    payload = {"username": "Dana", "room_name": "Review"}
    if token is not None:
        payload["token"] = token
    return {"type": "JOIN", "sender": "Dana", "payload": payload}


_PLAYBACK = {"type": "PLAYBACK", "sender": "Dana", "payload": {"frame": 1010, "is_playing": False}}


def test_room_is_open_when_no_token_is_set(qtbot, monkeypatch):
    monkeypatch.delenv("OPENREVIEW_SYNC_TOKEN", raising=False)
    engine = _host(qtbot)
    sock = _FakeSocket()
    with qtbot.waitSignal(engine.peer_joined, timeout=1000):
        engine._handle_incoming_message(_join(), source_socket=sock)
    assert sock.disconnected is False
    with qtbot.waitSignal(engine.remote_playback_received, timeout=1000):
        engine._handle_incoming_message(_PLAYBACK, source_socket=sock)


@pytest.mark.parametrize("bad", [None, "wrong", ""])
def test_room_turns_away_a_join_without_the_token(qtbot, monkeypatch, bad):
    monkeypatch.setenv("OPENREVIEW_SYNC_TOKEN", "room-token")
    engine = _host(qtbot)
    sock = _FakeSocket()
    with qtbot.assertNotEmitted(engine.peer_joined):
        engine._handle_incoming_message(_join(bad), source_socket=sock)
    assert sock.disconnected is True
    assert sock not in engine._authed_sockets


def test_room_ignores_messages_from_a_socket_that_never_joined(qtbot, monkeypatch):
    monkeypatch.setenv("OPENREVIEW_SYNC_TOKEN", "room-token")
    engine = _host(qtbot)
    with qtbot.assertNotEmitted(engine.remote_playback_received):
        engine._handle_incoming_message(_PLAYBACK, source_socket=_FakeSocket())


def test_room_accepts_a_join_with_the_token_and_then_its_messages(qtbot, monkeypatch):
    monkeypatch.setenv("OPENREVIEW_SYNC_TOKEN", "room-token")
    engine = _host(qtbot)
    sock = _FakeSocket()
    with qtbot.waitSignal(engine.peer_joined, timeout=1000):
        engine._handle_incoming_message(_join("room-token"), source_socket=sock)
    assert sock.disconnected is False and sock in engine._authed_sockets
    with qtbot.waitSignal(engine.remote_playback_received, timeout=1000):
        engine._handle_incoming_message(_PLAYBACK, source_socket=sock)


def test_a_client_sends_the_token_it_has_in_its_join(qtbot, monkeypatch):
    monkeypatch.setenv("OPENREVIEW_SYNC_TOKEN", "room-token")
    host, client = DailiesSyncEngine(), DailiesSyncEngine()
    port = 19261
    assert host.start_host(port=port, username="Host", room_name="Studio Dailies") is True
    try:
        assert client.room_name != "Studio Dailies"
        assert client.join_host(host="127.0.0.1", port=port, username="Dana") is True
        qtbot.waitUntil(lambda: client.is_connected, timeout=3000)
        # The host only answers an authenticated JOIN with ROOM_INFO, so learning its room name proves the token went through.
        qtbot.waitUntil(lambda: client.room_name == "Studio Dailies", timeout=3000)
    finally:
        client.disconnect_session()
        host.disconnect_session()
