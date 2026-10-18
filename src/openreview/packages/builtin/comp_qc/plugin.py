"""
xtra QC Utils Built-in Plugin for OpenReview.
Registers the xtra QC Utils HUD Card or Dock Widget, hooks into viewport rendering,
and orchestrates QC states, source plate comparisons, and matte inspection.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Any
from pathlib import Path
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence

from openreview.packages.plugin_base import OpenReviewPlugin, PluginContext
from openreview.packages.builtin.comp_qc.qc_state import CompQCState, XtraQCState
from openreview.packages.builtin.comp_qc.hud_comp_qc import CompQCHUDWidget, CompQCDockWidget, XtraQCWidget, XtraQCDockWidget
from openreview.widgets.floating_hud import FloatingHUDCard

logger = logging.getLogger(__name__)


class CompQCPlugin(OpenReviewPlugin):
    """Inbuilt Compositing Tech QC Plugin for OpenReview (xtra QC Utils)."""

    def __init__(self, context: Optional[PluginContext] = None) -> None:
        super().__init__(context)
        self.state = CompQCState()
        self.widget: Optional[XtraQCWidget] = None
        self.hud_card: Optional[FloatingHUDCard] = None
        self.dock: Optional[XtraQCDockWidget] = None
        self.menu_action: Optional[QAction] = None
        self._current_media_path: Optional[str] = None

    def initialize(self) -> None:
        """Initialize plugin and register dock or HUD card on host MainWindow."""
        main_win = self.context.main_window if self.context else None
        if not main_win or not hasattr(main_win, "viewport"):
            self.context.log("MainWindow or Viewport not available for xtra QC Utils.")
            return

        viewport = main_win.viewport

        # 1. Check if MainWindow already hosts comp_qc_dock
        if hasattr(main_win, "comp_qc_dock") and main_win.comp_qc_dock is not None:
            self.dock = main_win.comp_qc_dock
            self.state = getattr(main_win, "comp_qc_state", self.state)
            self.widget = getattr(self.dock, "panel", None)
        elif hasattr(main_win, "addDockWidget"):
            self.dock = CompQCDockWidget(self.state, parent=main_win)
            self.widget = self.dock.panel
            self._connect_panel_signals()
            main_win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            self.dock.hide()
            main_win.comp_qc_dock = self.dock
            main_win.hud_comp_qc = self.dock
            main_win.comp_qc_state = self.state
            viewport.comp_qc_state = self.state
            self.state.changed.connect(viewport.update)
        else:
            # Fallback for simple mock QWidget hosts
            self.widget = CompQCHUDWidget(self.state, parent=viewport)
            self._connect_panel_signals()
            self.hud_card = FloatingHUDCard(
                title="xtra QC Utils",
                content_widget=self.widget,
                parent=viewport,
                initial_pos=QPoint(180, 70),
            )
            self.hud_card.hide()
            main_win.hud_comp_qc = self.hud_card
            main_win.comp_qc_state = self.state
            viewport.comp_qc_state = self.state
            self.state.changed.connect(viewport.update)

        # 2. Register menu items in Tools or Window menu
        mb = main_win.menuBar() if hasattr(main_win, "menuBar") else None
        if mb:
            win_menu = None
            for action in mb.actions():
                menu = action.menu()
                if menu and "Window" in action.text():
                    win_menu = menu
                    break

            self.menu_action = QAction("xtra QC Utils (Hold Q)", main_win)
            self.menu_action.setShortcut(QKeySequence("Q"))
            self.menu_action.triggered.connect(self.toggle_hud)

            if win_menu:
                win_menu.addAction(self.menu_action)

            for action in mb.actions():
                menu = action.menu()
                if menu and "Review" in action.text():
                    menu.addSeparator()
                    menu.addAction(self.menu_action)
                    break

        self.context.log("xtra QC Utils Plugin initialized successfully.")

    def _connect_panel_signals(self) -> None:
        if not self.widget:
            return
        if hasattr(self.widget, "source_plate_dropped"):
            self.widget.source_plate_dropped.connect(self._on_source_dropped)
        if hasattr(self.widget, "source_prefetch_requested"):
            self.widget.source_prefetch_requested.connect(self._on_prefetch_source)
        if hasattr(self.widget, "source_unload_requested"):
            self.widget.source_unload_requested.connect(self._on_unload_source)
        if hasattr(self.widget, "matte_dropped"):
            self.widget.matte_dropped.connect(self._on_matte_dropped)
        if hasattr(self.widget, "matte_prefetch_requested"):
            self.widget.matte_prefetch_requested.connect(self._on_prefetch_matte)
        if hasattr(self.widget, "matte_unload_requested"):
            self.widget.matte_unload_requested.connect(self._on_unload_matte)

    def toggle_hud(self) -> None:
        """Toggle visibility of the Comp QC dock or HUD card."""
        target = self.dock or self.hud_card
        if target:
            vis = target.isHidden()
            target.setVisible(vis)
            if vis:
                target.raise_()
                if hasattr(target, "set_latched"):
                    target.set_latched(True)

    def on_media_loaded(self, media_path: str) -> None:
        """Hook called when new media is loaded."""
        self._current_media_path = media_path

    def on_frame_changed(self, frame: int) -> None:
        """Hook called on timeline playhead movement."""
        main_win = self.context.main_window if self.context else None
        if main_win and hasattr(main_win, "viewport"):
            main_win.viewport.update()

    def _on_source_dropped(self, file_path: str) -> None:
        main_win = self.context.main_window if self.context else None
        if main_win and hasattr(main_win, "_on_comp_qc_source_dropped"):
            main_win._on_comp_qc_source_dropped(file_path)

    def _on_prefetch_source(self) -> None:
        self.state.source_prefetch_progress = 1.0

    def _on_unload_source(self) -> None:
        self.state.source_plate_path = None
        self.state.source_prefetch_progress = 0.0
        main_win = self.context.main_window if self.context else None
        if main_win and hasattr(main_win, "viewport"):
            main_win.viewport.set_reference_frame(None)

    def _on_matte_dropped(self, file_path: str) -> None:
        main_win = self.context.main_window if self.context else None
        if main_win and hasattr(main_win, "_on_comp_qc_matte_dropped"):
            main_win._on_comp_qc_matte_dropped(file_path)

    def _on_prefetch_matte(self) -> None:
        self.state.matte_prefetch_progress = 1.0

    def _on_unload_matte(self) -> None:
        self.state.matte_path = None
        self.state.matte_prefetch_progress = 0.0
        main_win = self.context.main_window if self.context else None
        if main_win and hasattr(main_win, "viewport") and hasattr(main_win.viewport, "set_matte_frame"):
            main_win.viewport.set_matte_frame(None)

    def shutdown(self) -> None:
        """Clean up on plugin unload."""
        if self.hud_card:
            self.hud_card.hide()
            self.hud_card.deleteLater()
            self.hud_card = None
        if self.dock:
            self.dock.hide()
            self.dock = None
        if self.menu_action:
            self.menu_action.deleteLater()
            self.menu_action = None
        self.context.log("xtra QC Utils Plugin shut down.")


# Semantic alias
XtraQCPlugin = CompQCPlugin
