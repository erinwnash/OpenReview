"""
Multi-User Remote Dailies Sync Dialog for OpenReview.
Enables studio artists to host or join live collaborative review sessions,
share presenter control, view online peers, and chat in real time.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime

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
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QListWidget,
    QTextEdit,
    QCheckBox,
    QGroupBox,
    QTabWidget,
    QMessageBox,
    QFileDialog,
)

from openreview.network.sync_engine import DailiesSyncEngine


class DailiesSyncWidget(QWidget):
    """Studio Multi-User Dailies Synchronization Widget."""

    def __init__(self, sync_engine: DailiesSyncEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(420, 360)
        self.setMaximumHeight(500)
        self.engine = sync_engine

        self._setup_ui()
        self._update_from_engine()
        self._connect_signals()

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
            QLineEdit, QSpinBox {
                background-color: #121212;
                border: 1px solid #383838;
                color: #ffffff;
                padding: 4px;
                border-radius: 2px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #e5a823;
            }
            QListWidget, QTextEdit {
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
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #e5a823;
            }
            QPushButton:pressed {
                background-color: #e5a823;
                color: #121212;
            }
            QPushButton#primary_btn {
                background-color: #b8861b;
                color: #ffffff;
                border-color: #e5a823;
                font-weight: bold;
            }
            QPushButton#primary_btn:hover {
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Tabs: Session Setup & Participants / Review Chat
        self.tabs = QTabWidget(self)

        # TAB 1: Session & Participants
        tab_session = QWidget(self)
        layout_sess = QVBoxLayout(tab_session)
        layout_sess.setContentsMargins(10, 10, 10, 10)
        layout_sess.setSpacing(10)

        # Mode Selection
        mode_box = QHBoxLayout()
        self.radio_host = QRadioButton("Host Dailies Session", tab_session)
        self.radio_join = QRadioButton("Join Existing Session", tab_session)
        self.radio_host.setChecked(True)
        self.radio_host.toggled.connect(self._on_mode_toggled)

        mode_group = QButtonGroup(tab_session)
        mode_group.addButton(self.radio_host)
        mode_group.addButton(self.radio_join)
        mode_box.addWidget(self.radio_host)
        mode_box.addWidget(self.radio_join)
        mode_box.addStretch()
        layout_sess.addLayout(mode_box)

        # Configuration Box
        grp_conn = QGroupBox("Connection Settings", tab_session)
        form_conn = QFormLayout(grp_conn)

        self.edit_room = QLineEdit(self.engine.room_name or "VFX Review Main", grp_conn)
        form_conn.addRow("Review Room:", self.edit_room)

        self.edit_user = QLineEdit("Artist", grp_conn)
        form_conn.addRow("Your Name:", self.edit_user)

        self.edit_host = QLineEdit("127.0.0.1", grp_conn)
        form_conn.addRow("Host IP / Hostname:", self.edit_host)

        self.spin_port = QSpinBox(grp_conn)
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(9090)
        form_conn.addRow("Port:", self.spin_port)

        btn_conn_box = QHBoxLayout()
        self.btn_connect = QPushButton("Start Hosting", grp_conn)
        self.btn_connect.setObjectName("primary_btn")
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        btn_conn_box.addWidget(self.btn_connect)

        self.lbl_status = QLabel("🔴 Offline", grp_conn)
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        btn_conn_box.addWidget(self.lbl_status)
        btn_conn_box.addStretch()
        form_conn.addRow("", btn_conn_box)
        layout_sess.addWidget(grp_conn)

        # Collaboration Controls Box
        grp_collab = QGroupBox("Collaboration & Presenter", tab_session)
        collab_layout = QVBoxLayout(grp_collab)

        pres_row = QHBoxLayout()
        self.lbl_presenter = QLabel("Current Presenter: None", grp_collab)
        self.lbl_presenter.setStyleSheet("font-weight: bold; color: #e5a823;")
        pres_row.addWidget(self.lbl_presenter)
        pres_row.addStretch()

        self.btn_take_presenter = QPushButton("👑 Take Control", grp_collab)
        self.btn_take_presenter.clicked.connect(self.engine.request_presenter)
        pres_row.addWidget(self.btn_take_presenter)

        self.btn_pass_presenter = QPushButton("🤝 Pass Control", grp_collab)
        self.btn_pass_presenter.setToolTip("Pass presenter role to selected participant in peer list")
        self.btn_pass_presenter.clicked.connect(self._on_pass_presenter_clicked)
        pres_row.addWidget(self.btn_pass_presenter)
        collab_layout.addLayout(pres_row)

        self.chk_follow = QCheckBox("Follow Presenter Playback, Scrubbing & Colors", grp_collab)
        self.chk_follow.setChecked(True)
        self.chk_follow.toggled.connect(self.engine.set_following)
        collab_layout.addWidget(self.chk_follow)

        collab_layout.addWidget(QLabel("Active Participants in Review Room:", grp_collab))
        self.list_peers = QListWidget(grp_collab)
        collab_layout.addWidget(self.list_peers)
        layout_sess.addWidget(grp_collab)

        self.tabs.addTab(tab_session, "Session & Participants")

        # TAB 2: Dailies Chat & Review Feed
        tab_chat = QWidget(self)
        layout_chat = QVBoxLayout(tab_chat)
        layout_chat.setContentsMargins(10, 10, 10, 10)
        layout_chat.setSpacing(8)

        self.txt_chat_history = QTextEdit(tab_chat)
        self.txt_chat_history.setReadOnly(True)
        layout_chat.addWidget(self.txt_chat_history)

        chat_input_box = QHBoxLayout()
        self.edit_message = QLineEdit(tab_chat)
        self.edit_message.setPlaceholderText("Type a message or review comment to the room...")
        self.edit_message.returnPressed.connect(self._on_send_chat)
        chat_input_box.addWidget(self.edit_message)

        self.btn_send_chat = QPushButton("Send", tab_chat)
        self.btn_send_chat.clicked.connect(self._on_send_chat)
        chat_input_box.addWidget(self.btn_send_chat)
        layout_chat.addLayout(chat_input_box)

        chat_tools_box = QHBoxLayout()
        self.btn_export_chat = QPushButton("Save Chat Log...", tab_chat)
        self.btn_export_chat.clicked.connect(self._on_export_chat_clicked)
        chat_tools_box.addWidget(self.btn_export_chat)

        self.btn_clear_chat = QPushButton("Clear", tab_chat)
        self.btn_clear_chat.clicked.connect(self.txt_chat_history.clear)
        chat_tools_box.addWidget(self.btn_clear_chat)
        chat_tools_box.addStretch()
        layout_chat.addLayout(chat_tools_box)

        self.tabs.addTab(tab_chat, "Review Chat")

        main_layout.addWidget(self.tabs)

        # Bottom Close Button
        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self._on_close_clicked)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

        self._on_mode_toggled()

    def _connect_signals(self) -> None:
        self.engine.status_changed.connect(self._on_status_changed)
        self.engine.mode_changed.connect(self._on_mode_changed)
        self.engine.peer_list_updated.connect(self._on_peer_list_updated)
        self.engine.presenter_changed.connect(self._on_presenter_changed)
        self.engine.room_info_updated.connect(self._on_room_info_updated)
        self.engine.chat_message_received.connect(self._on_chat_received)

    def _update_from_engine(self) -> None:
        self.edit_user.setText(self.engine.username)
        self.edit_room.setText(self.engine.room_name)
        self.chk_follow.setChecked(self.engine.is_following)
        self._on_presenter_changed(self.engine.presenter)

        if self.engine.is_connected:
            self.lbl_status.setText(f"🟢 {self.engine.mode.capitalize()}")
            self.lbl_status.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.btn_connect.setText("Disconnect")
        else:
            self.lbl_status.setText("🔴 Offline")
            self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.btn_connect.setText("Start Hosting" if self.radio_host.isChecked() else "Join Session")

    def _on_mode_toggled(self) -> None:
        is_host = self.radio_host.isChecked()
        self.edit_host.setEnabled(not is_host)
        if not self.engine.is_connected:
            self.btn_connect.setText("Start Hosting" if is_host else "Join Session")

    def _on_connect_clicked(self) -> None:
        if self.engine.is_connected:
            self.engine.disconnect_session()
            return

        user = self.edit_user.text().strip() or "Artist"
        room = self.edit_room.text().strip() or "VFX Review Main"
        port = self.spin_port.value()

        if self.radio_host.isChecked():
            success = self.engine.start_host(port=port, username=user, room_name=room)
            if not success:
                QMessageBox.critical(self, "Host Failed", f"Could not bind to port {port}.")
        else:
            host = self.edit_host.text().strip() or "127.0.0.1"
            self.engine.join_host(host=host, port=port, username=user, room_name=room)

    def _on_room_info_updated(self, room_name: str) -> None:
        self.edit_room.setText(room_name)

    def _on_pass_presenter_clicked(self) -> None:
        item = self.list_peers.currentItem()
        if not item:
            QMessageBox.information(self, "Select Participant", "Please select a peer from the participants list first.")
            return
        target_user = item.text().replace(" (Host)", "").replace(" 👑", "").strip()
        self.engine.grant_presenter(target_user)

    def _on_export_chat_clicked(self) -> None:
        text = self.txt_chat_history.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Chat Log", "No chat messages to save.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Review Chat Log",
            f"dailies_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                QMessageBox.information(self, "Chat Log Saved", f"Chat saved successfully to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not write file:\n{e}")

    def _on_status_changed(self, connected: bool, text: str) -> None:
        if connected:
            self.lbl_status.setText(f"🟢 {self.engine.mode.capitalize()}")
            self.lbl_status.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.btn_connect.setText("Disconnect")
        else:
            self.lbl_status.setText("🔴 Offline")
            self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.btn_connect.setText("Start Hosting" if self.radio_host.isChecked() else "Join Session")
            self.list_peers.clear()

    def _on_mode_changed(self, mode: str) -> None:
        self.btn_take_presenter.setEnabled(mode in ("host", "client"))

    def _on_peer_list_updated(self, peers: list) -> None:
        self.list_peers.clear()
        for p in peers:
            self.list_peers.addItem(p)

    def _on_presenter_changed(self, presenter: str) -> None:
        self.lbl_presenter.setText(f"Current Presenter: {presenter}")

    def _on_send_chat(self) -> None:
        text = self.edit_message.text().strip()
        if not text:
            return
        self.engine.broadcast_chat(text)
        self.edit_message.clear()

    def _on_chat_received(self, sender: str, text: str) -> None:
        now_str = datetime.now().strftime("%H:%M:%S")
        self.txt_chat_history.append(f"[{now_str}] <b>{sender}</b>: {text}")


class DailiesSyncDialog(QDialog):
    """Studio Multi-User Dailies Synchronization Dialog wrapper."""

    def __init__(self, sync_engine: DailiesSyncEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Multi-User Remote Dailies Sync - OpenReview")
        self.resize(560, 520)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.widget = DailiesSyncWidget(sync_engine, self)
        layout.addWidget(self.widget)
        self.engine = sync_engine

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


