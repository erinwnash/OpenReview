"""
Custom Studio OCIO Configuration Dialog for OpenReview.
Allows loading studio config.ocio files, configuring working colorspaces,
selecting display/view transforms, and inspecting roles and looks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QListWidget,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QTabWidget,
)

from openreview.color.ocio_manager import OCIOManager
from openreview.core.preferences import PreferencesManager


class OCIOConfigWidget(QWidget):
    """Studio OpenColorIO v2 Configuration Widget."""

    def __init__(self, ocio_manager: OCIOManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(440, 360)
        self.setMaximumHeight(500)
        self.ocio = ocio_manager

        self._setup_ui()
        self._populate_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
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
            QLineEdit, QComboBox {
                background-color: #121212;
                border: 1px solid #383838;
                color: #ffffff;
                padding: 4px;
                border-radius: 2px;
            }
            QListWidget {
                background-color: #121212;
                border: 1px solid #2e2e2e;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #282828;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                padding: 6px 14px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #e5a823;
            }
            QPushButton:pressed {
                background-color: #e5a823;
                color: #121212;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background: #1e1e1e;
            }
            QTabBar::tab {
                background: #141414;
                color: #888888;
                padding: 6px 14px;
                border: 1px solid #2e2e2e;
            }
            QTabBar::tab:selected {
                background: #282828;
                color: #e5a823;
                font-weight: bold;
            }
        """ + __import__("openreview.ui.theme", fromlist=["get_spinbox_arrow_stylesheet"]).get_spinbox_arrow_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Config File Selection Box
        grp_file = QGroupBox("Studio Config File", self)
        file_layout = QVBoxLayout(grp_file)

        path_box = QHBoxLayout()
        self.edit_path = QLineEdit(self.ocio.config_path or "Built-in ACES Studio Configuration", grp_file)
        self.edit_path.setReadOnly(True)
        path_box.addWidget(self.edit_path, stretch=3)

        self.btn_browse = QPushButton("📁 Browse...", grp_file)
        self.btn_browse.clicked.connect(self._on_browse_config)
        path_box.addWidget(self.btn_browse)

        self.btn_reset = QPushButton("↺ Built-in", grp_file)
        self.btn_reset.setToolTip("Reset to built-in ACEScg analytical pipeline")
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        path_box.addWidget(self.btn_reset)
        file_layout.addLayout(path_box)

        self.lbl_info = QLabel(f"Active: {self.ocio.config_name}", grp_file)
        self.lbl_info.setStyleSheet("color: #888888; font-size: 11px;")
        file_layout.addWidget(self.lbl_info)
        layout.addWidget(grp_file)

        # 2. Working Space & View Selection
        grp_settings = QGroupBox("Active View & Transform Settings", self)
        form_layout = QFormLayout(grp_settings)

        self.combo_space = QComboBox(grp_settings)
        form_layout.addRow("Input Space:", self.combo_space)

        self.combo_display = QComboBox(grp_settings)
        self.combo_display.currentIndexChanged.connect(self._on_display_changed)
        form_layout.addRow("Active Display:", self.combo_display)

        self.combo_view = QComboBox(grp_settings)
        form_layout.addRow("Display View:", self.combo_view)
        layout.addWidget(grp_settings)

        # 3. Tabs: ColorSpaces, Roles, Looks, Search Paths, Context Vars
        self.tabs = QTabWidget(self)

        self.list_spaces = QListWidget(self)
        self.tabs.addTab(self.list_spaces, "Colorspaces")

        self.list_roles = QListWidget(self)
        self.tabs.addTab(self.list_roles, "Roles")

        self.list_looks = QListWidget(self)
        self.tabs.addTab(self.list_looks, "Looks")

        # Tab: Search Paths / LUT Dirs
        tab_sp = QWidget(self)
        layout_sp = QVBoxLayout(tab_sp)
        layout_sp.setContentsMargins(6, 6, 6, 6)
        layout_sp.setSpacing(6)
        self.list_sp = QListWidget(tab_sp)
        layout_sp.addWidget(self.list_sp)
        sp_btns = QHBoxLayout()
        self.btn_add_sp = QPushButton("📁 Add LUT Directory...", tab_sp)
        self.btn_add_sp.clicked.connect(self._on_add_search_path)
        self.btn_remove_sp = QPushButton("Remove", tab_sp)
        self.btn_remove_sp.clicked.connect(self._on_remove_search_path)
        sp_btns.addWidget(self.btn_add_sp)
        sp_btns.addWidget(self.btn_remove_sp)
        sp_btns.addStretch()
        layout_sp.addLayout(sp_btns)
        self.tabs.addTab(tab_sp, "LUT Search Paths")

        # Tab: Context Variables
        tab_ctx = QWidget(self)
        layout_ctx = QVBoxLayout(tab_ctx)
        layout_ctx.setContentsMargins(6, 6, 6, 6)
        layout_ctx.setSpacing(6)
        self.list_ctx = QListWidget(tab_ctx)
        layout_ctx.addWidget(self.list_ctx)
        ctx_edit_box = QHBoxLayout()
        self.edit_ctx_key = QLineEdit(tab_ctx)
        self.edit_ctx_key.setPlaceholderText("Key (e.g. SHOT)")
        self.edit_ctx_val = QLineEdit(tab_ctx)
        self.edit_ctx_val.setPlaceholderText("Value (e.g. sh010)")
        self.btn_set_ctx = QPushButton("Set", tab_ctx)
        self.btn_set_ctx.clicked.connect(self._on_set_context_var)
        self.btn_del_ctx = QPushButton("Remove", tab_ctx)
        self.btn_del_ctx.clicked.connect(self._on_del_context_var)
        ctx_edit_box.addWidget(self.edit_ctx_key)
        ctx_edit_box.addWidget(self.edit_ctx_val)
        ctx_edit_box.addWidget(self.btn_set_ctx)
        ctx_edit_box.addWidget(self.btn_del_ctx)
        layout_ctx.addLayout(ctx_edit_box)
        self.tabs.addTab(tab_ctx, "Context Variables")

        layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_bar = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Configuration", self)
        self.btn_apply.setStyleSheet("background-color: #e5a823; color: #121212; font-weight: bold;")
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        btn_bar.addWidget(self.btn_apply)

        btn_bar.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self._on_close_clicked)
        btn_bar.addWidget(btn_close)
        layout.addLayout(btn_bar)

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

    def _populate_ui(self) -> None:
        path = self.ocio.config_path
        self.edit_path.setText(path if path else "Built-in ACES Studio Configuration")
        self.lbl_info.setText(f"Active Config: {self.ocio.config_name} (OCIO Available: {self.ocio.has_ocio})")

        # ColorSpaces
        spaces = self.ocio.get_color_spaces()
        self.combo_space.blockSignals(True)
        self.combo_space.clear()
        self.combo_space.addItems(spaces)
        if self.ocio.input_space in spaces:
            self.combo_space.setCurrentText(self.ocio.input_space)
        self.combo_space.blockSignals(False)

        self.list_spaces.clear()
        self.list_spaces.addItems(spaces)

        # Displays
        displays = self.ocio.get_displays()
        self.combo_display.blockSignals(True)
        self.combo_display.clear()
        self.combo_display.addItems(displays)
        if self.ocio.display in displays:
            self.combo_display.setCurrentText(self.ocio.display)
        self.combo_display.blockSignals(False)

        self._on_display_changed()

        # Roles
        self.list_roles.clear()
        roles = self.ocio.get_roles()
        for r, cs in roles.items():
            self.list_roles.addItem(f"{r}: {cs}")
        if not roles:
            self.list_roles.addItem("No specific roles declared")

        # Looks
        self.list_looks.clear()
        looks = self.ocio.get_looks()
        self.list_looks.addItems(looks if looks else ["No custom looks declared"])

        # Search Paths
        self.list_sp.clear()
        search_paths = self.ocio.get_search_paths()
        for sp in search_paths:
            self.list_sp.addItem(sp)

        # Context Vars
        self.list_ctx.clear()
        for k, v in self.ocio.get_context_vars().items():
            self.list_ctx.addItem(f"{k} = {v}")

    def _on_display_changed(self) -> None:
        disp = self.combo_display.currentText()
        views = self.ocio.get_views(disp)
        self.combo_view.blockSignals(True)
        self.combo_view.clear()
        self.combo_view.addItems(views)
        if self.ocio.view in views:
            self.combo_view.setCurrentText(self.ocio.view)
        self.combo_view.blockSignals(False)

    def _on_browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OCIO Configuration File",
            "",
            "OCIO Config (*.ocio);;All Files (*.*)",
        )
        if path:
            success = self.ocio.load_config(path)
            if success:
                self._populate_ui()
                QMessageBox.information(self, "OCIO Config Loaded", f"Loaded OCIO configuration:\n{Path(path).name}")
            else:
                QMessageBox.warning(self, "Load Failed", f"Could not load OCIO file:\n{path}")

    def _on_reset_clicked(self) -> None:
        self.ocio.reset_to_default()
        self._populate_ui()
        QMessageBox.information(self, "Reset Config", "Reset to built-in ACES pipeline.")

    def _on_add_search_path(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select LUT / Transform Search Directory")
        if d:
            self.ocio.add_search_path(d)
            self._populate_ui()

    def _on_remove_search_path(self) -> None:
        item = self.list_sp.currentItem()
        if item:
            self.ocio.remove_search_path(item.text())
            self._populate_ui()

    def _on_set_context_var(self) -> None:
        k = self.edit_ctx_key.text().strip()
        v = self.edit_ctx_val.text().strip()
        if k:
            self.ocio.set_context_var(k, v)
            self.edit_ctx_key.clear()
            self.edit_ctx_val.clear()
            self._populate_ui()

    def _on_del_context_var(self) -> None:
        item = self.list_ctx.currentItem()
        if item and "=" in item.text():
            k = item.text().split("=")[0].strip()
            self.ocio.remove_context_var(k)
            self._populate_ui()

    def _on_apply_clicked(self) -> None:
        self.ocio.input_space = self.combo_space.currentText()
        self.ocio.display = self.combo_display.currentText()
        self.ocio.view = self.combo_view.currentText()

        # Persist to user preferences
        try:
            prefs = PreferencesManager.instance().prefs
            prefs.ocio_config_path = self.ocio.config_path or ""
            prefs.ocio_display = self.ocio.display
            prefs.ocio_view = self.ocio.view
            prefs.ocio_input_space = self.ocio.input_space
            prefs.ocio_lut_paths = self.ocio.get_search_paths()
            PreferencesManager.instance().save(prefs)
        except Exception as e:
            print(f"[OCIOConfigWidget] Could not save preferences: {e}")

        self._on_close_clicked()


class OCIOConfigDialog(QDialog):
    """Studio OpenColorIO v2 Configuration Dialog wrapper."""

    def __init__(self, ocio_manager: OCIOManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("OpenColorIO Configuration - OpenReview")
        self.resize(560, 500)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.widget = OCIOConfigWidget(ocio_manager, self)
        layout.addWidget(self.widget)
        self.ocio = ocio_manager

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


