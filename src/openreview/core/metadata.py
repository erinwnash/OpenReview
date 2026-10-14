"""
Comprehensive VFX and Media Metadata Extraction Engine.
Extracts container, codec, color, stream, and file system metadata
using ffprobe, OpenCV, and Pillow with robust cross-platform fallbacks.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any, Dict, Optional
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def find_ffprobe_executable() -> Optional[str]:
    """Locate ffprobe in PATH or common standard install locations."""
    # 1. System PATH
    p = shutil.which("ffprobe")
    if p:
        return p

    # 2. Local AppData / common Windows paths
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffprobe.exe"),
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def extract_media_metadata(file_path: Optional[str]) -> Dict[str, Any]:
    """
    Extract comprehensive metadata dictionary for given media file or container.
    Returns normalized dictionary with metadata fields.
    """
    if not file_path or not os.path.exists(file_path):
        return {
            "file_path": file_path or "No Media Loaded",
            "file_name": os.path.basename(file_path) if file_path else "Synthetic Stream",
            "file_dir": os.path.dirname(file_path) if file_path else "Memory",
            "status": "No file on disk",
        }

    meta: Dict[str, Any] = {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "file_dir": os.path.dirname(file_path),
        "extension": os.path.splitext(file_path)[1].lower(),
    }

    # 1. File System Attributes
    try:
        st = os.stat(file_path)
        meta["file_size_bytes"] = st.st_size
        meta["file_size_mb"] = st.st_size / (1024.0 * 1024.0)
        if meta["file_size_mb"] >= 1024.0:
            meta["file_size_str"] = f"{meta['file_size_mb'] / 1024.0:.2f} GB ({st.st_size:,} bytes)"
        else:
            meta["file_size_str"] = f"{meta['file_size_mb']:.2f} MB ({st.st_size:,} bytes)"
        meta["modified_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        meta["created_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_ctime))
    except Exception as e:
        meta["file_stat_error"] = str(e)

    # 2. ffprobe Detailed Container & Stream Analysis
    ffprobe_bin = find_ffprobe_executable()
    ffprobe_success = False

    if ffprobe_bin:
        try:
            cmd = [
                ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path,
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2.5,
            )
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                fmt = data.get("format", {})
                meta["format_name"] = fmt.get("format_long_name", fmt.get("format_name", ""))
                overall_br = int(fmt.get("bit_rate", 0))
                meta["overall_bitrate"] = overall_br
                if overall_br > 0:
                    meta["overall_bitrate_str"] = f"{overall_br / 1_000_000.0:.2f} Mbps ({overall_br // 1000:,} kbps)"
                meta["duration_sec"] = float(fmt.get("duration", 0.0))
                meta["format_tags"] = fmt.get("tags", {})

                for stream in data.get("streams", []):
                    stype = stream.get("codec_type")
                    if stype == "video" and "video_codec" not in meta:
                        meta["video_codec"] = stream.get("codec_long_name", stream.get("codec_name", ""))
                        meta["video_codec_short"] = stream.get("codec_name", "")
                        meta["video_codec_tag"] = stream.get("codec_tag_string", "")
                        meta["video_profile"] = stream.get("profile", "")
                        meta["video_level"] = str(stream.get("level", ""))
                        meta["pixel_format"] = stream.get("pix_fmt", "")
                        meta["color_space"] = stream.get("color_space", "")
                        meta["color_primaries"] = stream.get("color_primaries", "")
                        meta["color_transfer"] = stream.get("color_transfer", "")
                        meta["color_range"] = "TV (Limited 16-235)" if stream.get("color_range") == "tv" else ("PC (Full 0-255)" if stream.get("color_range") == "pc" else stream.get("color_range", ""))
                        v_br = int(stream.get("bit_rate", 0))
                        meta["video_bitrate"] = v_br
                        if v_br > 0:
                            meta["video_bitrate_str"] = f"{v_br / 1_000_000.0:.2f} Mbps ({v_br // 1000:,} kbps)"
                        meta["width"] = int(stream.get("width", 0))
                        meta["height"] = int(stream.get("height", 0))
                        meta["bits_per_sample"] = stream.get("bits_per_raw_sample", "")
                        meta["nb_frames"] = int(stream.get("nb_frames", 0))
                        meta["fps_str"] = stream.get("avg_frame_rate", "")
                        meta["stream_tags"] = stream.get("tags", {})
                        meta["field_order"] = stream.get("field_order", "progressive")
                        ffprobe_success = True

                    elif stype == "audio" and "audio_codec" not in meta:
                        meta["audio_codec"] = stream.get("codec_long_name", stream.get("codec_name", ""))
                        meta["audio_sample_rate"] = stream.get("sample_rate", "")
                        meta["audio_channels"] = stream.get("channels", 0)
                        meta["audio_channel_layout"] = stream.get("channel_layout", "")
                        a_br = int(stream.get("bit_rate", 0))
                        meta["audio_bitrate"] = a_br
                        if a_br > 0:
                            meta["audio_bitrate_str"] = f"{a_br // 1000} kbps"
        except Exception as e:
            meta["ffprobe_error"] = str(e)

    # 3. OpenCV Fallback for Video Files if ffprobe unavailable or partial
    from openreview.core.video_reader import is_video_file, get_video_codec_info
    from openreview.core.image_io import is_image_file

    if not ffprobe_success and HAS_CV2 and is_video_file(file_path):
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                if "width" not in meta or not meta["width"]:
                    meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                if "height" not in meta or not meta["height"]:
                    meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if "nb_frames" not in meta or not meta["nb_frames"]:
                    meta["nb_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if "fps" not in meta:
                    meta["fps"] = float(cap.get(cv2.CAP_PROP_FPS))
                fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
                if fourcc_int > 0 and "video_codec" not in meta:
                    fourcc_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip("\x00")
                    dec_name, family_desc = get_video_codec_info(fourcc_str)
                    meta["video_codec"] = f"{family_desc} ({fourcc_str})"
                    meta["video_codec_short"] = dec_name
                    meta["video_codec_tag"] = fourcc_str
                br_kbps = cap.get(cv2.CAP_PROP_BITRATE)
                if br_kbps > 0 and "overall_bitrate_str" not in meta:
                    meta["overall_bitrate_str"] = f"{br_kbps:.0f} kbps"
            cap.release()
        except Exception:
            pass

    # 4. Pillow Metadata for Still Images and Image Sequences
    if HAS_PIL and is_image_file(file_path):
        try:
            with Image.open(file_path) as img:
                meta["image_format"] = img.format or meta["extension"][1:].upper()
                meta["image_mode"] = img.mode
                if "width" not in meta or not meta["width"]:
                    meta["width"], meta["height"] = img.size
                if hasattr(img, "info") and img.info:
                    meta["image_info_tags"] = {
                        str(k): str(v) for k, v in img.info.items() if len(str(v)) < 120
                    }
        except Exception:
            pass

    return meta
