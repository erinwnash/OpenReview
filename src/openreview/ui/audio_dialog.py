"""
Audio Settings & Offsets Dialog for OpenReview.
Provides studio controls for audio track volume, mute, scrubbing,
sub-second offsets, frame offsets, and external track loading.
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
    QSlider,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QLabel,
    QGroupBox,
    QFileDialog,
    QMessageBox,
)

from openreview.audio.audio_engine import AudioEngine


class AudioSettingsWidget(QWidget):
    """Studio Audio Control & Track Offset Widget."""

    def __init__(self, audio_engine: AudioEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(400, 360)
        self.setMaximumHeight(480)
        self.engine = audio_engine

        self._setup_ui()
        self._update_from_engine()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1c;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #333333;
                margin-top: 8px;
                padding-top: 12px;
                color: #e5a823;
                font-weight: bold;
            }
            QLabel {
                color: #cccccc;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #121212;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                padding: 4px;
                border-radius: 2px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2b2b2b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #e5a823;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                padding: 6px 14px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #e5a823;
            }
            QPushButton:pressed {
                background-color: #e5a823;
                color: #121212;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
        """ + __import__("openreview.ui.theme", fromlist=["get_spinbox_arrow_stylesheet"]).get_spinbox_arrow_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Track Source Info Box
        grp_track = QGroupBox("Audio Track Source", self)
        track_layout = QVBoxLayout(grp_track)
        self.lbl_track_path = QLabel("No active audio track loaded", grp_track)
        self.lbl_track_path.setWordWrap(True)
        self.lbl_track_path.setStyleSheet("color: #888888; font-size: 11px;")
        track_layout.addWidget(self.lbl_track_path)

        track_btn_layout = QHBoxLayout()
        from openreview.resources import get_vfx_icon
        self.btn_load_audio = QPushButton("Load Audio Track...", grp_track)
        self.btn_load_audio.setIcon(get_vfx_icon("folder"))
        self.btn_load_audio.clicked.connect(self._on_browse_audio)
        track_btn_layout.addWidget(self.btn_load_audio)

        self.btn_unload_audio = QPushButton("✕ Unload", grp_track)
        self.btn_unload_audio.clicked.connect(self._on_unload_audio)
        track_btn_layout.addWidget(self.btn_unload_audio)
        track_layout.addLayout(track_btn_layout)
        layout.addWidget(grp_track)

        # 2. Playback & Scrubbing
        grp_play = QGroupBox("Volume & Scrubbing", self)
        play_layout = QFormLayout(grp_play)

        # Volume Slider
        vol_box = QHBoxLayout()
        self.slider_volume = QSlider(Qt.Orientation.Horizontal, grp_play)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.valueChanged.connect(self._on_volume_slider_changed)
        vol_box.addWidget(self.slider_volume)

        self.lbl_volume = QLabel("100%", grp_play)
        self.lbl_volume.setFixedWidth(40)
        vol_box.addWidget(self.lbl_volume)
        play_layout.addRow("Master Volume:", vol_box)

        # Mute Checkbox
        self.chk_mute = QCheckBox("Mute Audio (M / Ctrl+M)", grp_play)
        self.chk_mute.toggled.connect(self.engine.set_muted)
        play_layout.addRow("", self.chk_mute)

        # Scrubbing Checkbox
        self.chk_scrubbing = QCheckBox("Enable Audio Scrubbing on Timeline Drag", grp_play)
        self.chk_scrubbing.toggled.connect(self.engine.set_scrubbing_enabled)
        play_layout.addRow("", self.chk_scrubbing)
        layout.addWidget(grp_play)

        # 3. Offsets & Lipsync Alignment
        grp_offsets = QGroupBox("Audio Alignment Offsets", self)
        offsets_layout = QFormLayout(grp_offsets)

        self.spin_offset_sec = QDoubleSpinBox(grp_offsets)
        self.spin_offset_sec.setRange(-60.0, 60.0)
        self.spin_offset_sec.setSingleStep(0.01)
        self.spin_offset_sec.setDecimals(3)
        self.spin_offset_sec.setSuffix(" sec")
        self.spin_offset_sec.valueChanged.connect(self.engine.set_offset_seconds)
        offsets_layout.addRow("Offset (Seconds):", self.spin_offset_sec)

        self.spin_offset_frames = QSpinBox(grp_offsets)
        self.spin_offset_frames.setRange(-1000, 1000)
        self.spin_offset_frames.setSingleStep(1)
        self.spin_offset_frames.setSuffix(" frames")
        self.spin_offset_frames.valueChanged.connect(self.engine.set_offset_frames)
        offsets_layout.addRow("Offset (Frames):", self.spin_offset_frames)

        self.btn_reset_offsets = QPushButton("↺ Reset All Offsets", grp_offsets)
        self.btn_reset_offsets.clicked.connect(self._on_reset_offsets)
        offsets_layout.addRow("", self.btn_reset_offsets)
        layout.addWidget(grp_offsets)

        layout.addStretch()

        # Bottom Close button
        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self._on_close_clicked)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

    def _connect_signals(self) -> None:
        self.engine.volume_changed.connect(self._on_engine_volume_changed)
        self.engine.mute_changed.connect(self.chk_mute.setChecked)
        self.engine.offsets_changed.connect(self._on_engine_offsets_changed)
        self.engine.scrubbing_changed.connect(self.chk_scrubbing.setChecked)
        self.engine.track_loaded.connect(self._on_track_loaded)
        self.engine.track_unloaded.connect(self._on_track_unloaded)

    def _update_from_engine(self) -> None:
        vol = self.engine.get_volume()
        self.slider_volume.setValue(int(vol * 100))
        self.lbl_volume.setText(f"{int(vol * 100)}%")
        self.chk_mute.setChecked(self.engine.is_muted())
        self.chk_scrubbing.setChecked(self.engine.is_scrubbing_enabled())
        self.spin_offset_sec.setValue(self.engine.get_offset_seconds())
        self.spin_offset_frames.setValue(self.engine.get_offset_frames())

        path = self.engine.media_path
        if path:
            self.lbl_track_path.setText(f"Track: {Path(path).name}\nPath: {path}")
            self.btn_unload_audio.setEnabled(True)
        else:
            self.lbl_track_path.setText("No active audio track loaded")
            self.btn_unload_audio.setEnabled(False)

    def _on_volume_slider_changed(self, value: int) -> None:
        self.lbl_volume.setText(f"{value}%")
        self.engine.set_volume(value / 100.0)

    def _on_engine_volume_changed(self, vol: float) -> None:
        val = int(vol * 100)
        if self.slider_volume.value() != val:
            self.slider_volume.blockSignals(True)
            self.slider_volume.setValue(val)
            self.slider_volume.blockSignals(False)
        self.lbl_volume.setText(f"{val}%")

    def _on_engine_offsets_changed(self, sec: float, frames: int) -> None:
        if self.spin_offset_sec.value() != sec:
            self.spin_offset_sec.blockSignals(True)
            self.spin_offset_sec.setValue(sec)
            self.spin_offset_sec.blockSignals(False)
        if self.spin_offset_frames.value() != frames:
            self.spin_offset_frames.blockSignals(True)
            self.spin_offset_frames.setValue(frames)
            self.spin_offset_frames.blockSignals(False)

    def _on_reset_offsets(self) -> None:
        self.engine.reset_offsets()
        self.spin_offset_sec.setValue(0.0)
        self.spin_offset_frames.setValue(0)

    def _on_browse_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio Track",
            "",
            "Audio & Video Files (*.wav *.mp3 *.aac *.flac *.m4a *.mov *.mp4 *.mkv);;All Files (*.*)",
        )
        if path:
            success = self.engine.load_audio(path)
            if not success:
                QMessageBox.warning(self, "Load Failed", f"Could not load audio file:\n{path}")

    def _on_unload_audio(self) -> None:
        self.engine.unload_audio()

    def _on_track_loaded(self, path: str) -> None:
        self.lbl_track_path.setText(f"Track: {Path(path).name}\nPath: {path}")
        self.btn_unload_audio.setEnabled(True)

    def _on_track_unloaded(self) -> None:
        self.lbl_track_path.setText("No active audio track loaded")
        self.btn_unload_audio.setEnabled(False)


class AudioSettingsDialog(QDialog):
    """Studio Audio Control & Track Offset Dialog wrapper."""

    def __init__(self, audio_engine: AudioEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Audio Settings & Offsets - OpenReview")
        self.resize(460, 460)
        self.setStyleSheet("background-color: #1c1c1c;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.widget = AudioSettingsWidget(audio_engine, self)
        layout.addWidget(self.widget)
        self.engine = audio_engine

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


