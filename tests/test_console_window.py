"""
Tests for the Diagnostic Console & Error Log Window feature:
- Default hidden state on startup
- Opening/closing from the Window menu and keyboard shortcut
- Capturing Python logging, print (stdout/stderr), and unhandled exceptions
- Automatic popup when an error is logged on app console (and toggle preference)
- Severity filtering, search filtering, clipboard copy, clear, and file export
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from openreview.core.console_logger import ConsoleLogManager
from openreview.core.preferences import PreferencesManager
from openreview.ui.main_window import MainWindow


@pytest.fixture
def clean_console_env(tmp_path):
    """Provide isolated PreferencesManager and ConsoleLogManager for each test."""
    PreferencesManager.reset_instance()
    pref_mgr = PreferencesManager(config_dir=tmp_path / "prefs")
    PreferencesManager._instance = pref_mgr

    ConsoleLogManager.reset_instance()
    log_mgr = ConsoleLogManager.instance()
    log_mgr.install_hooks()
    log_mgr.clear()

    yield pref_mgr, log_mgr

    ConsoleLogManager.reset_instance()
    PreferencesManager.reset_instance()


def test_console_window_hidden_by_default_and_menu_toggle(qapp, clean_console_env):
    """Console window should be hidden by default and toggleable via Window menu."""
    win = MainWindow()
    try:
        assert hasattr(win, "console_window")
        assert win.console_window.isHidden()
        assert hasattr(win, "act_console_window")
        assert not win.act_console_window.isChecked()

        # Open via Window menu action
        win.act_console_window.trigger()
        assert not win.console_window.isHidden()
        assert win.act_console_window.isChecked()

        # Close via ConsoleWindow.close() -> hides window and unchecks menu action
        win.console_window.close()
        assert win.console_window.isHidden()
        assert not win.act_console_window.isChecked()
    finally:
        win.close()


def test_console_auto_opens_on_error_log(qapp, clean_console_env):
    """Console window should stay hidden on INFO/WARNING and open automatically on ERROR."""
    pref_mgr, log_mgr = clean_console_env
    win = MainWindow()
    try:
        win.console_window.hide()
        log_mgr.clear()

        test_logger = logging.getLogger("openreview.test_auto_open")

        # INFO and WARNING must NOT open the console window
        test_logger.info("Normal playback started")
        test_logger.warning("Minor frame metadata warning")
        assert win.console_window.isHidden()
        assert len(log_mgr.get_entries()) >= 2

        # ERROR log must automatically open the console window
        test_logger.error("Failed to decode EXR frame 1005")
        assert not win.console_window.isHidden()
        assert win.act_console_window.isChecked()
        assert "Failed to decode EXR frame 1005" in win.console_window.log_view.toPlainText()
    finally:
        win.close()


def test_console_auto_opens_on_error_print_and_respects_toggle(qapp, clean_console_env):
    """Error prints / stderr should auto-open console unless Auto-open on Error is disabled."""
    pref_mgr, log_mgr = clean_console_env
    win = MainWindow()
    try:
        win.console_window.hide()
        log_mgr.clear()

        # Re-ensure stream hooks are active on current sys.stdout/stderr
        log_mgr.install_hooks()

        # Standard info print does not open console
        print("[AudioEngine] Audio initialized successfully")
        assert win.console_window.isHidden()

        # Error print automatically opens console
        print("[OCIOManager] PyOpenColorIO CreateFromFile error: invalid config")
        assert not win.console_window.isHidden()

        # Hide console and disable "Auto-open on Error" checkbox
        win.console_window.hide()
        win.console_window.auto_open_cb.setChecked(False)
        assert pref_mgr.prefs.console_auto_open_on_error is False

        # Subsequent error logs are recorded but do NOT pop open the window
        logging.getLogger("openreview.test").error("Suppressed popup error")
        assert win.console_window.isHidden()
        assert any("Suppressed popup error" in e.message for e in log_mgr.get_entries())
    finally:
        win.close()


def test_console_captures_unhandled_exception(qapp, clean_console_env):
    """Unhandled exceptions via sys.excepthook should be logged as CRITICAL and open console."""
    _, log_mgr = clean_console_env
    win = MainWindow()
    prev_orig = log_mgr._orig_excepthook
    log_mgr._orig_excepthook = lambda *args: None
    try:
        win.console_window.hide()
        log_mgr.clear()

        try:
            raise RuntimeError("Simulated GPU shader compilation failure")
        except RuntimeError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            sys.excepthook(exc_type, exc_val, exc_tb)

        assert not win.console_window.isHidden()
        entries = log_mgr.get_entries()
        assert any(
            e.level == "CRITICAL" and "Simulated GPU shader compilation failure" in e.message
            for e in entries
        )
    finally:
        log_mgr._orig_excepthook = prev_orig
        win.close()


def test_console_filtering_search_clear_copy_and_save(qapp, clean_console_env, tmp_path):
    """Verify level filter, search box, clipboard copy, file export, and clear button."""
    _, log_mgr = clean_console_env
    win = MainWindow()
    try:
        cw = win.console_window
        log_mgr.clear()

        log_mgr.record_log("DEBUG", "openreview.cache", "Prefetching frame 1001", is_error=False)
        log_mgr.record_log("INFO", "openreview.reader", "Loaded sequence shot_010", is_error=False)
        log_mgr.record_log("WARNING", "openreview.ocio", "Fallback display transform used", is_error=False)
        log_mgr.record_log("ERROR", "openreview.exr", "Corrupt scanline in frame 1004", is_error=True)

        assert len(cw.get_filtered_entries()) == 4
        assert "Total: 4 | Warnings: 1 | Errors: 1" in cw.summary_label.text()

        # Filter to "Errors Only" (index 4 -> min_rank 40)
        cw.level_combo.setCurrentIndex(4)
        filtered = cw.get_filtered_entries()
        assert len(filtered) == 1
        assert filtered[0].level == "ERROR"

        # Reset level filter to "All Levels" and filter by keyword search
        cw.level_combo.setCurrentIndex(0)
        cw.search_edit.setText("shot_010")
        filtered = cw.get_filtered_entries()
        assert len(filtered) == 1
        assert "Loaded sequence shot_010" in filtered[0].message

        # Copy filtered logs to clipboard
        copied = cw.copy_logs_to_clipboard()
        assert "Loaded sequence shot_010" in copied

        # Save filtered logs to file
        out_log: Path = tmp_path / "exported_console.log"
        assert cw.save_logs_to_file(str(out_log)) is True
        assert out_log.is_file()
        assert "Loaded sequence shot_010" in out_log.read_text(encoding="utf-8")

        # Clear logs
        cw.search_edit.clear()
        cw.clear_logs()
        assert len(log_mgr.get_entries()) == 0
        assert cw.log_view.toPlainText() == ""
    finally:
        win.close()
