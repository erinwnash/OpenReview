"""
OpenReview Media Export Engine.
Exports QuickTime movies (.mov / .mp4) and Image Sequences (.png / .jpg)
with optional WYSIWYG burn-in of annotations, color transforms, and mattes.
"""
from __future__ import annotations

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Callable, Optional, Tuple, Dict, Any
import numpy as np
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import OpenEXR
    import Imath
    HAS_OPENEXR = True
except ImportError:
    HAS_OPENEXR = False


class MediaExporter:
    """Handles disk writing for single frames, sequences, and video containers."""

    @staticmethod
    def _to_uint8(image_data: np.ndarray) -> np.ndarray:
        """Convert numpy array to uint8 RGB (0..255)."""
        if image_data.dtype == np.uint8:
            return image_data[:, :, :3]
        if image_data.dtype == np.uint16:
            return (image_data[:, :, :3] >> 8).astype(np.uint8)
        return np.clip(image_data[:, :, :3] * 255.0, 0, 255).astype(np.uint8)

    @staticmethod
    def resize_frame(image: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """High-quality downscaling/upscaling using Area/Lanczos resampling."""
        h, w = image.shape[:2]
        if w == target_w and h == target_h:
            return image
        if HAS_CV2:
            interp = cv2.INTER_AREA if (target_w <= w and target_h <= h) else cv2.INTER_LANCZOS4
            return cv2.resize(image, (target_w, target_h), interpolation=interp)
        else:
            if image.dtype != np.uint8:
                u8 = MediaExporter._to_uint8(image)
                pil_img = Image.fromarray(u8).resize((target_w, target_h), Image.Resampling.LANCZOS)
                return np.array(pil_img)
            else:
                pil_img = Image.fromarray(image).resize((target_w, target_h), Image.Resampling.LANCZOS)
                return np.array(pil_img)

    @staticmethod
    def save_exr(
        file_path: str | Path,
        image_data: np.ndarray,
        compression: str = "zip",
        bit_depth: str = "16",
    ) -> None:
        """Save a float32 or float16 RGB/RGBA numpy array to an OpenEXR file."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        if not HAS_OPENEXR:
            if HAS_CV2:
                bgr = cv2.cvtColor(image_data.astype(np.float32), cv2.COLOR_RGB2BGR) if image_data.ndim >= 3 and image_data.shape[2] >= 3 else image_data
                cv2.imwrite(str(p), bgr)
                return
            raise RuntimeError("OpenEXR or OpenCV is required for EXR export.")

        h, w = image_data.shape[:2]
        header = OpenEXR.Header(w, h)

        comp_lower = str(compression).lower()
        if comp_lower == "piz":
            header['compression'] = Imath.Compression(Imath.Compression.PIZ_COMPRESSION)
        elif comp_lower == "rle":
            header['compression'] = Imath.Compression(Imath.Compression.RLE_COMPRESSION)
        elif comp_lower == "dwaa":
            header['compression'] = Imath.Compression(Imath.Compression.DWAA_COMPRESSION)
        elif comp_lower == "dwab":
            header['compression'] = Imath.Compression(Imath.Compression.DWAB_COMPRESSION)
        elif comp_lower in ("none", "uncompressed"):
            header['compression'] = Imath.Compression(Imath.Compression.NO_COMPRESSION)
        else:
            header['compression'] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)

        is_half = str(bit_depth).strip() in ("16", "half", "Half")
        pt = Imath.PixelType(Imath.PixelType.HALF if is_half else Imath.PixelType.FLOAT)
        dtype = np.float16 if is_half else np.float32

        has_alpha = (image_data.ndim >= 3 and image_data.shape[2] >= 4)
        if has_alpha:
            header['channels'] = {
                'R': Imath.Channel(pt),
                'G': Imath.Channel(pt),
                'B': Imath.Channel(pt),
                'A': Imath.Channel(pt),
            }
            r = image_data[:, :, 0].astype(dtype, copy=False).tobytes()
            g = image_data[:, :, 1].astype(dtype, copy=False).tobytes()
            b = image_data[:, :, 2].astype(dtype, copy=False).tobytes()
            a = image_data[:, :, 3].astype(dtype, copy=False).tobytes()
            pixels = {'R': r, 'G': g, 'B': b, 'A': a}
        else:
            header['channels'] = {
                'R': Imath.Channel(pt),
                'G': Imath.Channel(pt),
                'B': Imath.Channel(pt),
            }
            r = image_data[:, :, 0].astype(dtype, copy=False).tobytes()
            g = image_data[:, :, 1].astype(dtype, copy=False).tobytes()
            b = image_data[:, :, 2].astype(dtype, copy=False).tobytes()
            pixels = {'R': r, 'G': g, 'B': b}

        out = OpenEXR.OutputFile(str(p), header)
        try:
            out.writePixels(pixels)
        finally:
            out.close()

    @staticmethod
    def save_dpx(
        file_path: str | Path,
        image_data: np.ndarray,
        bit_depth: int = 10,
    ) -> None:
        """Save an image array to a standard 10-bit or 16-bit SMPTE 268M DPX file."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        from openreview.core.image_io import write_dpx
        if image_data.dtype == np.uint8:
            arr = image_data.astype(np.float32) / 255.0
        elif image_data.dtype == np.uint16:
            arr = image_data.astype(np.float32) / 65535.0
        else:
            arr = image_data.astype(np.float32)
        success = write_dpx(str(p), arr, bit_depth=bit_depth)
        if not success:
            raise RuntimeError(f"Failed to write DPX file to {p}")

    @staticmethod
    def save_image_file(
        image_data: np.ndarray,
        file_path: str | Path,
        compression: str = "zip",
        bit_depth: str = "16",
        quality: int = 95,
    ) -> None:
        """Save image array to disk in EXR, DPX, TIFF, PNG, JPEG, or Targa format."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        ext = p.suffix.lower()

        if ext == ".exr":
            if image_data.dtype == np.uint8:
                f_img = image_data.astype(np.float32) / 255.0
            elif image_data.dtype == np.uint16:
                f_img = image_data.astype(np.float32) / 65535.0
            else:
                f_img = image_data.astype(np.float32)
            MediaExporter.save_exr(p, f_img, compression=compression, bit_depth=bit_depth)
            return

        if ext == ".dpx":
            bd = 16 if str(bit_depth).strip() == "16" else 10
            MediaExporter.save_dpx(p, image_data, bit_depth=bd)
            return

        if ext in (".tif", ".tiff"):
            if str(bit_depth).strip() == "16":
                if image_data.dtype in (np.float32, np.float64, np.float16):
                    arr_16 = np.clip(image_data * 65535.0, 0, 65535).astype(np.uint16)
                elif image_data.dtype == np.uint8:
                    arr_16 = (image_data.astype(np.uint16) * 257)
                else:
                    arr_16 = image_data.astype(np.uint16)
                if HAS_CV2:
                    bgr = cv2.cvtColor(arr_16, cv2.COLOR_RGB2BGR) if arr_16.ndim >= 3 and arr_16.shape[2] >= 3 else arr_16
                    cv2.imwrite(str(p), bgr)
                else:
                    img = Image.fromarray(arr_16)
                    img.save(str(p))
                return
            else:
                arr_8 = MediaExporter._to_uint8(image_data)
                img = Image.fromarray(arr_8)
                img.save(str(p))
                return

        if ext == ".png":
            if str(bit_depth).strip() == "16":
                if image_data.dtype in (np.float32, np.float64, np.float16):
                    arr_16 = np.clip(image_data * 65535.0, 0, 65535).astype(np.uint16)
                elif image_data.dtype == np.uint8:
                    arr_16 = (image_data.astype(np.uint16) * 257)
                else:
                    arr_16 = image_data.astype(np.uint16)
                if HAS_CV2:
                    bgr = cv2.cvtColor(arr_16, cv2.COLOR_RGB2BGR) if arr_16.ndim >= 3 and arr_16.shape[2] >= 3 else arr_16
                    cv2.imwrite(str(p), bgr)
                else:
                    img = Image.fromarray(arr_16)
                    img.save(str(p))
                return
            else:
                arr_8 = MediaExporter._to_uint8(image_data)
                img = Image.fromarray(arr_8)
                img.save(str(p))
                return

        if ext in (".jpg", ".jpeg"):
            arr_8 = MediaExporter._to_uint8(image_data)
            img = Image.fromarray(arr_8)
            img.save(str(p), quality=int(quality))
            return

        if ext == ".tga":
            arr_8 = MediaExporter._to_uint8(image_data)
            if HAS_CV2:
                bgr = cv2.cvtColor(arr_8, cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(p), bgr)
            else:
                img = Image.fromarray(arr_8)
                img.save(str(p))
            return

        arr_8 = MediaExporter._to_uint8(image_data)
        img = Image.fromarray(arr_8)
        img.save(str(p))

    @staticmethod
    def export_video(
        frame_provider: Callable[[int], np.ndarray],
        frames: List[int],
        output_path: str | Path,
        fps: float = 24.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> str:
        """
        Export frames to a video container (.mov / .mp4) using OpenCV VideoWriter.
        """
        if not HAS_CV2:
            raise RuntimeError("OpenCV (cv2) is required for video export.")

        if not frames:
            raise ValueError("No frames provided for video export.")

        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        first_frame = frame_provider(frames[0])
        h, w = first_frame.shape[:2]

        ext = p.suffix.lower()
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(str(p), fourcc, float(fps), (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open video writer for {p}")

        try:
            total = len(frames)
            for i, f in enumerate(frames):
                if cancel_token and cancel_token():
                    break
                img_rgb = frame_provider(f)
                img_u8 = MediaExporter._to_uint8(img_rgb)
                if img_u8.shape[0] != h or img_u8.shape[1] != w:
                    img_u8 = cv2.resize(img_u8, (w, h))

                img_bgr = cv2.cvtColor(img_u8, cv2.COLOR_RGB2BGR)
                writer.write(img_bgr)

                if progress_callback:
                    progress_callback(i + 1, total)
        finally:
            writer.release()

        return str(p)

    @staticmethod
    def export_video_ffmpeg(
        frame_provider: Callable[[int], np.ndarray],
        frames: List[int],
        output_path: str | Path,
        fps: float = 24.0,
        codec: str = "Apple ProRes 422 HQ",
        crf: int = 18,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> str:
        """
        Export frames to QuickTime (.mov) or MP4 (.mp4) using FFmpeg rawvideo pipe.
        Supports Apple ProRes (Proxy, 422, HQ, 4444) and H.264 / H.265.
        Falls back cleanly to OpenCV VideoWriter if FFmpeg is unavailable.
        """
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            return MediaExporter.export_video(frame_provider, frames, output_path, fps, progress_callback, cancel_token)

        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        if not frames:
            raise ValueError("No frames provided for video export.")

        first_frame = frame_provider(frames[0])
        h, w = first_frame.shape[:2]
        # Video codecs require even dimensions
        if w % 2 != 0:
            w -= 1
        if h % 2 != 0:
            h -= 1

        codec_str = str(codec).lower()
        if "prores" in codec_str:
            if "proxy" in codec_str:
                profile = "0"
            elif "4444" in codec_str:
                profile = "4"
            elif "hq" in codec_str:
                profile = "3"
            else:
                profile = "2"
            pix_fmt = "yuva444p10le" if profile == "4" else "yuv422p10le"
            codec_args = ["-c:v", "prores_ks", "-profile:v", profile, "-pix_fmt", pix_fmt]
        elif "265" in codec_str or "hevc" in codec_str:
            codec_args = ["-c:v", "libx265", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]
        else:  # H.264
            codec_args = ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]

        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-pix_fmt", "rgb24",
            "-r", f"{fps:.4f}",
            "-i", "-",
            *codec_args,
            str(p),
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            total = len(frames)
            for i, f in enumerate(frames):
                if cancel_token and cancel_token():
                    proc.kill()
                    return str(p)
                img = frame_provider(f)
                if img.shape[0] != h or img.shape[1] != w:
                    img = MediaExporter.resize_frame(img, w, h)
                img_u8 = MediaExporter._to_uint8(img)
                if not img_u8.flags["C_CONTIGUOUS"]:
                    img_u8 = np.ascontiguousarray(img_u8)
                proc.stdin.write(img_u8.tobytes())
                if progress_callback:
                    progress_callback(i + 1, total)

            proc.stdin.close()
            proc.wait()
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"FFmpeg export failed (code {proc.returncode}): {stderr}")
        except Exception as e:
            if proc.poll() is None:
                proc.kill()
            raise e

        return str(p)

    @staticmethod
    def export_sequence(
        frame_provider: Callable[[int], np.ndarray],
        frames: List[int],
        output_dir: str | Path,
        filename_prefix: str = "frame",
        file_ext: str = "png",
        pad: int = 4,
        compression: str = "zip",
        bit_depth: str = "16",
        quality: int = 95,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """
        Export list of frames as an image sequence.
        e.g. output_dir/frame.0101.exr
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        ext = file_ext.lstrip(".")
        saved_paths: List[str] = []
        total = len(frames)

        for i, f in enumerate(frames):
            if cancel_token and cancel_token():
                break
            frame_num_str = f"{f:0{pad}d}"
            filename = f"{filename_prefix}.{frame_num_str}.{ext}"
            file_path = out_dir / filename
            img = frame_provider(f)
            MediaExporter.save_image_file(
                img,
                file_path,
                compression=compression,
                bit_depth=bit_depth,
                quality=quality,
            )
            saved_paths.append(str(file_path))

            if progress_callback:
                progress_callback(i + 1, total)

        return saved_paths

    @staticmethod
    def render_strokes_on_image(base_img: np.ndarray, strokes: list) -> np.ndarray:
        """
        Renders vector markup strokes directly onto a base image at native image resolution,
        completely independent of screen display size, viewport pan, and zoom.
        """
        if base_img is None:
            return np.zeros((1080, 1920, 3), dtype=np.uint8)

        if base_img.dtype != np.uint8:
            rgb_u8 = np.clip(base_img[:, :, :3] * 255.0, 0, 255).astype(np.uint8)
        else:
            rgb_u8 = base_img[:, :, :3].copy()

        if not strokes:
            return rgb_u8

        h, w = rgb_u8.shape[:2]

        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QImage
        from PySide6.QtCore import Qt, QPointF, QRect, QRectF
        import math
        from openreview.models.annotations import ShapeType

        # Create QImage copy from contiguous buffer
        qimg = QImage(rgb_u8.data, w, h, rgb_u8.strides[0], QImage.Format.Format_RGB888).copy()

        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        scale = max(1.0, max(w, h) / 1920.0)

        for stroke in strokes:
            if not stroke.points:
                continue

            color = QColor(*stroke.color)
            scaled_width = max(1.0, stroke.width * scale)
            pen = QPen(color, scaled_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            # Map normalized [0.0, 1.0] coordinates to native image pixel coordinates
            pts = [QPointF(p[0] * w, p[1] * h) for p in stroke.points]

            if stroke.shape_type == ShapeType.PEN:
                if len(pts) == 1:
                    painter.drawPoint(pts[0])
                else:
                    from PySide6.QtGui import QPainterPath
                    path = QPainterPath()
                    path.moveTo(pts[0])
                    for pt in pts[1:]:
                        path.lineTo(pt)
                    painter.drawPath(path)

            elif stroke.shape_type == ShapeType.LINE and len(pts) >= 2:
                painter.drawLine(pts[0], pts[-1])

            elif stroke.shape_type == ShapeType.ARROW and len(pts) >= 2:
                p0 = pts[0]
                p1 = pts[-1]
                painter.drawLine(p0, p1)
                dx = p1.x() - p0.x()
                dy = p1.y() - p0.y()
                length = math.hypot(dx, dy)
                if length > 5:
                    ux = dx / length
                    uy = dy / length
                    arrow_sz = 14.0 * scale
                    left_x = p1.x() - arrow_sz * (ux + uy * 0.5)
                    left_y = p1.y() - arrow_sz * (uy - ux * 0.5)
                    right_x = p1.x() - arrow_sz * (ux - uy * 0.5)
                    right_y = p1.y() - arrow_sz * (uy + ux * 0.5)
                    painter.drawLine(p1, QPointF(left_x, left_y))
                    painter.drawLine(p1, QPointF(right_x, right_y))

            elif stroke.shape_type == ShapeType.RECTANGLE and len(pts) >= 2:
                p0 = pts[0]
                p1 = pts[-1]
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(min(p0.x(), p1.x()), min(p0.y(), p1.y()), abs(p1.x() - p0.x()), abs(p1.y() - p0.y())))

            elif stroke.shape_type == ShapeType.CIRCLE and len(pts) >= 2:
                p0 = pts[0]
                p1 = pts[-1]
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(min(p0.x(), p1.x()), min(p0.y(), p1.y()), abs(p1.x() - p0.x()), abs(p1.y() - p0.y())))

            elif stroke.shape_type == ShapeType.TEXT and pts:
                p0 = pts[0]
                txt = stroke.text or "Note"
                base_font_pt = max(10, int(stroke.width * 3.5)) if stroke.width > 1.0 else 12
                font_pt = max(8, int(base_font_pt * scale))
                font = QFont("Segoe UI", font_pt, QFont.Weight.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()

                lines = txt.split("\n")
                line_height = metrics.lineSpacing()
                max_line_w = max((metrics.horizontalAdvance(line) for line in lines), default=int(40 * scale))
                total_h = line_height * len(lines)

                pad_x = int(8 * scale)
                pad_y = int(6 * scale)
                box_w = max_line_w + pad_x * 2
                box_h = total_h + pad_y * 2

                box_x = int(p0.x())
                box_y = int(p0.y())
                text_rect = QRect(box_x, box_y, box_w, box_h)

                painter.setBrush(QColor(18, 18, 18, 220))
                painter.setPen(QPen(color, max(1.0, 1.5 * scale)))
                painter.drawRoundedRect(text_rect, 4.0 * scale, 4.0 * scale)

                painter.setPen(color)
                cur_y = box_y + pad_y + metrics.ascent()
                for line in lines:
                    painter.drawText(box_x + pad_x, cur_y, line)
                    cur_y += line_height

        painter.end()

        # Convert back to uint8 numpy array
        qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
        w, h = qimg.width(), qimg.height()
        ptr = qimg.constBits()
        return np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()

    @staticmethod
    def export_pdf_review_sheet(
        output_pdf_path: str | Path,
        entries: List[dict],
        title: str = "OpenReview - VFX Review Sheet",
        fps: float = 24.0,
    ) -> str:
        """
        Generate a structured, professional studio PDF review report using reportlab.
        Includes high-resolution frame thumbnails with burned-in annotations and review notes.
        """
        import tempfile
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        p = Path(output_pdf_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(p),
            pagesize=landscape(letter),
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#c28a10"),
            fontName="Helvetica-Bold",
        )
        sub_style = ParagraphStyle(
            "SubHeader",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#555555"),
            fontName="Helvetica",
        )
        item_title_style = ParagraphStyle(
            "ItemTitle",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1a1a1a"),
            fontName="Helvetica-Bold",
        )
        note_style = ParagraphStyle(
            "NoteStyle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2a2a2a"),
            fontName="Helvetica",
        )

        story = []

        import datetime
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"Generated on {date_str} | FPS: {fps:.2f} | Annotated Keyframes: {len(entries)}", sub_style))
        story.append(Spacer(1, 14))

        temp_files = []
        try:
            for item in entries:
                f_num = item.get("frame", 0)
                tc = item.get("timecode", "00:00:00:00")
                note_text = item.get("note", "").strip() or "No review notes."
                st_count = item.get("strokes_count", 0)
                img_data = item.get("image")

                tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tf_path = tf.name
                tf.close()
                temp_files.append(tf_path)

                if img_data is not None:
                    MediaExporter.save_image_file(img_data, tf_path)
                else:
                    blank = np.zeros((100, 100, 3), dtype=np.uint8)
                    MediaExporter.save_image_file(blank, tf_path)

                thumb = RLImage(tf_path, width=320, height=180)

                text_content = [
                    Paragraph(f"<b>Frame:</b> {f_num} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Timecode:</b> {tc}", item_title_style),
                    Paragraph(f"<b>Markup:</b> {st_count} vector stroke(s)", sub_style),
                    Spacer(1, 6),
                    Paragraph("<b>Review Notes:</b>", sub_style),
                    Paragraph(note_text.replace("\n", "<br/>"), note_style),
                ]

                row_table = Table([[thumb, text_content]], colWidths=[330, 380])
                row_table.setStyle(
                    TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dddddd")),
                        ("PADDING", (0, 0), (-1, -1), 8),
                    ])
                )

                story.append(row_table)
                story.append(Spacer(1, 12))

            doc.build(story)
        finally:
            for tf_path in temp_files:
                try:
                    os.remove(tf_path)
                except Exception:
                    pass

        return str(p)

    @staticmethod
    def _linearize_input(rgb: np.ndarray, input_space: int = 0) -> np.ndarray:
        """Convert float32 RGB to scene-linear based on input color space index."""
        if input_space == 0:  # sRGB
            higher = np.power(np.maximum((rgb + 0.055) / 1.055, 0.0), 2.4)
            lower = rgb / 12.92
            return np.where(rgb > 0.04045, higher, lower)
        elif input_space == 3:  # Cineon
            x = (rgb * 1023.0 - 685.0) / 300.0
            return np.maximum(0.0, (np.power(10.0, x) - 0.010798) / 0.989202)
        elif input_space == 4:  # ALEXA LogC
            cut, a, b, c, d, e, f = 0.1496582, 0.247190, 0.385537, 0.078277, 0.105910, 5.253018, 0.0400405
            lin = np.where(rgb > cut, (np.power(10.0, (rgb - b) / a) - d) / c, (rgb - f) / e)
            return np.maximum(lin, 0.0)
        elif input_space == 5:  # ALEXA LogC Film
            cut, a, b, c, d, e, f = 0.1496582, 0.247190, 0.385537, 0.078277, 0.105910, 5.253018, 0.0400405
            lin = np.where(rgb > cut, (np.power(10.0, (rgb - b) / a) - d) / c, (rgb - f) / e)
            return np.power(np.maximum(lin, 0.0), 1.15) * 1.1
        elif input_space == 6:  # Rec.709
            higher = np.power(np.maximum((rgb + 0.099) / 1.099, 0.0), 1.0 / 0.45)
            lower = rgb / 4.5
            return np.where(rgb > 0.081, higher, lower)
        elif input_space == 7:  # Gamma 2.2
            return np.power(np.maximum(rgb, 0.0), 2.2)
        else:  # ACEScg / Linear / Raw
            return rgb.copy()

    @staticmethod
    def _apply_color_grade(lin: np.ndarray, viewport) -> np.ndarray:
        """Apply exposure, gain, ASC CDL, grading edits, and 3D LUT to scene-linear float array."""
        if viewport is None:
            return lin

        # Scene-linear Exposure & Gain
        exposure_ev = float(getattr(viewport, "exposure_ev", 0.0))
        gain = float(getattr(viewport, "gain", 1.0))
        total_gain = gain * (2.0 ** exposure_ev)
        lin = lin * total_gain

        # Fast Saturation in Scene-Linear
        saturation = float(getattr(viewport, "saturation", 1.0))
        if abs(saturation - 1.0) > 0.0001:
            luma = lin[:, :, 0:1] * 0.2126 + lin[:, :, 1:2] * 0.7152 + lin[:, :, 2:3] * 0.0722
            lin = luma * (1.0 - saturation) + lin * saturation

        # ASC CDL Evaluation
        cg = getattr(viewport, "color_grading", None)
        if cg and getattr(cg, "cdl_enabled", False) and getattr(cg, "active_cdl", None):
            cdl = cg.active_cdl
            slope = np.array(cdl.slope, dtype=np.float32)
            offset = np.array(cdl.offset, dtype=np.float32)
            power = np.array(cdl.power, dtype=np.float32)
            sat = float(cdl.saturation)
            sop = np.power(np.maximum(lin * slope + offset, 0.0), np.maximum(power, 0.0001))
            luma = sop[:, :, 0:1] * 0.2126 + sop[:, :, 1:2] * 0.7152 + sop[:, :, 2:3] * 0.0722
            lin = np.maximum(0.0, luma * (1.0 - sat) + sop * sat)

        # Interactive Color Grading Edits
        if cg:
            g_gain = np.array(cg.gain, dtype=np.float32)
            g_offset = np.array(cg.offset, dtype=np.float32)
            lin = lin * g_gain + g_offset

            if cg.gamma > 0.001 and abs(cg.gamma - 1.0) > 0.001:
                lin = np.power(np.maximum(lin, 0.0), 1.0 / cg.gamma)
            if abs(cg.contrast - 1.0) > 0.001:
                lin = np.maximum(0.0, (lin - 0.18) * cg.contrast + 0.18)
            if abs(cg.saturation - 1.0) > 0.001:
                luma = lin[:, :, 0:1] * 0.2126 + lin[:, :, 1:2] * 0.7152 + lin[:, :, 2:3] * 0.0722
                lin = np.maximum(0.0, luma * (1.0 - cg.saturation) + lin * cg.saturation)
            if abs(cg.hue) > 0.01:
                angle = np.radians(cg.hue)
                cos_a, sin_a = np.cos(angle), np.sin(angle)
                mat = np.array([
                    [0.213 + cos_a * 0.787 - sin_a * 0.213, 0.715 - cos_a * 0.715 - sin_a * 0.715, 0.072 - cos_a * 0.072 + sin_a * 0.928],
                    [0.213 - cos_a * 0.213 + sin_a * 0.143, 0.715 + cos_a * 0.285 + sin_a * 0.140, 0.072 - cos_a * 0.072 - sin_a * 0.283],
                    [0.213 - cos_a * 0.213 - sin_a * 0.787, 0.715 - cos_a * 0.715 + sin_a * 0.715, 0.072 + cos_a * 0.928 + sin_a * 0.072],
                ], dtype=np.float32)
                lin = np.dot(lin, mat.T)

            # 3D LUT Evaluation
            if getattr(cg, "lut_enabled", False) and getattr(cg, "active_lut", None):
                lut = cg.active_lut
                if lut.data_3d is not None and lut.size_3d > 0:
                    sz = lut.size_3d
                    coords = np.clip(lin * (sz - 1), 0, sz - 1)
                    i0 = np.floor(coords).astype(np.int32)
                    i1 = np.minimum(i0 + 1, sz - 1)
                    f = coords - i0
                    lut_arr = lut.data_3d
                    c000 = lut_arr[i0[..., 2], i0[..., 1], i0[..., 0]]
                    c100 = lut_arr[i0[..., 2], i0[..., 1], i1[..., 0]]
                    c010 = lut_arr[i0[..., 2], i1[..., 1], i0[..., 0]]
                    c110 = lut_arr[i0[..., 2], i1[..., 1], i1[..., 0]]
                    c001 = lut_arr[i1[..., 2], i0[..., 1], i0[..., 0]]
                    c101 = lut_arr[i1[..., 2], i0[..., 1], i1[..., 0]]
                    c011 = lut_arr[i1[..., 2], i1[..., 1], i0[..., 0]]
                    c111 = lut_arr[i1[..., 2], i1[..., 1], i1[..., 0]]
                    fx, fy, fz = f[..., 0:1], f[..., 1:2], f[..., 2:3]
                    c00 = c000 * (1 - fx) + c100 * fx
                    c01 = c001 * (1 - fx) + c101 * fx
                    c10 = c010 * (1 - fx) + c110 * fx
                    c11 = c011 * (1 - fx) + c111 * fx
                    c0 = c00 * (1 - fy) + c10 * fy
                    c1 = c01 * (1 - fy) + c11 * fy
                    lin = c0 * (1 - fz) + c1 * fz

        return lin

    @staticmethod
    def _apply_display_transform(lin: np.ndarray, viewport) -> np.ndarray:
        """Apply display view transform and monitor gamma/brightness trim."""
        if viewport is None:
            return lin

        view_transform = int(getattr(viewport, "view_transform", 0))
        if view_transform == 0:  # sRGB Display
            higher = 1.055 * np.power(np.maximum(lin, 0.0), 1.0 / 2.4) - 0.055
            lower = 12.92 * lin
            disp = np.where(lin > 0.0031308, higher, lower)
        elif view_transform == 1:  # ACES Filmic Tone Mapping
            a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
            x = np.maximum(lin, 0.0)
            filmic = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0)
            higher = 1.055 * np.power(filmic, 1.0 / 2.4) - 0.055
            lower = 12.92 * filmic
            disp = np.where(filmic > 0.0031308, higher, lower)
        elif view_transform == 2:  # Raw / Pass-through
            disp = lin
        elif view_transform == 3:  # Rec.709
            higher = 1.099 * np.power(np.maximum(lin, 0.0), 0.45) - 0.099
            lower = 4.5 * lin
            disp = np.where(lin > 0.018, higher, lower)
        elif view_transform == 4:  # Gamma 2.2
            disp = np.power(np.maximum(lin, 0.0), 1.0 / 2.2)
        else:
            disp = lin

        # Display Gamma & Brightness Trim
        gamma = float(getattr(viewport, "gamma", 1.0))
        if abs(gamma - 1.0) > 0.0001:
            gamma_pow = 1.0 / max(0.0001, abs(gamma))
            disp = np.power(np.maximum(disp, 0.0), gamma_pow)
            if gamma < 0:
                disp = 1.0 - disp

        cg = getattr(viewport, "color_grading", None)
        if cg and abs(cg.brightness) > 0.001:
            disp = disp * (2.0 ** cg.brightness)

        if cg and getattr(cg, "invert_colors", False):
            disp = 1.0 - disp

        return disp

    @staticmethod
    def apply_screenspace_color_transforms(raw_img: np.ndarray, viewport) -> np.ndarray:
        """
        Apply complete source input colorspace linearization, scene-linear exposure & gain,
        ASC CDL, interactive color grading edits, 3D LUT, display view transform, and gamma,
        producing a color-managed uint8 RGB image matching viewport screen rendering exactly.
        """
        if raw_img is None:
            return np.zeros((1080, 1920, 3), dtype=np.uint8)

        if raw_img.dtype in (np.float32, np.float64, np.float16):
            rgb = raw_img[:, :, :3].astype(np.float32)
        else:
            rgb = raw_img[:, :, :3].astype(np.float32) / 255.0

        if viewport is None:
            return np.clip(rgb * 255.0, 0, 255).astype(np.uint8)

        input_space = int(getattr(viewport, "input_space", 0))
        lin = MediaExporter._linearize_input(rgb, input_space)
        lin = MediaExporter._apply_color_grade(lin, viewport)
        disp = MediaExporter._apply_display_transform(lin, viewport)
        return np.clip(disp * 255.0, 0, 255).astype(np.uint8)

    @staticmethod
    def convert_colorspace(
        raw_img: np.ndarray,
        target_space: str,
        viewport=None,
        burn_in_grade: bool = True,
    ) -> np.ndarray:
        """
        Convert raw frame image to specified target color space.
        Supported target_space options:
          - 'Current View (WYSIWYG)': full screen-space color management (uint8)
          - 'Scene-Linear (ACEScg)': scene-linear float32, optional grade burn-in
          - 'sRGB (Display)': sRGB transfer curve float32/uint8, optional grade burn-in
          - 'Rec.709 (Display)': Rec.709 transfer curve float32/uint8, optional grade burn-in
          - 'Cineon Log': Cineon log printing density curve float32, optional grade burn-in
          - 'Raw / Pass-Through': untouched raw frame data
        """
        if raw_img is None:
            return np.zeros((1080, 1920, 3), dtype=np.uint8)

        space_str = str(target_space).strip().lower()
        if "wysiwyg" in space_str or "current" in space_str:
            return MediaExporter.apply_screenspace_color_transforms(raw_img, viewport)

        if "raw" in space_str or "pass-through" in space_str:
            return raw_img

        if raw_img.dtype in (np.float32, np.float64, np.float16):
            rgb = raw_img[:, :, :3].astype(np.float32)
        else:
            rgb = raw_img[:, :, :3].astype(np.float32) / 255.0

        input_space = int(getattr(viewport, "input_space", 0)) if viewport else (0 if raw_img.dtype == np.uint8 else 1)
        lin = MediaExporter._linearize_input(rgb, input_space)

        if burn_in_grade and viewport:
            lin = MediaExporter._apply_color_grade(lin, viewport)

        if "linear" in space_str or "acescg" in space_str:
            return lin.astype(np.float32)

        if "709" in space_str:
            higher = 1.099 * np.power(np.maximum(lin, 0.0), 0.45) - 0.099
            lower = 4.5 * lin
            disp = np.where(lin > 0.018, higher, lower)
            return np.clip(disp, 0.0, 1.0).astype(np.float32)

        if "cineon" in space_str:
            x = np.maximum(lin * 0.989202 + 0.010798, 1e-6)
            cineon = np.clip((685.0 + 300.0 * np.log10(x)) / 1023.0, 0.0, 1.0)
            return cineon.astype(np.float32)

        # Default sRGB
        higher = 1.055 * np.power(np.maximum(lin, 0.0), 1.0 / 2.4) - 0.055
        lower = 12.92 * lin
        disp = np.where(lin > 0.0031308, higher, lower)
        return np.clip(disp, 0.0, 1.0).astype(np.float32)

