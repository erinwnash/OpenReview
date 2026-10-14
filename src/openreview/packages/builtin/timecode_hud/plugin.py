"""
Timecode HUD Overlay Built-in Plugin.
"""
from openreview.packages.plugin_base import OpenReviewPlugin


class TimecodeHudPlugin(OpenReviewPlugin):
    """Monitors frame changes and logs telemetry for HUD extensions."""

    def initialize(self) -> None:
        self.context.log("Timecode HUD Overlay Extension active.")

    def on_media_loaded(self, media_path: str) -> None:
        self.context.log(f"Media loaded into OpenReview: {media_path}")

    def on_frame_changed(self, frame: int) -> None:
        # Frame advancement hook
        pass

    def shutdown(self) -> None:
        self.context.log("Timecode HUD Overlay Extension shutdown.")
