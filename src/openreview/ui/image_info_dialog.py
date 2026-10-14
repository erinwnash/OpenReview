"""
Image Info & Source Details Dialog.
Provides comprehensive VFX metadata readouts: resolution, color depth, pixel aspect ratio,
file paths, frame counts, timecode, codecs, bitrates, audio streams, and container attributes.
"""
from __future__ import annotations

import os
import time
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
    QFrame,
    QScrollArea,
    QApplication,
)


class ImageInfoWidget(QWidget):
    """Studio Image Info and Source Media Details Widget."""

    def __init__(self, media_info: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.info = media_info or {}
        self.setMinimumWidth(440)
        self.setMinimumHeight(480)

        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
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
                min-width: 120px;
            }
            QLabel#val {
                color: #e0e0e0;
                font-size: 11px;
                font-family: Consolas, monospace;
            }
            QPushButton#btn {
                background-color: #2c2c2c;
                color: #dddddd;
                border: 1px solid #444444;
                padding: 5px 14px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btn:hover {
                background-color: #e5a823;
                color: #111111;
            }
            QPushButton#btn_copy {
                background-color: #242424;
                color: #aaaaaa;
                border: 1px solid #3a3a3a;
                padding: 5px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton#btn_copy:hover {
                background-color: #333333;
                color: #ffffff;
                border-color: #666666;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Main Layout created ONCE
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(10, 8, 10, 8)
        self._main_layout.setSpacing(8)

        # Scroll Area created ONCE
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._main_layout.addWidget(self._scroll_area, stretch=1)

        # Bottom Button Bar created ONCE
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_copy = QPushButton("Copy All to Clipboard", self)
        self.btn_copy.setObjectName("btn_copy")
        self.btn_copy.clicked.connect(self._on_copy_all)
        btn_box.addWidget(self.btn_copy)

        btn_box.addStretch()

        self.btn_close = QPushButton("Close", self)
        self.btn_close.setObjectName("btn")
        self.btn_close.clicked.connect(self._on_close_clicked)
        btn_box.addWidget(self.btn_close)

        self._main_layout.addLayout(btn_box)

        # Populate initial content
        self._rebuild_content()

    def update_info(self, media_info: Dict[str, Any]) -> None:
        """Update media info dictionary and dynamically refresh all widgets."""
        self.info = media_info or {}
        self._rebuild_content()

    def _rebuild_content(self) -> None:
        """Construct rich metadata view inside scroll area."""
        content_w = QWidget()
        c_layout = QVBoxLayout(content_w)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(10)

        def add_row(grid: QGridLayout, r: int, label: str, value: str):
            h = QLabel(label)
            h.setObjectName("hdr")
            v = QLabel(value)
            v.setObjectName("val")
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(h, r, 0)
            grid.addWidget(v, r, 1)

        file_path = self.info.get("file_path", "")
        has_file = bool(file_path and os.path.exists(file_path))
        file_name = self.info.get("file_name", os.path.basename(file_path) if has_file else "Synthetic Stream")
        file_dir = self.info.get("file_dir", os.path.dirname(file_path) if has_file else "In-Memory")

        # 1. Source File / Container
        file_grp = QGroupBox("Source File / Media Container", content_w)
        fg_layout = QGridLayout(file_grp)
        fg_layout.setSpacing(5)

        add_row(fg_layout, 0, "Name:", file_name)
        add_row(fg_layout, 1, "Directory:", file_dir)
        add_row(fg_layout, 2, "Media Type:", self.info.get("media_type", "Video / Image Sequence"))

        if has_file:
            size_str = self.info.get("file_size_str")
            if not size_str:
                size_bytes = os.path.getsize(file_path)
                size_mb = size_bytes / (1024.0 * 1024.0)
                size_str = f"{size_mb:.2f} MB ({size_bytes:,} bytes)"
            mod_time = self.info.get("modified_time")
            if not mod_time:
                mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(file_path)))

            add_row(fg_layout, 3, "File Size:", size_str)
            add_row(fg_layout, 4, "Date Modified:", mod_time)
            if self.info.get("created_time"):
                add_row(fg_layout, 5, "Date Created:", self.info["created_time"])
            if self.info.get("format_name"):
                add_row(fg_layout, 6, "Container:", self.info["format_name"])
            if self.info.get("overall_bitrate_str"):
                add_row(fg_layout, 7, "Total Bitrate:", self.info["overall_bitrate_str"])
        else:
            add_row(fg_layout, 3, "Storage:", "In-Memory RAM Frame Buffer")

        c_layout.addWidget(file_grp)

        # 2. Video & Codec Specifications
        v_grp = QGroupBox("Video & Codec Specifications", content_w)
        vg_layout = QGridLayout(v_grp)
        vg_layout.setSpacing(5)

        w = self.info.get("width", 1920)
        h = self.info.get("height", 1080)
        mp = (w * h) / 1_000_000.0 if w and h else 0.0
        aspect = w / max(1.0, float(h)) if w and h else 1.778

        # Standard resolution tag (FHD, UHD, 4K DCI, 2K, etc.)
        res_tag = ""
        if w == 1920 and h == 1080:
            res_tag = " (1080p Full HD)"
        elif w == 3840 and h == 2160:
            res_tag = " (4K UHD-1)"
        elif w == 4096 and h == 2160:
            res_tag = " (4K DCI Native)"
        elif w == 2048 and h == 1080:
            res_tag = " (2K DCI)"
        elif w == 1280 and h == 720:
            res_tag = " (720p HD)"

        add_row(vg_layout, 0, "Resolution:", f"{w} x {h} ({mp:.2f} MP){res_tag}")
        add_row(vg_layout, 1, "Image Aspect:", f"{aspect:.3f}:1")
        add_row(vg_layout, 2, "Pixel Aspect:", f"{self.info.get('pixel_aspect', 1.0):.3f}")

        v_codec = self.info.get("video_codec", "")
        if v_codec:
            codec_tag = self.info.get("video_codec_tag", "")
            codec_display = f"{v_codec} [{codec_tag}]" if codec_tag else v_codec
            add_row(vg_layout, 3, "Video Codec:", codec_display)

        if self.info.get("video_profile"):
            lvl = f", Level {self.info['video_level']}" if self.info.get("video_level") else ""
            add_row(vg_layout, 4, "Profile & Level:", f"{self.info['video_profile']}{lvl}")

        if self.info.get("pixel_format"):
            b_sample = f", {self.info['bits_per_sample']}-bit" if self.info.get("bits_per_sample") else ""
            add_row(vg_layout, 5, "Pixel Format:", f"{self.info['pixel_format']}{b_sample}")
        elif self.info.get("bit_depth"):
            add_row(vg_layout, 5, "Precision / Depth:", str(self.info["bit_depth"]))

        if self.info.get("video_bitrate_str"):
            add_row(vg_layout, 6, "Stream Bitrate:", self.info["video_bitrate_str"])

        if self.info.get("color_space") or self.info.get("color_primaries"):
            cs = self.info.get("color_space", "bt709")
            cp = self.info.get("color_primaries", "")
            cr = self.info.get("color_range", "")
            cs_str = f"{cs}" + (f" (Primaries: {cp})" if cp and cp != cs else "") + (f" | {cr}" if cr else "")
            add_row(vg_layout, 7, "Colorspace / Range:", cs_str)

        if self.info.get("color_transfer"):
            add_row(vg_layout, 8, "Transfer Function:", str(self.info["color_transfer"]))

        if self.info.get("image_format"):
            add_row(vg_layout, 9, "Image Format:", f"{self.info['image_format']} ({self.info.get('image_mode', 'RGBA')})")

        c_layout.addWidget(v_grp)

        # 3. Audio Stream Specifications (if present)
        if self.info.get("audio_codec"):
            a_grp = QGroupBox("Audio Stream Specifications", content_w)
            ag_layout = QGridLayout(a_grp)
            ag_layout.setSpacing(5)

            add_row(ag_layout, 0, "Audio Codec:", self.info.get("audio_codec", "AAC"))
            sr = self.info.get("audio_sample_rate", "")
            sr_str = f"{int(sr):,} Hz" if sr and str(sr).isdigit() else str(sr)
            add_row(ag_layout, 1, "Sample Rate:", sr_str)
            ch = self.info.get("audio_channels", 2)
            ch_layout = self.info.get("audio_channel_layout", "")
            ch_str = f"{ch} Channels" + (f" ({ch_layout})" if ch_layout else "")
            add_row(ag_layout, 2, "Channels:", ch_str)
            if self.info.get("audio_bitrate_str"):
                add_row(ag_layout, 3, "Audio Bitrate:", self.info["audio_bitrate_str"])

            c_layout.addWidget(a_grp)

        # 4. Timeline & Playback
        t_grp = QGroupBox("Timeline & Playback", content_w)
        tg_layout = QGridLayout(t_grp)
        tg_layout.setSpacing(5)

        start = self.info.get("start_frame", 1)
        end = self.info.get("end_frame", 100)
        total = max(1, end - start + 1)
        fps = self.info.get("fps", 24.0)
        dur_sec = total / max(0.1, fps)

        hours = int(dur_sec // 3600)
        mins = int((dur_sec % 3600) // 60)
        secs = int(dur_sec % 60)
        frames_tc = int((dur_sec - int(dur_sec)) * fps)
        tc_str = f"{hours:02d}:{mins:02d}:{secs:02d}:{frames_tc:02d}"

        curr_f = self.info.get("current_frame", start)
        curr_dur = (curr_f - start) / max(0.1, fps)
        curr_tc = f"{int(curr_dur // 3600):02d}:{int((curr_dur % 3600) // 60):02d}:{int(curr_dur % 60):02d}:{int((curr_dur - int(curr_dur)) * fps):02d}"

        add_row(tg_layout, 0, "Sequence Range:", f"[{start} .. {end}] ({total} frames)")
        add_row(tg_layout, 1, "Native FPS:", f"{fps:.2f} fps")
        add_row(tg_layout, 2, "Total Duration:", f"{dur_sec:.2f} sec ({tc_str})")
        add_row(tg_layout, 3, "Current Playhead:", f"Frame {curr_f} ({curr_tc})")
        add_row(tg_layout, 4, "Active In / Out:", f"[{self.info.get('in_frame', start)} .. {self.info.get('out_frame', end)}]")

        c_layout.addWidget(t_grp)

        # 5. Studio OCIO & Viewport Color
        ocio_grp = QGroupBox("Studio OCIO & Viewport Color", content_w)
        og_layout = QGridLayout(ocio_grp)
        og_layout.setSpacing(5)

        add_row(og_layout, 0, "Input Colorspace:", self.info.get("input_space_name", "sRGB (Texture/Video)"))
        add_row(og_layout, 1, "View Transform:", self.info.get("view_transform_name", "sRGB - Display"))
        add_row(og_layout, 2, "Exposure EV:", f"{self.info.get('exposure_ev', 0.0):+.2f} EV")
        add_row(og_layout, 3, "Display Gamma:", f"{self.info.get('gamma', 1.0):.2f}")
        add_row(og_layout, 4, "Channel Mode:", self.info.get("channel_mode_str", "RGB (All Channels)"))

        c_layout.addWidget(ocio_grp)

        # 6. Container / Stream Tags (if present)
        tags = dict(self.info.get("stream_tags", {}))
        tags.update(self.info.get("format_tags", {}))
        tags.update(self.info.get("image_info_tags", {}))

        if tags:
            tag_grp = QGroupBox("Embedded Metadata & Tags", content_w)
            tag_layout = QGridLayout(tag_grp)
            tag_layout.setSpacing(4)
            r = 0
            for k, v in list(tags.items())[:12]:
                add_row(tag_layout, r, f"{k}:", str(v))
                r += 1
            c_layout.addWidget(tag_grp)

        c_layout.addStretch()
        self._scroll_area.setWidget(content_w)

    def _on_copy_all(self) -> None:
        """Copy formatted metadata string to system clipboard."""
        lines = ["=== OpenReview Source Media Details ==="]
        for k, v in sorted(self.info.items()):
            if isinstance(v, dict):
                lines.append(f"\n[{k}]")
                for sub_k, sub_v in v.items():
                    lines.append(f"  {sub_k}: {sub_v}")
            else:
                lines.append(f"{k}: {v}")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.btn_copy.setText("✓ Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, lambda: self.btn_copy.setText("Copy All to Clipboard"))

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_I, Qt.Key.Key_Escape):
            self._on_close_clicked()
            event.accept()
            return
        super().keyPressEvent(event)


class ImageInfoDialog(QDialog):
    """Studio Image Info and Source Media Details Dialog wrapper."""

    def __init__(self, media_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Source Media & Image Details")
        self.resize(500, 580)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.widget = ImageInfoWidget(media_info, self)
        layout.addWidget(self.widget)
        self.info = media_info

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
