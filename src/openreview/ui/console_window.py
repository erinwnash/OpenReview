"""
Non-Modal Diagnostic Console & Error Log Window for OpenReview.
Displays real-time application logs, warnings, errors, stdout/stderr prints,
Qt messages, and unhandled exception tracebacks with severity filtering,
search, clipboard export, and automatic popup on error.
"""
from __future__ import annotations

import html
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from openreview.core.console_logger import ConsoleLogManager, LogEntry
from openreview.core.preferences import PreferencesManager, UserPreferences


_LEVEL_RANK = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_LEVEL_COLOR = {
    "DEBUG": "#888888",
    "INFO": "#d8d8d8",
    "WARNING": "#f0ad4e",
    "ERROR": "#ff5555",
    "CRITICAL": "#ff3333",
}


class ConsoleWindow(QDialog):
    """
    Standalone non-modal Console & Error Log Window.
    Remains hidden by default; opened via Window menu or automatically on error.
    """
    visibility_changed = Signal(bool)

    def __init__(
        self,
        log_manager: Optional[ConsoleLogManager] = None,
        pref_mgr: Optional[PreferencesManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        # Configure as an independent non-modal window with minimize/maximize/close buttons
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setWindowTitle("OpenReview - Console & Error Log")
        self.resize(860, 480)
        self.setMinimumSize(560, 280)

        from openreview.resources import get_app_icon
        self.setWindowIcon(get_app_icon())

        self.log_manager = log_manager or ConsoleLogManager.instance()
        self.pref_mgr = pref_mgr or PreferencesManager.instance()

        self._setup_ui()
        self._connect_signals()
        self.refresh_logs()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1c;
                color: #e0e0e0;
            }
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            QLabel#summaryBadge {
                background-color: #141414;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 3px 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                color: #cccccc;
            }
            QComboBox, QLineEdit {
                background-color: #141414;
                color: #e0e0e0;
                border: 1px solid #383838;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:focus, QLineEdit:focus {
                border-color: #e5a823;
            }
            QCheckBox {
                color: #cccccc;
                font-size: 11px;
                spacing: 5px;
            }
            QPushButton {
                background-color: #2b2b2b;
                color: #dddddd;
                border: 1px solid #444444;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e5a823;
                color: #111111;
                border-color: #e5a823;
            }
            QPlainTextEdit#consoleLogView {
                background-color: #121212;
                color: #d8d8d8;
                border: 1px solid #303030;
                border-radius: 3px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #e5a823;
                selection-color: #111111;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # Top Filter & Controls Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_level = QLabel("Level:")
        top_bar.addWidget(lbl_level)

        self.level_combo = QComboBox(self)
        self.level_combo.addItem("All Levels", 0)
        self.level_combo.addItem("Debug+", 10)
        self.level_combo.addItem("Info+", 20)
        self.level_combo.addItem("Warnings & Errors", 30)
        self.level_combo.addItem("Errors Only", 40)
        self.level_combo.setCurrentIndex(0)
        self.level_combo.setFixedWidth(140)
        top_bar.addWidget(self.level_combo)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter logs by keyword, module, or error...")
        self.search_edit.setClearButtonEnabled(True)
        top_bar.addWidget(self.search_edit, stretch=1)

        self.auto_scroll_cb = QCheckBox("Auto-scroll", self)
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.setToolTip("Automatically scroll to the newest log message")
        top_bar.addWidget(self.auto_scroll_cb)

        self.auto_open_cb = QCheckBox("Auto-open on Error", self)
        auto_open_init = getattr(self.pref_mgr.prefs, "console_auto_open_on_error", True)
        self.auto_open_cb.setChecked(bool(auto_open_init))
        self.auto_open_cb.setToolTip(
            "Automatically open this Console Window whenever an application error occurs"
        )
        top_bar.addWidget(self.auto_open_cb)

        root_layout.addLayout(top_bar)

        # Central Read-Only Log Viewport
        self.log_view = QPlainTextEdit(self)
        self.log_view.setObjectName("consoleLogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root_layout.addWidget(self.log_view, stretch=1)

        # Bottom Status & Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.summary_label = QLabel("Total: 0 | Warnings: 0 | Errors: 0", self)
        self.summary_label.setObjectName("summaryBadge")
        bottom_bar.addWidget(self.summary_label)

        bottom_bar.addStretch(1)

        self.clear_btn = QPushButton("Clear", self)
        self.clear_btn.setToolTip("Clear all console log entries")
        bottom_bar.addWidget(self.clear_btn)

        self.copy_btn = QPushButton("Copy All", self)
        self.copy_btn.setToolTip("Copy visible console logs to the clipboard")
        bottom_bar.addWidget(self.copy_btn)

        self.save_btn = QPushButton("Save Log...", self)
        self.save_btn.setToolTip("Save visible console logs to a .log file")
        bottom_bar.addWidget(self.save_btn)

        root_layout.addLayout(bottom_bar)

    def _connect_signals(self) -> None:
        self.log_manager.log_emitted.connect(self._on_log_emitted)
        self.log_manager.logs_cleared.connect(self._on_logs_cleared)

        self.level_combo.currentIndexChanged.connect(lambda _: self.refresh_logs())
        self.search_edit.textChanged.connect(lambda _: self.refresh_logs())
        self.auto_open_cb.toggled.connect(self._on_auto_open_toggled)

        self.clear_btn.clicked.connect(self.clear_logs)
        self.copy_btn.clicked.connect(self.copy_logs_to_clipboard)
        self.save_btn.clicked.connect(self.save_logs_to_file)

        self.pref_mgr.preferences_changed.connect(self._on_preferences_changed)

    def _on_auto_open_toggled(self, checked: bool) -> None:
        if getattr(self.pref_mgr.prefs, "console_auto_open_on_error", True) != checked:
            self.pref_mgr.prefs.console_auto_open_on_error = checked
            self.pref_mgr.save()

    def _on_preferences_changed(self, prefs: UserPreferences) -> None:
        target = bool(getattr(prefs, "console_auto_open_on_error", True))
        if self.auto_open_cb.isChecked() != target:
            self.auto_open_cb.blockSignals(True)
            self.auto_open_cb.setChecked(target)
            self.auto_open_cb.blockSignals(False)

    def _matches_filter(self, entry: LogEntry) -> bool:
        min_rank = int(self.level_combo.currentData() or 0)
        entry_rank = _LEVEL_RANK.get(entry.level.upper(), 20)
        if entry_rank < min_rank:
            return False

        query = self.search_edit.text().strip().lower()
        if query:
            haystack = f"{entry.timestamp} {entry.level} {entry.source} {entry.message}".lower()
            if query not in haystack:
                return False
        return True

    def _format_entry_html(self, entry: LogEntry) -> str:
        color = _LEVEL_COLOR.get(entry.level.upper(), "#d8d8d8")
        ts_esc = html.escape(entry.timestamp)
        lvl_esc = html.escape(f"{entry.level:<8}").replace(" ", "&nbsp;")
        src_esc = html.escape(entry.source)
        msg_esc = html.escape(entry.message).replace("\n", "<br/>")
        weight = "bold" if entry.is_error else "normal"
        return (
            f'<span style="color:#666666;">[{ts_esc}]</span> '
            f'<span style="color:{color}; font-weight:bold;">[{lvl_esc}]</span> '
            f'<span style="color:#8ab4f8;">[{src_esc}]</span> '
            f'<span style="color:{color}; font-weight:{weight};">{msg_esc}</span>'
        )

    def _update_summary_counts(self, entries: Optional[List[LogEntry]] = None) -> None:
        if entries is None:
            entries = self.log_manager.get_entries()
        total = len(entries)
        warnings = sum(1 for e in entries if e.level.upper() == "WARNING")
        errors = sum(1 for e in entries if e.is_error or e.level.upper() in ("ERROR", "CRITICAL"))
        self.summary_label.setText(f"Total: {total} | Warnings: {warnings} | Errors: {errors}")

    def _on_log_emitted(self, entry: LogEntry) -> None:
        self._update_summary_counts()
        if self._matches_filter(entry):
            self.log_view.appendHtml(self._format_entry_html(entry))
            if self.auto_scroll_cb.isChecked():
                self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _on_logs_cleared(self) -> None:
        self.log_view.clear()
        self._update_summary_counts([])

    def refresh_logs(self) -> None:
        """Rebuild the log viewport from buffered entries using active filters."""
        entries = self.log_manager.get_entries()
        self._update_summary_counts(entries)
        self.log_view.clear()
        filtered = [e for e in entries if self._matches_filter(e)]
        if filtered:
            html_lines = "<br/>".join(self._format_entry_html(e) for e in filtered)
            self.log_view.appendHtml(html_lines)
            if self.auto_scroll_cb.isChecked():
                self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def get_filtered_entries(self) -> List[LogEntry]:
        """Return all buffered entries matching current level and search filters."""
        return [e for e in self.log_manager.get_entries() if self._matches_filter(e)]

    def clear_logs(self) -> None:
        """Clear all buffered and displayed logs."""
        self.log_manager.clear()

    def copy_logs_to_clipboard(self) -> str:
        """Copy currently filtered plain-text log lines to the system clipboard."""
        text = "\n".join(e.formatted_line() for e in self.get_filtered_entries())
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        return text

    def save_logs_to_file(self, file_path: Optional[str] = None) -> bool:
        """Export currently filtered plain-text log lines to a file on disk."""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Console Log",
                "openreview_console.log",
                "Log Files (*.log *.txt);;All Files (*)",
            )
        if not file_path:
            return False
        try:
            text = "\n".join(e.formatted_line() for e in self.get_filtered_entries())
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text + ("\n" if text else ""))
            return True
        except Exception:
            return False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.auto_scroll_cb.isChecked():
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def closeEvent(self, event) -> None:
        """Hide instead of destroying when closed by the user so logs remain accessible."""
        event.ignore()
        self.hide()
