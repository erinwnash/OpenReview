"""
OpenReview User Interface Layer.
"""
from typing import Any

__all__ = ["MainWindow", "get_3dequalizer_stylesheet"]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from openreview.ui.main_window import MainWindow
        return MainWindow
    if name == "get_3dequalizer_stylesheet":
        from openreview.ui.theme import get_3dequalizer_stylesheet
        return get_3dequalizer_stylesheet
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
