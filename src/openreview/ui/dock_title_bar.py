"""
Custom Dock Title Bar for OpenReview.
Provides clean window title, tab cycle navigation buttons (‹ and ›),
undock/float toggle, and close button for tabified dock widgets.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QDockWidget,
)


class TabbedDockTitleBar(QWidget):
    """
    Title bar widget installed on QDockWidget instances.
    Provides title display and small left/right cycle buttons when multiple
    dock widgets are tabified in the same dock area.
    """

    def __init__(self, dock: QDockWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent or dock)
        self.dock = dock
        self.setObjectName("TabbedDockTitleBar")
        self._setup_ui()
        self.dock.windowTitleChanged.connect(self.lbl_title.setText)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(4)

        # Title Label
        self.lbl_title = QLabel(self.dock.windowTitle(), self)
        self.lbl_title.setStyleSheet("""
            color: #d8d8d8;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.3px;
        """)
        layout.addWidget(self.lbl_title, 1)

        # Cycle Previous Tab Button (‹)
        self.btn_prev = QToolButton(self)
        self.btn_prev.setText("‹")
        self.btn_prev.setToolTip("Previous tab (cycle docks)")
        self.btn_prev.setFixedSize(20, 20)
        self.btn_prev.setStyleSheet("""
            QToolButton {
                background: #252525;
                color: #aaaaaa;
                border: 1px solid #383838;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QToolButton:hover {
                background: #383838;
                color: #e5a823;
                border-color: #e5a823;
            }
            QToolButton:pressed {
                background: #181818;
            }
        """)
        self.btn_prev.clicked.connect(self._on_cycle_prev)
        layout.addWidget(self.btn_prev)

        # Cycle Next Tab Button (›)
        self.btn_next = QToolButton(self)
        self.btn_next.setText("›")
        self.btn_next.setToolTip("Next tab (cycle docks)")
        self.btn_next.setFixedSize(20, 20)
        self.btn_next.setStyleSheet("""
            QToolButton {
                background: #252525;
                color: #aaaaaa;
                border: 1px solid #383838;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QToolButton:hover {
                background: #383838;
                color: #e5a823;
                border-color: #e5a823;
            }
            QToolButton:pressed {
                background: #181818;
            }
        """)
        self.btn_next.clicked.connect(self._on_cycle_next)
        layout.addWidget(self.btn_next)

        # Float / Undock Button
        self.btn_float = QToolButton(self)
        self.btn_float.setText("🗗")
        self.btn_float.setToolTip("Float / Undock panel")
        self.btn_float.setFixedSize(20, 20)
        self.btn_float.setStyleSheet("""
            QToolButton {
                background: transparent;
                color: #888888;
                border: none;
                font-size: 11px;
            }
            QToolButton:hover {
                background: #383838;
                color: #ffffff;
                border-radius: 2px;
            }
        """)
        self.btn_float.clicked.connect(self._on_toggle_float)
        layout.addWidget(self.btn_float)

        # Close Button (✕)
        self.btn_close = QToolButton(self)
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("Close panel")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet("""
            QToolButton {
                background: transparent;
                color: #888888;
                border: none;
                font-size: 11px;
            }
            QToolButton:hover {
                background: #c0392b;
                color: #ffffff;
                border-radius: 2px;
            }
        """)
        self.btn_close.clicked.connect(self.dock.close)
        layout.addWidget(self.btn_close)

        self.setStyleSheet("""
            QWidget#TabbedDockTitleBar {
                background-color: #202020;
                border-bottom: 1px solid #303030;
            }
        """)

    def _on_cycle_prev(self) -> None:
        main_win = self.dock.window()
        if hasattr(main_win, "cycle_dock_tab"):
            main_win.cycle_dock_tab(self.dock, forward=False)

    def _on_cycle_next(self) -> None:
        main_win = self.dock.window()
        if hasattr(main_win, "cycle_dock_tab"):
            main_win.cycle_dock_tab(self.dock, forward=True)

    def _on_toggle_float(self) -> None:
        self.dock.setFloating(not self.dock.isFloating())
