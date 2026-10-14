import pytest
from PySide6.QtWidgets import QApplication
from openreview.network.ipc_server import IpcServer
from openreview.sdk.client import OpenReviewClient, OpenReviewError
from openreview.sdk import dcc


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


class MockSlider:
    def __init__(self):
        self.val = 1.0

    def set_value(self, v):
        self.val = v


class MockTopBar:
    def __init__(self):
        self.gain_slider = MockSlider()
        self.gamma_slider = MockSlider()
        self.sat_slider = MockSlider()


class MockPix:
    def save(self, path):
        return True


class MockViewport:
    def __init__(self):
        self.exposure_ev = 0.0
        self.gain = 1.0
        self.gamma = 1.0
        self.saturation = 1.0
        self.channel_mode = "RGB"
        self.playback_engine = "opengl_core"

    def update(self):
        pass

    def grab(self):
        return MockPix()


class MockClock:
    def __init__(self):
        self.current_frame = 1
        self.start_frame = 1
        self.end_frame = 100
        self.in_frame = 1
        self.out_frame = 100
        self.fps = 24.0
        self.is_playing = False
        self.loop_mode = "loop"
        self.bookmarks = set()

    def play(self):
        self.is_playing = True

    def pause(self):
        self.is_playing = False

    def toggle_playback(self):
        self.is_playing = not self.is_playing

    def set_frame(self, f):
        self.current_frame = f

    def set_fps(self, fps):
        self.fps = fps

    def set_in_out(self, in_f, out_f):
        self.in_frame = in_f
        self.out_frame = out_f

    def add_bookmark(self, f):
        self.bookmarks.add(f)

    def clear_all_bookmarks(self):
        self.bookmarks.clear()


class MockWindow:
    def __init__(self):
        self.clock = MockClock()
        self.viewport = MockViewport()
        self.top_bar = MockTopBar()
        self._current_media_path = None
        self._current_media_type = "none"

    def _load_path(self, path):
        self._current_media_path = str(path)
        self._current_media_type = "image"
        return True


def test_sdk_client_connection_failure():
    client = OpenReviewClient(port=59999, timeout=0.5)
    assert client.ping() is False
    with pytest.raises(OpenReviewError):
        client.get_status()


import threading
import time


def test_sdk_with_ipc_server(qtbot):
    mock_win = MockWindow()
    # Use dedicated test port
    server = IpcServer(main_window=mock_win)
    assert server.start(host="127.0.0.1", port=45199) is True

    def call_client(func):
        res = []
        err = []

        def runner():
            try:
                res.append(func())
            except Exception as e:
                err.append(e)

        t = threading.Thread(target=runner)
        t.start()
        start_time = time.time()
        while t.is_alive():
            qtbot.wait(5)
            if time.time() - start_time > 4.0:
                break
        t.join(timeout=1.0)
        if err:
            raise err[0]
        return res[0]

    try:
        client = OpenReviewClient(host="127.0.0.1", port=45199, timeout=2.0)
        
        # Test ping
        assert call_client(client.ping) is True

        # Test get_status
        status = call_client(client.get_status)
        assert status["fps"] == 24.0
        assert status["current_frame"] == 1
        assert status["is_playing"] is False

        # Test load_media
        res = call_client(lambda: client.load_media("/path/to/shot.exr"))
        assert res is True
        assert mock_win._current_media_path == "/path/to/shot.exr"

        # Test playback controls
        call_client(client.play)
        assert mock_win.clock.is_playing is True
        call_client(client.pause)
        assert mock_win.clock.is_playing is False
        call_client(client.toggle_play)
        assert mock_win.clock.is_playing is True

        # Test seek and fps
        call_client(lambda: client.seek(42))
        assert mock_win.clock.current_frame == 42
        call_client(lambda: client.set_fps(30.0))
        assert mock_win.clock.fps == 30.0

        # Test in/out
        call_client(lambda: client.set_in_out(1001, 1050))
        assert mock_win.clock.in_frame == 1001
        assert mock_win.clock.out_frame == 1050

        # Test color adjustments
        call_client(lambda: client.set_color(gain=1.5, gamma=0.8, saturation=1.2))
        assert mock_win.viewport.gain == 1.5
        assert mock_win.viewport.gamma == 0.8
        assert mock_win.viewport.saturation == 1.2

        # Test bookmarks
        call_client(lambda: client.add_bookmark(1020, "Fix roto edge"))
        assert 1020 in mock_win.clock.bookmarks
        call_client(client.clear_bookmarks)
        assert len(mock_win.clock.bookmarks) == 0

        # Test export frame
        assert call_client(lambda: client.export_frame("/tmp/out.png", 1020)) is True

    finally:
        server.stop()


def test_dcc_script_helpers():
    py_nuke = dcc.get_nuke_menu_script(port=45124)
    assert "openreview.sdk" in py_nuke
    assert "OpenReviewClient" in py_nuke

    py_maya = dcc.get_maya_shelf_script(port=45124)
    assert "openreview.sdk" in py_maya
    assert "OpenReviewClient" in py_maya
