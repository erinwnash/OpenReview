"""
Application Bootstrap and Entry Point for OpenReview.
"""
from __future__ import annotations

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from openreview.ui.main_window import MainWindow


def create_application() -> QApplication:
    # Set Windows Process AppUserModelID for taskbar icon association
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("openreview.vfx.app")
        except Exception:
            pass

    # Configure high-DPI behavior
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Configure Default OpenGL Core Profile Surface Format
    gl_format = QSurfaceFormat()
    gl_format.setVersion(3, 3)
    gl_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    gl_format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    gl_format.setSwapInterval(0)  # Master clock-driven frame pacing (disables 60Hz integer divisor locks)
    QSurfaceFormat.setDefaultFormat(gl_format)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("OpenReview")
        app.setOrganizationName("OpenReview")
    app.setStyle("Fusion")

    from openreview.resources import get_app_icon
    app.setWindowIcon(get_app_icon())

    return app


def main() -> int:
    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
