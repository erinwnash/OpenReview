"""
Unit tests for OS File Associations and Initial File Ingestion.
"""
import os
import tempfile
from pathlib import Path
import pytest

from openreview.core.file_associations import (
    get_command_string,
    get_icon_path,
    is_file_association_registered,
    register_file_associations,
    unregister_file_associations,
)


def test_command_string_and_icon():
    cmd = get_command_string()
    assert '"%1"' in cmd
    assert len(cmd) > 5

    ico = get_icon_path()
    assert ico != ""
    assert ico.endswith(".ico") or ico.endswith(",0")


def test_is_registered_query():
    # Should safely return a boolean without crashing
    res = is_file_association_registered()
    assert isinstance(res, bool)


def test_main_window_load_initial_file(qapp, monkeypatch):
    from openreview.ui.main_window import MainWindow

    loaded_sessions = []
    loaded_media = []

    window = MainWindow()

    monkeypatch.setattr(window, "_open_session_file", lambda p: loaded_sessions.append(str(p)))
    monkeypatch.setattr(window, "_load_path", lambda p: loaded_media.append(str(p)))

    with tempfile.TemporaryDirectory() as td:
        dummy_ovr = os.path.join(td, "project_v01.ovr")
        with open(dummy_ovr, "w") as f:
            f.write("{}")

        dummy_mov = os.path.join(td, "shot_010.mov")
        with open(dummy_mov, "w") as f:
            f.write("dummy")

        # Test loading .ovr
        window.load_initial_file(dummy_ovr)
        assert len(loaded_sessions) == 1
        assert loaded_sessions[0].endswith("project_v01.ovr")

        # Test loading media
        window.load_initial_file(dummy_mov)
        assert len(loaded_media) == 1
        assert loaded_media[0].endswith("shot_010.mov")
