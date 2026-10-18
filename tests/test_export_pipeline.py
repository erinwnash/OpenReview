"""
Comprehensive automated tests for OpenReview Studio Export Media Pipeline.
Tests OpenEXR, DPX, TIFF, PNG, JPEG, Targa, FFmpeg ProRes/H264 export,
downrezzing resampler, colorspace conversions, and ExportWorker.
"""
import os
import shutil
import tempfile
import pytest
import numpy as np

from openreview.core.exporter import MediaExporter
from openreview.ui.export_dialog import ExportWorker


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="openreview_export_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_save_exr_half_and_float(temp_dir):
    """Verify OpenEXR export in 16-bit half and 32-bit float across compressions."""
    rgb = np.random.rand(64, 64, 3).astype(np.float32)
    rgba = np.random.rand(64, 64, 4).astype(np.float32)

    # 16-bit half ZIP
    p1 = os.path.join(temp_dir, "test_half_zip.exr")
    MediaExporter.save_exr(p1, rgb, compression="zip", bit_depth="16")
    assert os.path.exists(p1) and os.path.getsize(p1) > 0

    # 32-bit float PIZ
    p2 = os.path.join(temp_dir, "test_float_piz.exr")
    MediaExporter.save_exr(p2, rgb, compression="piz", bit_depth="32")
    assert os.path.exists(p2) and os.path.getsize(p2) > 0

    # 16-bit DWAA RGBA
    p3 = os.path.join(temp_dir, "test_rgba_dwaa.exr")
    MediaExporter.save_exr(p3, rgba, compression="dwaa", bit_depth="16")
    assert os.path.exists(p3) and os.path.getsize(p3) > 0


def test_save_dpx_10_and_16(temp_dir):
    """Verify DPX export in 10-bit and 16-bit SMPTE 268M format."""
    rgb = np.random.rand(48, 48, 3).astype(np.float32)

    # 10-bit
    p10 = os.path.join(temp_dir, "test_10bit.dpx")
    MediaExporter.save_dpx(p10, rgb, bit_depth=10)
    assert os.path.exists(p10) and os.path.getsize(p10) > 0

    # 16-bit
    p16 = os.path.join(temp_dir, "test_16bit.dpx")
    MediaExporter.save_dpx(p16, rgb, bit_depth=16)
    assert os.path.exists(p16) and os.path.getsize(p16) > 0


def test_save_image_file_all_formats(temp_dir):
    """Verify generic dispatcher handles EXR, DPX, TIFF, PNG, JPEG, TGA."""
    rgb = np.random.rand(32, 32, 3).astype(np.float32)

    formats = [
        ("frame.exr", {"compression": "zip", "bit_depth": "16"}),
        ("frame.dpx", {"bit_depth": "10"}),
        ("frame.tif", {"bit_depth": "16"}),
        ("frame.png", {"bit_depth": "8"}),
        ("frame.jpg", {"quality": 90}),
        ("frame.tga", {}),
    ]

    for filename, kwargs in formats:
        p = os.path.join(temp_dir, filename)
        MediaExporter.save_image_file(rgb, p, **kwargs)
        assert os.path.exists(p) and os.path.getsize(p) > 0


def test_downrez_resizing():
    """Verify Area downscaling and Lanczos upscaling preserves aspect and dims."""
    orig = np.full((1080, 1920, 3), 128, dtype=np.uint8)

    # Downrez 50%
    down = MediaExporter.resize_frame(orig, 960, 540)
    assert down.shape == (540, 960, 3)

    # Downrez 25%
    down25 = MediaExporter.resize_frame(orig, 480, 270)
    assert down25.shape == (270, 480, 3)

    # Upscale
    up = MediaExporter.resize_frame(down25, 1920, 1080)
    assert up.shape == (1080, 1920, 3)


def test_colorspace_conversions():
    """Verify colorspace transforms: Linear, sRGB, Rec709, Cineon, Raw."""
    raw = np.full((64, 64, 3), 0.5, dtype=np.float32)

    # Raw / pass-through
    res_raw = MediaExporter.convert_colorspace(raw, "Raw / Pass-Through")
    assert np.allclose(res_raw, raw)

    # Scene linear
    res_lin = MediaExporter.convert_colorspace(raw, "Scene-Linear (ACEScg)")
    assert res_lin.dtype == np.float32
    assert res_lin.shape == (64, 64, 3)

    # sRGB
    res_srgb = MediaExporter.convert_colorspace(raw, "sRGB (Display)")
    assert res_srgb.dtype == np.float32
    assert np.all(res_srgb >= 0.0) and np.all(res_srgb <= 1.0)

    # Rec.709
    res_709 = MediaExporter.convert_colorspace(raw, "Rec.709 (Display)")
    assert res_709.dtype == np.float32

    # Cineon
    res_cineon = MediaExporter.convert_colorspace(raw, "Cineon Log")
    assert res_cineon.dtype == np.float32


def test_export_video_ffmpeg_prores_and_x264(temp_dir):
    """Verify FFmpeg pipe generates valid ProRes and H.264 files."""
    frames = [101, 102, 103]
    def frame_provider(f):
        return np.full((180, 320, 3), (f % 256), dtype=np.uint8)

    # ProRes 422 HQ
    prores_path = os.path.join(temp_dir, "test_prores.mov")
    out = MediaExporter.export_video_ffmpeg(
        frame_provider,
        frames,
        prores_path,
        fps=24.0,
        codec="Apple ProRes 422 HQ",
    )
    assert os.path.exists(out) and os.path.getsize(out) > 0

    # H.264 MP4
    mp4_path = os.path.join(temp_dir, "test_x264.mp4")
    out_mp4 = MediaExporter.export_video_ffmpeg(
        frame_provider,
        frames,
        mp4_path,
        fps=24.0,
        codec="H.264",
        crf=20,
    )
    assert os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 0


def test_export_sequence_exr(temp_dir):
    """Verify sequence export generates correct numbered files with padding."""
    frames = [1, 2, 3]
    def frame_provider(f):
        return np.random.rand(64, 64, 3).astype(np.float32)

    seq_dir = os.path.join(temp_dir, "exr_seq")
    saved = MediaExporter.export_sequence(
        frame_provider,
        frames,
        output_dir=seq_dir,
        filename_prefix="shot_v01",
        file_ext="exr",
        pad=4,
        compression="zip",
        bit_depth="16",
    )
    assert len(saved) == 3
    for p in saved:
        assert os.path.exists(p) and os.path.getsize(p) > 0
    assert os.path.basename(saved[0]) == "shot_v01.0001.exr"
    assert os.path.basename(saved[2]) == "shot_v01.0003.exr"


def test_export_worker_async(qapp, temp_dir):
    """Verify ExportWorker runs non-blocking in background and signals completion."""
    frames = [1, 2]
    dest = os.path.join(temp_dir, "worker_test.mov")

    config = {
        "destination": dest,
        "frames": frames,
        "export_type": "video",
        "codec": "Apple ProRes 422 HQ",
        "fps": 24.0,
        "colorspace": "sRGB (Display)",
        "burn_annotations": False,
        "burn_grade": False,
        "target_width": 320,
        "target_height": 180,
    }

    def raw_reader(f):
        return np.full((180, 320, 3), 100, dtype=np.uint8)

    worker = ExportWorker(config, raw_frame_reader=raw_reader)
    completed = []
    worker.finished.connect(lambda path: completed.append(path))

    worker.start()
    worker.wait(5000)
    qapp.processEvents()

    assert len(completed) == 1
    assert os.path.exists(dest) and os.path.getsize(dest) > 0
