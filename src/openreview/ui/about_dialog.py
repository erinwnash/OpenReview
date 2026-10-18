"""
About Dialog for OpenReview.
Provides comprehensive application information, branding, and a dedicated
interactive third-party license inspector with full copyright notices and texts.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPixmap, QPainter, QDesktopServices, QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QDialogButtonBox,
    QFrame,
    QSplitter,
)

import openreview
from openreview.resources import get_app_icon, get_app_logo_path, get_licenses


class AboutDialog(QDialog):
    """
    Studio-grade About dialog featuring:
    - Overview tab: Logo, versioning, author, architecture, and project links.
    - Licenses tab: Master-detail browser of all core dependencies, licenses,
      copyright notices, filter search, and copy-to-clipboard utilities.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("About OpenReview")
        self.setWindowIcon(get_app_icon())
        self.resize(700, 540)
        self.setMinimumSize(560, 420)

        self._license_items: List[Dict[str, Any]] = get_licenses()

        self._apply_theme()
        self._init_ui()

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #181818;
                border-radius: 4px;
                top: -1px;
            }
            QTabBar::tab {
                background: #252525;
                color: #aaaaaa;
                padding: 8px 20px;
                border: 1px solid #333333;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #181818;
                color: #e5a823;
                border-color: #333333;
                border-bottom: 1px solid #181818;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #2c2c2c;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #121212;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #e5a823;
            }
            QListWidget {
                background-color: #141414;
                border: 1px solid #2e2e2e;
                border-radius: 4px;
                color: #d0d0d0;
                outline: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #202020;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #242424;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #2f2716;
                border: 1px solid #e5a823;
                color: #ffd269;
            }
            QPlainTextEdit {
                background-color: #111111;
                border: 1px solid #2e2e2e;
                border-radius: 4px;
                color: #c8c8c8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
                padding: 8px;
            }
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                color: #ffffff;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #e5a823;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QScrollBar:vertical {
                background: #141414;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #e5a823;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._create_about_tab(), "About")
        self.tabs.addTab(self._create_licenses_tab(), "Licenses")
        main_layout.addWidget(self.tabs)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        btn_box.rejected.connect(self.accept)
        main_layout.addWidget(btn_box)

    def _create_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Logo Header
        logo_path = get_app_logo_path()
        if logo_path.exists():
            logo_lbl = QLabel(tab)
            pix = None
            if logo_path.suffix.lower() == ".svg":
                try:
                    from PySide6.QtSvg import QSvgRenderer
                    renderer = QSvgRenderer(str(logo_path))
                    if renderer.isValid():
                        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                        target_w, target_h = 420, 68
                        pix = QPixmap(int(target_w * dpr), int(target_h * dpr))
                        pix.setDevicePixelRatio(dpr)
                        pix.fill(Qt.GlobalColor.transparent)
                        p = QPainter(pix)
                        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        renderer.render(p, QRectF(0, 0, target_w, target_h))
                        p.end()
                except Exception:
                    pix = None
            if pix is None or pix.isNull():
                pix = QPixmap(str(logo_path)).scaled(
                    420, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_lbl)

        # Info Box
        info_lbl = QLabel(tab)
        info_lbl.setWordWrap(True)
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_lbl.setOpenExternalLinks(True)
        info_lbl.setStyleSheet("font-size: 12px; line-height: 1.5; color: #cccccc;")

        ver = openreview.__version__
        info_lbl.setText(
            f"<div style='text-align: center;'>"
            f"<span style='font-size: 16px; font-weight: bold; color: #e5a823;'>OpenReview</span> "
            f"<span style='background-color: #2b2b2b; color: #f0b830; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;'>v{ver}</span><br>"
            f"<span style='color: #a0a0a0;'>Created by <strong style='color: #ffffff;'>Maruthu Chakravarthi</strong></span><br><br>"
            f"<span style='color: #e0e0e0; font-size: 13px;'>"
            f"Studio-grade VFX Sequence Playback, HDR Inspection, and Collaborative Dailies Review Workstation."
            f"</span><br><br>"
            f"<div style='background-color: #141414; border: 1px solid #2a2a2a; border-radius: 6px; padding: 10px; margin: 0 20px;'>"
            f"<span style='color: #88aaff; font-weight: 600;'>Color Pipeline:</span> OpenColorIO v2 &bull; ACES 1.3 / 2.0 &bull; OCIO CPU/GPU Shaders<br>"
            f"<span style='color: #88aaff; font-weight: 600;'>Graphics Engine:</span> PySide6 (Qt 6) &bull; OpenGL 3.3 Core Profile<br>"
            f"<span style='color: #88aaff; font-weight: 600;'>Format Support:</span> OpenEXR multi-part / deep &bull; DPX &bull; TIFF &bull; ProRes &bull; DNxHR"
            f"</div><br>"
            f"<span style='color: #999999;'>Licensed under the <strong style='color: #e5a823;'>MIT License</strong>. "
            f"See the <a href='#licenses' style='color: #e5a823; text-decoration: none;'>Licenses tab</a> for third-party notices.</span><br><br>"
            f"<a href='https://github.com/maruthuvfx/OpenReview' style='color: #64b5f6; text-decoration: none;'>GitHub Repository</a> &nbsp;&bull;&nbsp; "
            f"<a href='https://maruthuvfx.github.io/OpenReview/' style='color: #64b5f6; text-decoration: none;'>Documentation</a> &nbsp;&bull;&nbsp; "
            f"<a href='https://github.com/maruthuvfx/OpenReview/issues' style='color: #64b5f6; text-decoration: none;'>Report an Issue</a>"
            f"</div>"
        )
        info_lbl.linkActivated.connect(self._handle_link_click)
        layout.addWidget(info_lbl)

        layout.addStretch()
        return tab

    def _create_licenses_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Search bar
        self.search_input = QLineEdit(tab)
        self.search_input.setPlaceholderText("Filter libraries by name, license type, or keywords...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_libraries)
        layout.addWidget(self.search_input)

        # Master-Detail Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal, tab)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2b2b2b;
                width: 4px;
            }
        """)

        # Left list
        self.list_widget = QListWidget(splitter)
        self.list_widget.currentRowChanged.connect(self._on_item_selected)
        splitter.addWidget(self.list_widget)

        # Right detail panel
        detail_container = QWidget(splitter)
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(12, 0, 4, 0)
        detail_layout.setSpacing(8)

        # Header info
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.detail_title = QLabel("Select a library", detail_container)
        self.detail_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        header_row.addWidget(self.detail_title)

        self.detail_version = QLabel("", detail_container)
        self.detail_version.setStyleSheet(
            "background-color: #262626; color: #e5a823; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;"
        )
        header_row.addWidget(self.detail_version)

        self.detail_license_tag = QLabel("", detail_container)
        self.detail_license_tag.setStyleSheet(
            "background-color: #1e3a5f; color: #80bfff; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 500;"
        )
        header_row.addWidget(self.detail_license_tag)

        header_row.addStretch()

        self.btn_homepage = QPushButton("Website ↗", detail_container)
        self.btn_homepage.setFixedHeight(26)
        self.btn_homepage.clicked.connect(self._open_homepage)
        header_row.addWidget(self.btn_homepage)

        detail_layout.addLayout(header_row)

        # Description
        self.detail_desc = QLabel("", detail_container)
        self.detail_desc.setWordWrap(True)
        self.detail_desc.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        detail_layout.addWidget(self.detail_desc)

        # Copyright Card
        self.detail_copyright = QLabel("", detail_container)
        self.detail_copyright.setWordWrap(True)
        self.detail_copyright.setStyleSheet(
            "background-color: #141414; border-left: 3px solid #e5a823; padding: 6px 10px; color: #dddddd; font-size: 11px;"
        )
        detail_layout.addWidget(self.detail_copyright)

        # Full License label & Copy button
        lic_header_row = QHBoxLayout()
        lic_lbl = QLabel("License Terms:", detail_container)
        lic_lbl.setStyleSheet("color: #888888; font-weight: 600; font-size: 11px;")
        lic_header_row.addWidget(lic_lbl)
        lic_header_row.addStretch()

        self.btn_copy = QPushButton("Copy License Text", detail_container)
        self.btn_copy.setFixedHeight(24)
        self.btn_copy.clicked.connect(self._copy_license_text)
        lic_header_row.addWidget(self.btn_copy)
        detail_layout.addLayout(lic_header_row)

        # Text Viewer
        self.detail_text = QPlainTextEdit(detail_container)
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 7)

        layout.addWidget(splitter)

        self._populate_license_list()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

        return tab

    def _populate_license_list(self) -> None:
        self.list_widget.clear()
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""

        for item in self._license_items:
            # Check query match
            searchable = f"{item['name']} {item['package']} {item['license_type']} {item['description']}".lower()
            if query and query not in searchable:
                continue

            list_item = QListWidgetItem()
            list_item.setText(f"{item['name']}\n{item['license_type']}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(list_item)

    def _filter_libraries(self, text: str) -> None:
        current_data = None
        if self.list_widget.currentItem():
            current_data = self.list_widget.currentItem().data(Qt.ItemDataRole.UserRole)

        self._populate_license_list()

        # Try to restore selection
        if current_data:
            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                if item.data(Qt.ItemDataRole.UserRole).get("id") == current_data.get("id"):
                    self.list_widget.setCurrentRow(row)
                    return

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self._clear_detail()

    def _on_item_selected(self, row: int) -> None:
        if row < 0 or row >= self.list_widget.count():
            return

        item = self.list_widget.item(row)
        if not item:
            return

        data: Dict[str, Any] = item.data(Qt.ItemDataRole.UserRole)
        self.detail_title.setText(data.get("name", ""))
        self.detail_version.setText(f"v{data.get('version', '')}")
        self.detail_license_tag.setText(data.get("license_type", ""))
        self.detail_desc.setText(data.get("description", ""))
        self.detail_copyright.setText(data.get("copyright", ""))
        self.detail_text.setPlainText(data.get("license_text", ""))

        self._current_homepage = data.get("homepage", "")
        self.btn_homepage.setEnabled(bool(self._current_homepage))

    def _clear_detail(self) -> None:
        self.detail_title.setText("No matches found")
        self.detail_version.setText("")
        self.detail_license_tag.setText("")
        self.detail_desc.setText("")
        self.detail_copyright.setText("")
        self.detail_text.setPlainText("")
        self.btn_homepage.setEnabled(False)
        self._current_homepage = ""

    def _open_homepage(self) -> None:
        if hasattr(self, "_current_homepage") and self._current_homepage:
            QDesktopServices.openUrl(self._current_homepage)

    def _copy_license_text(self) -> None:
        text = self.detail_text.toPlainText()
        if not text:
            return

        clipboard: QClipboard = QGuiApplication.clipboard()
        clipboard.setText(text)

        original_text = "Copy License Text"
        self.btn_copy.setText("✓ Copied!")
        self.btn_copy.setStyleSheet("background-color: #234d20; color: #a3e635; border-color: #4d7c0f;")
        QTimer.singleShot(1500, self._restore_copy_button)

    def _restore_copy_button(self) -> None:
        self.btn_copy.setText("Copy License Text")
        self.btn_copy.setStyleSheet("")

    def _handle_link_click(self, link: str) -> None:
        if link == "#licenses":
            self.tabs.setCurrentIndex(1)
        elif link.startswith("http://") or link.startswith("https://"):
            QDesktopServices.openUrl(link)
