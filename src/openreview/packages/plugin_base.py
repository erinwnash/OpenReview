"""
Base Plugin Interface and Context for OpenReview Extensions.
"""
from __future__ import annotations

import logging
from abc import ABC
from typing import Optional, Any, Dict
from openreview.packages.manifest import PackageManifest

logger = logging.getLogger(__name__)


class PluginContext:
    """Provides plugin instances with access to host OpenReview features."""

    def __init__(self, manifest: PackageManifest, main_window: Optional[Any] = None):
        self.manifest = manifest
        self.main_window = main_window

    def log(self, message: str, level: int = logging.INFO) -> None:
        """Log message with plugin namespace prefix."""
        logger.log(level, "[Plugin:%s] %s", self.manifest.name, message)

    def show_toast(self, message: str, duration_ms: int = 3000) -> None:
        """Display an on-screen transient toast message in the viewport."""
        if self.main_window and hasattr(self.main_window, "viewport"):
            self.main_window.viewport.show_toast(f"[{self.manifest.name}] {message}")


class OpenReviewPlugin(ABC):
    """Abstract base class for all OpenReview extension plugins."""

    def __init__(self, context: Optional[PluginContext] = None):
        self.context = context

    def initialize(self) -> None:
        """Called immediately after plugin module is loaded."""
        pass

    def shutdown(self) -> None:
        """Called before plugin is unloaded or application exits."""
        pass

    def on_init(self, context: Optional[PluginContext] = None) -> None:
        """Lifecycle hook: Called when plugin is initialized."""
        pass

    def on_shutdown(self) -> None:
        """Lifecycle hook: Called before plugin is unloaded."""
        pass

    # --------------------------------------------------------------------------
    # Event Hook Callbacks
    # --------------------------------------------------------------------------
    def on_media_loaded(self, media_path: str) -> None:
        """Hook: Fired when new media (video, sequence) is loaded into the viewer."""
        pass

    def on_frame_changed(self, frame: int) -> None:
        """Hook: Fired when playhead advances or user seeks to a new frame."""
        pass

    def on_playback_state_changed(self, is_playing: bool) -> None:
        """Hook: Fired when playback starts or pauses."""
        pass

    def on_annotation_added(self, annotation: Any) -> None:
        """Hook: Fired when an annotation or stroke is drawn."""
        pass

    def on_session_saved(self, session_path: str) -> None:
        """Hook: Fired after a session file is saved."""
        pass

    def on_session_loaded(self, session_path: str) -> None:
        """Hook: Fired after a session file is opened."""
        pass
