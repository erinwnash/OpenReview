"""
Centralized Diagnostic Console Logger & Stream/Exception Interceptor for OpenReview.
Captures Python logging records, stdout/stderr print statements, unhandled exceptions,
and Qt internal messages into a thread-safe ring buffer with Qt signals for live UI updates
and automatic error window activation.
"""
from __future__ import annotations

import datetime
import logging
import re
import sys
import threading
import traceback
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional, TextIO

from PySide6.QtCore import (
    QObject,
    QtMsgType,
    QMessageLogContext,
    Signal,
    qInstallMessageHandler,
)


_ERROR_PATTERN = re.compile(r"\b(error|exception|traceback|critical|fatal)\b", re.IGNORECASE)
_WARNING_PATTERN = re.compile(r"\b(warn|warning)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LogEntry:
    """Single immutable diagnostic log entry."""
    timestamp: str
    level: str        # "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    source: str       # Logger name, "stdout", "stderr", "qt", "exception"
    message: str
    is_error: bool = False

    def formatted_line(self) -> str:
        """Return plain-text formatted line for copying or saving to disk."""
        return f"[{self.timestamp}] [{self.level:<8}] [{self.source}] {self.message}"


class _QtConsoleLoggingHandler(logging.Handler):
    """Custom Python logging.Handler that forwards LogRecords to ConsoleLogManager."""

    def __init__(self, manager: ConsoleLogManager) -> None:
        super().__init__(level=logging.DEBUG)
        self._manager = manager

    def emit(self, record: logging.LogRecord) -> None:
        if self._manager._is_reentrant():
            return
        try:
            self._manager._enter_guard()
            msg = self.format(record)
            level_name = record.levelname.upper()
            is_err = record.levelno >= logging.ERROR
            self._manager.record_log(
                level=level_name,
                source=record.name or "root",
                message=msg,
                is_error=is_err,
            )
        except Exception:
            pass
        finally:
            self._manager._exit_guard()


class _StreamInterceptor:
    """
    File-like wrapper for sys.stdout and sys.stderr that forwards writes to the
    original stream while emitting complete lines into ConsoleLogManager.
    """

    def __init__(
        self,
        manager: ConsoleLogManager,
        underlying: Optional[TextIO],
        stream_name: str,
    ) -> None:
        self._manager = manager
        self._underlying = underlying
        self._stream_name = stream_name
        self._buffer = ""
        self._lock = threading.RLock()

    @property
    def underlying(self) -> Optional[TextIO]:
        return self._underlying

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)

        # Always forward to underlying stream if available
        if self._underlying is not None:
            try:
                self._underlying.write(text)
            except Exception:
                pass

        if not text or self._manager._is_reentrant():
            return len(text)

        try:
            self._manager._enter_guard()
            with self._lock:
                self._buffer += text
                while "\n" in self._buffer:
                    line, self._buffer = self._buffer.split("\n", 1)
                    clean = line.rstrip("\r")
                    if clean.strip():
                        self._emit_line(clean)
        except Exception:
            pass
        finally:
            self._manager._exit_guard()

        return len(text)

    def _emit_line(self, line: str) -> None:
        # Avoid capturing pytest's own test progress dots/headers if running under pytest
        if self._stream_name == "stderr":
            if _WARNING_PATTERN.search(line) and not _ERROR_PATTERN.search(line):
                level = "WARNING"
                is_error = False
            else:
                level = "ERROR"
                is_error = True
        else:
            if _ERROR_PATTERN.search(line):
                level = "ERROR"
                is_error = True
            elif _WARNING_PATTERN.search(line):
                level = "WARNING"
                is_error = False
            else:
                level = "INFO"
                is_error = False

        # Extract bracketed prefix like "[OCIOManager] message" if present
        source = self._stream_name
        message = line
        if line.startswith("[") and "]" in line:
            close_idx = line.find("]")
            prefix = line[1:close_idx].strip()
            rest = line[close_idx + 1:].strip()
            if prefix and rest and " " not in prefix:
                source = prefix
                message = rest

        self._manager.record_log(
            level=level,
            source=source,
            message=message,
            is_error=is_error,
        )

    def flush(self) -> None:
        if self._underlying is not None:
            try:
                self._underlying.flush()
            except Exception:
                pass

    def __getattr__(self, name: str):
        if self._underlying is not None:
            return getattr(self._underlying, name)
        raise AttributeError(f"'_StreamInterceptor' object has no attribute {name!r}")


