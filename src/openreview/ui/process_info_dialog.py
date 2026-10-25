"""
Process Info & Playback Performance Metrics Dialog.
Provides real-time system performance telemetry: FPS stability, dropped frames,
RAM cache utilization, GPU renderer details, and GLSL pipeline state.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QProgressBar,
    QScrollArea,
)

from openreview.widgets.draggable_scroll_area import BlenderScrollArea


class ProcessInfoDialog(QDialog):
    """Studio Process Info & Playback Performance Diagnostics."""

    def __init__(self, metrics: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Process Info & Playback Performance")
        self.resize(500, 520)
        self.setMinimumWidth(440)
        self.metrics = metrics

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1c;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 12px;
                font-size: 11px;
                font-weight: bold;
                color: #e5a823;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel#hdr {
                color: #888888;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#val {
                color: #e0e0e0;
                font-size: 11px;
                font-family: monospace;
            }
            QProgressBar {
                border: 1px solid #333333;
                border-radius: 2px;
                background-color: #222222;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #e5a823;
            }
            QPushButton#btn {
                background-color: #2c2c2c;
                color: #dddddd;
                border: 1px solid #444444;
                padding: 6px 16px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btn:hover {
                background-color: #e5a823;
                color: #111111;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        scroll = BlenderScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content_w = QWidget(scroll)
        c_layout = QVBoxLayout(content_w)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(12)

        def add_row(grid: QGridLayout, r: int, label: str, value: str):
            h = QLabel(label)
            h.setObjectName("hdr")
            v = QLabel(value)
            v.setObjectName("val")
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(h, r, 0)
            grid.addWidget(v, r, 1)

        # 1. Playback Engine Telemetry
        play_grp = QGroupBox("Playback Performance", content_w)
        pg_layout = QGridLayout(play_grp)
        pg_layout.setSpacing(6)

        target_fps = self.metrics.get("target_fps", 24.0)
        measured_fps = self.metrics.get("measured_fps", target_fps)
        stability = (measured_fps / max(0.1, target_fps)) * 100.0

        add_row(pg_layout, 0, "Target FPS:", f"{target_fps:.2f} fps")
        add_row(pg_layout, 1, "Measured FPS:", f"{measured_fps:.2f} fps ({min(100.0, stability):.1f}% real-time)")
        add_row(pg_layout, 2, "Dropped Frames:", str(self.metrics.get("dropped_frames", 0)))
        add_row(pg_layout, 3, "Frame Time:", f"{1000.0 / max(0.1, measured_fps):.2f} ms")
        add_row(pg_layout, 4, "Loop Mode:", str(self.metrics.get("loop_mode", "Loop")))

        c_layout.addWidget(play_grp)

        # 2. RAM Cache Utilization
        cache_grp = QGroupBox("RAM Cache Utilization", content_w)
        cg_layout = QVBoxLayout(cache_grp)
        cg_layout.setSpacing(6)

        used_mb = self.metrics.get("cache_used_mb", 0.0)
        max_mb = self.metrics.get("cache_max_mb", 2048.0)
        mode = self.metrics.get("cache_mode", "Off")
        pct = int(min(100.0, (used_mb / max(1.0, max_mb)) * 100.0))

        c_info = QLabel(f"Mode: {mode} | Used: {used_mb:.1f} MB / {max_mb:.0f} MB ({pct}%)")
        c_info.setStyleSheet("color: #cccccc; font-size: 11px;")
        cg_layout.addWidget(c_info)

        bar = QProgressBar(cache_grp)
        bar.setRange(0, 100)
        bar.setValue(pct)
        cg_layout.addWidget(bar)

        c_layout.addWidget(cache_grp)

        # 3. GPU Hardware & OpenGL Pipeline
        gpu_grp = QGroupBox("OpenGL GPU Pipeline", content_w)
        gg_layout = QGridLayout(gpu_grp)
        gg_layout.setSpacing(6)

        add_row(gg_layout, 0, "GPU Vendor:", self.metrics.get("gl_vendor", "OpenGL Hardware"))
        add_row(gg_layout, 1, "Renderer:", self.metrics.get("gl_renderer", "Core Profile 3.3"))
        add_row(gg_layout, 2, "GLSL Version:", "#version 330 core")
        add_row(gg_layout, 3, "Texture Precision:", "RGBA32F (Float32)")
        add_row(gg_layout, 4, "Active 3D LUT:", "Bound (Texture Unit 2)" if self.metrics.get("has_lut") else "None")
        add_row(gg_layout, 5, "Active ASC CDL:", "Active" if self.metrics.get("has_cdl") else "None")

        c_layout.addWidget(gpu_grp)

        # 4. Host & Process
        sys_grp = QGroupBox("Host System", content_w)
        sg_layout = QGridLayout(sys_grp)
        sg_layout.setSpacing(6)

        add_row(sg_layout, 0, "Process ID (PID):", str(os.getpid()))
        add_row(sg_layout, 1, "Python Version:", sys.version.split()[0])
        add_row(sg_layout, 2, "Platform:", sys.platform)

        c_layout.addWidget(sys_grp)

        scroll.setWidget(content_w)
        layout.addWidget(scroll, stretch=1)

        # Close button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Close", self)
        btn_close.setObjectName("btn")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
