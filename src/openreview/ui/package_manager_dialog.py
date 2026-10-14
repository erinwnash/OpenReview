"""
Package and Plugin Management Dialog for OpenReview.
Provides visual management for installed plugins, extensions, zip package installs,
and software update checks against GitHub Releases or Studio manifest channels.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QSplitter,
)

from openreview.packages.manifest import PackageManifest
from openreview.packages.package_manager import PackageManager
from openreview.packages.updater import SoftwareUpdater, UpdateInfo, CURRENT_VERSION


class PackageManagerDialog(QDialog):
    """Studio Package and Plugin Manager Dialog."""

    def __init__(self, pkg_mgr: Optional[PackageManager] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("OpenReview Package & Plugin Manager")
        self.resize(840, 560)
        self.pkg_mgr = pkg_mgr or PackageManager.instance()
        self.updater = SoftwareUpdater()

        self._setup_ui()
        self._refresh_package_table()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background: #252525;
                color: #aaaaaa;
                padding: 7px 18px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #333333;
                color: #e5a823;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #333333;
                margin-top: 6px;
                padding-top: 10px;
                color: #e5a823;
                font-weight: bold;
            }
            QLabel {
                color: #cccccc;
            }
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                color: #ffffff;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                border-color: #e5a823;
                background-color: #383838;
            }
            QTableWidget {
                background-color: #141414;
                border: 1px solid #333333;
                color: #dddddd;
                gridline-color: #262626;
                selection-background-color: #3d3420;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #bbbbbb;
                padding: 4px;
                border: 1px solid #333333;
                font-weight: bold;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #121212;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                padding: 4px 6px;
                border-radius: 2px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = QTabWidget(self)

        # -------------------------------------------------------------
        # Tab 1: Installed Plugins & Extensions
        # -------------------------------------------------------------
        tab_plugins = QWidget()
        plug_layout = QVBoxLayout(tab_plugins)
        plug_layout.setContentsMargins(10, 10, 10, 10)
        plug_layout.setSpacing(10)

        # Top Action Bar
        top_bar = QHBoxLayout()
        self.btn_install_zip = QPushButton("Install from Zip (.zip)...")
        self.btn_install_zip.clicked.connect(self._on_install_zip)
        top_bar.addWidget(self.btn_install_zip)

        self.btn_install_dir = QPushButton("Install from Folder...")
        self.btn_install_dir.clicked.connect(self._on_install_dir)
        top_bar.addWidget(self.btn_install_dir)

        self.btn_open_folder = QPushButton("Open Packages Folder")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        top_bar.addWidget(self.btn_open_folder)

        top_bar.addStretch()

        self.btn_reload = QPushButton("Reload All Plugins")
        self.btn_reload.clicked.connect(self._on_reload_plugins)
        top_bar.addWidget(self.btn_reload)

        plug_layout.addLayout(top_bar)

        # Splitter: Table (Left) + Inspector (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Version", "Status", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # Inspector Panel
        inspector = QWidget()
        insp_layout = QVBoxLayout(inspector)
        insp_layout.setContentsMargins(8, 0, 0, 0)
        insp_layout.setSpacing(8)

        grp_info = QGroupBox("Extension Details")
        form_info = QFormLayout(grp_info)

        self.lbl_det_name = QLabel("-")
        self.lbl_det_name.setStyleSheet("font-weight: bold; color: #e5a823;")
        form_info.addRow("Name:", self.lbl_det_name)

        self.lbl_det_ver = QLabel("-")
        form_info.addRow("Version:", self.lbl_det_ver)

        self.lbl_det_author = QLabel("-")
        form_info.addRow("Author:", self.lbl_det_author)

        self.txt_det_desc = QTextEdit()
        self.txt_det_desc.setReadOnly(True)
        self.txt_det_desc.setMaximumHeight(80)
        form_info.addRow("Description:", self.txt_det_desc)

        self.lbl_det_path = QLabel("-")
        self.lbl_det_path.setStyleSheet("color: #888888; font-size: 10px;")
        self.lbl_det_path.setWordWrap(True)
        form_info.addRow("Path:", self.lbl_det_path)

        insp_layout.addWidget(grp_info)

        # Actions Row
        insp_btn_row = QHBoxLayout()
        self.btn_toggle_enable = QPushButton("Disable Plugin")
        self.btn_toggle_enable.clicked.connect(self._on_toggle_enable_selected)
        insp_btn_row.addWidget(self.btn_toggle_enable)

        self.btn_uninstall = QPushButton("Uninstall")
        self.btn_uninstall.setStyleSheet("background-color: #782828; color: #ffffff;")
        self.btn_uninstall.clicked.connect(self._on_uninstall_selected)
        insp_btn_row.addWidget(self.btn_uninstall)

        insp_btn_row.addStretch()
        insp_layout.addLayout(insp_btn_row)
        insp_layout.addStretch()

        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        plug_layout.addWidget(splitter)
        self.tabs.addTab(tab_plugins, "Installed Plugins & Extensions")

        # -------------------------------------------------------------
        # Tab 2: Software Updates
        # -------------------------------------------------------------
        tab_updates = QWidget()
        upd_layout = QVBoxLayout(tab_updates)
        upd_layout.setContentsMargins(14, 14, 14, 14)
        upd_layout.setSpacing(12)

        grp_version = QGroupBox("OpenReview Version Status")
        ver_layout = QVBoxLayout(grp_version)
        ver_layout.setSpacing(8)

        self.lbl_curr_ver = QLabel(f"<b>Installed Version:</b> <span style='color: #e5a823;'>v{CURRENT_VERSION}</span>")
        self.lbl_curr_ver.setStyleSheet("font-size: 13px;")
        ver_layout.addWidget(self.lbl_curr_ver)

        self.lbl_upd_banner = QLabel("Click 'Check for Updates' to query the release channel.")
        self.lbl_upd_banner.setStyleSheet("""
            background-color: #141414;
            border: 1px solid #333333;
            border-radius: 4px;
            padding: 10px;
            color: #88aaff;
            font-size: 12px;
        """)
        ver_layout.addWidget(self.lbl_upd_banner)

        # Channel selection row
        chan_row = QHBoxLayout()
        chan_row.addWidget(QLabel("Update Channel:"))

        self.combo_channel = QComboBox()
        self.combo_channel.addItem("GitHub Releases (Official)", "github")
        self.combo_channel.addItem("Studio Internal Repository (Custom URL)", "studio")
        self.combo_channel.currentIndexChanged.connect(self._on_channel_changed)
        chan_row.addWidget(self.combo_channel)

        self.txt_custom_url = QLineEdit()
        self.txt_custom_url.setPlaceholderText("https://pipeline.studio.internal/openreview/version.json")
        self.txt_custom_url.hide()
        chan_row.addWidget(self.txt_custom_url, 1)

        self.btn_check_updates = QPushButton("Check for Updates")
        self.btn_check_updates.setStyleSheet("background-color: #27ae60; color: #ffffff; font-weight: bold; padding: 6px 16px;")
        self.btn_check_updates.clicked.connect(self._on_check_updates)
        chan_row.addWidget(self.btn_check_updates)

        ver_layout.addLayout(chan_row)
        upd_layout.addWidget(grp_version)

        # Release Notes & Download
        grp_notes = QGroupBox("Release Notes & Changelog")
        notes_layout = QVBoxLayout(grp_notes)

        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        notes_layout.addWidget(self.txt_notes)

        self.btn_download_update = QPushButton("Download Update")
        self.btn_download_update.setStyleSheet("background-color: #2980b9; color: #ffffff; font-weight: bold; padding: 8px 18px;")
        self.btn_download_update.hide()
        self.btn_download_update.clicked.connect(self._on_download_update)
        notes_layout.addWidget(self.btn_download_update)

        upd_layout.addWidget(grp_notes)

        self.tabs.addTab(tab_updates, "Software Updates")
        layout.addWidget(self.tabs)

        # Bottom Close Row
        btm_row = QHBoxLayout()
        btm_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btm_row.addWidget(btn_close)
        layout.addLayout(btm_row)

        self._current_update_info: Optional[UpdateInfo] = None

    # --------------------------------------------------------------------------
    # Plugin Table Handlers
    # --------------------------------------------------------------------------
    def _refresh_package_table(self) -> None:
        packages = self.pkg_mgr.discover_packages()
        self.table.setRowCount(len(packages))

        for row, p in enumerate(packages):
            item_name = QTableWidgetItem(p.name)
            item_name.setData(Qt.ItemDataRole.UserRole, p.name)
            item_ver = QTableWidgetItem(p.version)

            status_text = "Enabled" if p.enabled else "Disabled"
            item_status = QTableWidgetItem(status_text)
            if p.enabled:
                item_status.setForeground(QColor("#2ecc71"))
            else:
                item_status.setForeground(QColor("#e74c3c"))

            type_text = "Built-in" if p.is_builtin else "User Package"
            item_type = QTableWidgetItem(type_text)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_ver)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_type)

        if packages:
            self.table.selectRow(0)

    def _get_selected_manifest(self) -> Optional[PackageManifest]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        return self.pkg_mgr._manifests.get(name)

    def _on_row_selected(self) -> None:
        p = self._get_selected_manifest()
        if not p:
            self.lbl_det_name.setText("-")
            self.lbl_det_ver.setText("-")
            self.lbl_det_author.setText("-")
            self.txt_det_desc.setPlainText("")
            self.lbl_det_path.setText("-")
            self.btn_uninstall.setEnabled(False)
            self.btn_toggle_enable.setEnabled(False)
            return

        self.lbl_det_name.setText(p.name)
        self.lbl_det_ver.setText(f"v{p.version}")
        self.lbl_det_author.setText(p.author or "Unknown")
        self.txt_det_desc.setPlainText(p.description or "No description provided.")
        self.lbl_det_path.setText(p.package_path)

        self.btn_toggle_enable.setEnabled(True)
        self.btn_toggle_enable.setText("Disable Plugin" if p.enabled else "Enable Plugin")
        self.btn_uninstall.setEnabled(not p.is_builtin)

    def _on_toggle_enable_selected(self) -> None:
        p = self._get_selected_manifest()
        if p:
            self.pkg_mgr.set_package_enabled(p.name, not p.enabled)
            self._refresh_package_table()

    def _on_uninstall_selected(self) -> None:
        p = self._get_selected_manifest()
        if not p:
            return

        reply = QMessageBox.question(
            self,
            "Uninstall Extension",
            f"Are you sure you want to permanently delete plugin '{p.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.pkg_mgr.uninstall_package(p.name)
                self._refresh_package_table()
                QMessageBox.information(self, "Success", f"Plugin '{p.name}' uninstalled.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to uninstall: {e}")

    def _on_install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Install Extension Package", "", "Zip Packages (*.zip);;All Files (*.*)"
        )
        if path:
            try:
                manifest = self.pkg_mgr.install_from_zip(Path(path))
                self._refresh_package_table()
                QMessageBox.information(self, "Success", f"Installed extension '{manifest.name}' v{manifest.version}!")
            except Exception as e:
                QMessageBox.critical(self, "Installation Error", f"Failed to install package:\n{e}")

    def _on_install_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Extension Folder Containing manifest.json")
        if dir_path:
            try:
                manifest = self.pkg_mgr.install_from_dir(Path(dir_path))
                self._refresh_package_table()
                QMessageBox.information(self, "Success", f"Installed extension '{manifest.name}' v{manifest.version}!")
            except Exception as e:
                QMessageBox.critical(self, "Installation Error", f"Failed to install package:\n{e}")

    def _on_open_folder(self) -> None:
        folder = str(self.pkg_mgr.user_packages_dir)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _on_reload_plugins(self) -> None:
        self.pkg_mgr.reload_all()
        self._refresh_package_table()
        QMessageBox.information(self, "Plugins Reloaded", "All active extensions have been reloaded.")

    # --------------------------------------------------------------------------
    # Software Updates Handlers
    # --------------------------------------------------------------------------
    def _on_channel_changed(self, index: int) -> None:
        channel = self.combo_channel.currentData()
        self.txt_custom_url.setVisible(channel == "studio")

    def _on_check_updates(self) -> None:
        self.lbl_upd_banner.setText("Checking for updates...")
        channel = self.combo_channel.currentData()
        custom_url = self.txt_custom_url.text().strip() if channel == "studio" else None

        info = self.updater.check_for_updates(channel=channel, custom_url=custom_url)
        self._current_update_info = info

        if info.error_message:
            self.lbl_upd_banner.setText(f"<span style='color: #e74c3c;'>{info.error_message}</span>")
            self.txt_notes.setPlainText(info.error_message)
            self.btn_download_update.hide()
        elif info.is_update_available:
            self.lbl_upd_banner.setText(
                f"<b style='color: #2ecc71;'>A newer version of OpenReview is available: v{info.latest_version}</b> "
                f"(Current: v{info.current_version})"
            )
            self.txt_notes.setPlainText(f"# {info.release_title}\n\n{info.release_notes}")
            self.btn_download_update.show()
            self.btn_download_update.setText(f"Download OpenReview v{info.latest_version}")
        else:
            self.lbl_upd_banner.setText(
                f"<b style='color: #88aaff;'>OpenReview is up to date!</b> (v{info.current_version} is the latest version)"
            )
            self.txt_notes.setPlainText(f"You are running the latest version: v{info.current_version}\n\n{info.release_notes}")
            self.btn_download_update.hide()

    def _on_download_update(self) -> None:
        if self._current_update_info and self._current_update_info.download_url:
            QDesktopServices.openUrl(QUrl(self._current_update_info.download_url))