class ConsoleLogManager(QObject):
    """
    Singleton diagnostic console log manager.
    Collects application logs, print output, Qt warnings/errors, and unhandled exceptions.
    """
    log_emitted = Signal(object)   # Emits LogEntry
    error_logged = Signal(object)  # Emits LogEntry when is_error is True
    logs_cleared = Signal()

    _instance: Optional[ConsoleLogManager] = None

    def __init__(self, max_entries: int = 5000, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._max_entries = max(100, int(max_entries))
        self._entries: Deque[LogEntry] = deque(maxlen=self._max_entries)
        self._lock = threading.RLock()
        self._tls = threading.local()

        self._logging_handler: Optional[_QtConsoleLoggingHandler] = None
        self._stdout_interceptor: Optional[_StreamInterceptor] = None
        self._stderr_interceptor: Optional[_StreamInterceptor] = None
        self._orig_excepthook: Optional[Callable] = None
        self._orig_threading_excepthook: Optional[Callable] = None
        self._orig_qt_handler: Optional[Callable] = None
        self._hooks_installed: bool = False

    @classmethod
    def instance(cls) -> ConsoleLogManager:
        if cls._instance is None:
            cls._instance = ConsoleLogManager()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance.uninstall_hooks()
        cls._instance = None

    def _is_reentrant(self) -> bool:
        return getattr(self._tls, "in_emit", False)

    def _enter_guard(self) -> None:
        self._tls.in_emit = True

    def _exit_guard(self) -> None:
        self._tls.in_emit = False

    def install_hooks(self) -> None:
        """Install Python logging handler, stdout/stderr interceptors, excepthooks, and Qt message handler."""
        with self._lock:
            # 1. Python logging handler on root logger
            root_logger = logging.getLogger()
            if self._logging_handler is None:
                self._logging_handler = _QtConsoleLoggingHandler(self)
                formatter = logging.Formatter("%(message)s")
                self._logging_handler.setFormatter(formatter)
            if self._logging_handler not in root_logger.handlers:
                root_logger.addHandler(self._logging_handler)

            # Ensure openreview namespace logger allows DEBUG/INFO records through
            or_logger = logging.getLogger("openreview")
            if or_logger.level == logging.NOTSET or or_logger.level > logging.DEBUG:
                or_logger.setLevel(logging.DEBUG)

            # 2. Wrap sys.stdout and sys.stderr if not already wrapped by us
            if not isinstance(sys.stdout, _StreamInterceptor):
                self._stdout_interceptor = _StreamInterceptor(self, sys.stdout, "stdout")
                sys.stdout = self._stdout_interceptor  # type: ignore[assignment]
            if not isinstance(sys.stderr, _StreamInterceptor):
                self._stderr_interceptor = _StreamInterceptor(self, sys.stderr, "stderr")
                sys.stderr = self._stderr_interceptor  # type: ignore[assignment]

            if not self._hooks_installed:
                # 3. Unhandled exception hooks
                self._orig_excepthook = sys.excepthook
                sys.excepthook = self._handle_unhandled_exception

                if hasattr(threading, "excepthook"):
                    self._orig_threading_excepthook = threading.excepthook
                    threading.excepthook = self._handle_threading_exception

                # 4. Qt message handler
                try:
                    self._orig_qt_handler = qInstallMessageHandler(self._handle_qt_message)
                except Exception:
                    self._orig_qt_handler = None

                self._hooks_installed = True

    def uninstall_hooks(self) -> None:
        """Restore original streams, exception hooks, Qt message handler, and detach logging handler."""
        with self._lock:
            root_logger = logging.getLogger()
            if self._logging_handler is not None and self._logging_handler in root_logger.handlers:
                root_logger.removeHandler(self._logging_handler)

            if isinstance(sys.stdout, _StreamInterceptor) and self._stdout_interceptor is not None:
                if sys.stdout is self._stdout_interceptor and self._stdout_interceptor.underlying is not None:
                    sys.stdout = self._stdout_interceptor.underlying
            self._stdout_interceptor = None

            if isinstance(sys.stderr, _StreamInterceptor) and self._stderr_interceptor is not None:
                if sys.stderr is self._stderr_interceptor and self._stderr_interceptor.underlying is not None:
                    sys.stderr = self._stderr_interceptor.underlying
            self._stderr_interceptor = None

            if self._hooks_installed:
                if self._orig_excepthook is not None:
                    sys.excepthook = self._orig_excepthook
                    self._orig_excepthook = None

                if self._orig_threading_excepthook is not None and hasattr(threading, "excepthook"):
                    threading.excepthook = self._orig_threading_excepthook
                    self._orig_threading_excepthook = None

                try:
                    qInstallMessageHandler(self._orig_qt_handler)
                except Exception:
                    pass
                self._orig_qt_handler = None
                self._hooks_installed = False

    def _handle_unhandled_exception(self, exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            if self._orig_excepthook is not None:
                self._orig_excepthook(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip()
        self.record_log(
            level="CRITICAL",
            source="exception",
            message=f"Unhandled Exception:\n{tb_text}",
            is_error=True,
        )
        if self._orig_excepthook is not None:
            try:
                self._enter_guard()
                self._orig_excepthook(exc_type, exc_value, exc_tb)
            finally:
                self._exit_guard()

    def _handle_threading_exception(self, args) -> None:
        tb_text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        ).rstrip()
        thread_name = getattr(args.thread, "name", "WorkerThread")
        self.record_log(
            level="CRITICAL",
            source=f"thread:{thread_name}",
            message=f"Unhandled Thread Exception:\n{tb_text}",
            is_error=True,
        )
        if self._orig_threading_excepthook is not None:
            try:
                self._enter_guard()
                self._orig_threading_excepthook(args)
            finally:
                self._exit_guard()

    def _handle_qt_message(
        self,
        mode: QtMsgType,
        context: QMessageLogContext,
        message: str,
    ) -> None:
        if not self._is_reentrant() and message:
            try:
                self._enter_guard()
                if mode == QtMsgType.QtDebugMsg:
                    level, is_err = "DEBUG", False
                elif mode == QtMsgType.QtInfoMsg:
                    level, is_err = "INFO", False
                elif mode == QtMsgType.QtWarningMsg:
                    level, is_err = "WARNING", False
                elif mode == QtMsgType.QtCriticalMsg:
                    level, is_err = "ERROR", True
                elif mode == QtMsgType.QtFatalMsg:
                    level, is_err = "CRITICAL", True
                else:
                    level, is_err = "INFO", False

                cat = getattr(context, "category", None)
                source = f"qt.{cat}" if cat and cat != "default" else "qt"
                self.record_log(level=level, source=source, message=message, is_error=is_err)
            except Exception:
                pass
            finally:
                self._exit_guard()

        if self._orig_qt_handler is not None:
            try:
                self._orig_qt_handler(mode, context, message)
            except Exception:
                pass

    def record_log(
        self,
        level: str,
        source: str,
        message: str,
        is_error: Optional[bool] = None,
    ) -> LogEntry:
        """Create a LogEntry, store it in the ring buffer, and emit notification signals."""
        norm_level = (level or "INFO").upper()
        if is_error is None:
            is_error = norm_level in ("ERROR", "CRITICAL", "FATAL")

        now_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = LogEntry(
            timestamp=now_str,
            level=norm_level,
            source=source or "app",
            message=message,
            is_error=bool(is_error),
        )
        with self._lock:
            self._entries.append(entry)

        self.log_emitted.emit(entry)
        if entry.is_error:
            self.error_logged.emit(entry)
        return entry

    def get_entries(self) -> List[LogEntry]:
        """Return a snapshot list of all buffered LogEntry items."""
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        """Clear all buffered log entries and notify listeners."""
        with self._lock:
            self._entries.clear()
        self.logs_cleared.emit()
