import os
import pytest
import numpy as np

from openreview.core.image_io import read_image_file, read_exr, read_dpx, write_exr, write_dpx
from openreview.core.reader import DiskMediaReader
from openreview.core.sequence_parser import SequenceInfo, DiskSequenceReader, detect_image_sequence


def test_exr_write_and_read(tmp_path):
    exr_path = str(tmp_path / "shot_1001.exr")
    # Gradient test image with values > 1.0 (HDR)
    src_data = np.zeros((64, 64, 4), dtype=np.float32)
    src_data[:, :, 0] = np.linspace(0.0, 2.5, 64)  # HDR Red ramp
    src_data[:, :, 1] = 0.5
    src_data[:, :, 2] = 0.8
    src_data[:, :, 3] = 1.0

    success = write_exr(exr_path, src_data)
    assert success is True
    assert os.path.exists(exr_path)

    # Read back via unified reader
    decoded = read_image_file(exr_path)
    assert decoded is not None
    assert decoded.shape == (64, 64, 4)
    assert decoded.dtype == np.float32
    # Ensure not black canvas (pixels > 0)
    assert np.max(decoded[:, :, 0]) > 2.0
    assert np.allclose(decoded[0, 0, 1], 0.5, atol=1e-2)
    assert np.allclose(decoded[0, 0, 2], 0.8, atol=1e-2)


def test_dpx_10bit_write_and_read(tmp_path):
    dpx_path = str(tmp_path / "comp_0042.dpx")
    src_data = np.zeros((48, 48, 4), dtype=np.float32)
    src_data[:, :, 0] = 0.75
    src_data[:, :, 1] = 0.25
    src_data[:, :, 2] = 0.50
    src_data[:, :, 3] = 1.0

    success = write_dpx(dpx_path, src_data, bit_depth=10)
    assert success is True
    assert os.path.exists(dpx_path)

    decoded = read_image_file(dpx_path)
    assert decoded is not None
    assert decoded.shape == (48, 48, 4)
    assert decoded.dtype == np.float32
    # 10-bit precision quantization check
    assert np.isclose(decoded[0, 0, 0], 0.75, atol=1e-2)
    assert np.isclose(decoded[0, 0, 1], 0.25, atol=1e-2)
    assert np.isclose(decoded[0, 0, 2], 0.50, atol=1e-2)
    assert decoded[0, 0, 3] == 1.0


def test_dpx_16bit_write_and_read(tmp_path):
    dpx_path = str(tmp_path / "plate_0100.dpx")
    src_data = np.zeros((32, 32, 4), dtype=np.float32)
    src_data[:, :, 0] = 0.9
    src_data[:, :, 1] = 0.1
    src_data[:, :, 2] = 0.4
    src_data[:, :, 3] = 1.0

    success = write_dpx(dpx_path, src_data, bit_depth=16)
    assert success is True

    decoded = read_dpx(dpx_path)
    assert decoded is not None
    assert decoded.shape == (32, 32, 4)
    assert np.isclose(decoded[0, 0, 0], 0.9, atol=1e-3)
    assert np.isclose(decoded[0, 0, 1], 0.1, atol=1e-3)


def test_disk_media_reader_with_exr_and_dpx(tmp_path):
    exr_file = str(tmp_path / "single_frame.exr")
    dpx_file = str(tmp_path / "single_frame.dpx")

    img_data = np.full((32, 32, 4), 0.6, dtype=np.float32)
    img_data[:, :, 3] = 1.0
    write_exr(exr_file, img_data)
    write_dpx(dpx_file, img_data, bit_depth=10)

    # Test DiskMediaReader
    reader_exr = DiskMediaReader(exr_file)
    frame_exr = reader_exr.read_frame(1)
    assert frame_exr is not None
    assert not np.all(frame_exr[:, :, :3] == 0)  # Not black canvas

    reader_dpx = DiskMediaReader(dpx_file)
    frame_dpx = reader_dpx.read_frame(1)
    assert frame_dpx is not None
    assert not np.all(frame_dpx[:, :, :3] == 0)  # Not black canvas


def test_sequence_media_reader_with_exr_sequence(tmp_path):
    # Generate 3 EXR frames
    for f in range(1001, 1004):
        f_path = str(tmp_path / f"shot_sq01.{f:04d}.exr")
        data = np.full((32, 32, 4), float(f - 1000) * 0.3, dtype=np.float32)
        data[:, :, 3] = 1.0
        write_exr(f_path, data)

    seq_info = SequenceInfo(
        directory=str(tmp_path),
        prefix="shot_sq01",
        separator=".",
        padding=4,
        extension=".exr",
        start_frame=1001,
        end_frame=1003,
        available_frames={1001, 1002, 1003},
        missing_frames=set(),
    )
    seq_reader = DiskSequenceReader(seq_info)

    f1001 = seq_reader.read_frame(1001)
    assert f1001 is not None
    assert not np.all(f1001[:, :, :3] == 0)
    assert np.isclose(f1001[0, 0, 0], 0.3, atol=1e-2)

    f1002 = seq_reader.read_frame(1002)
    assert f1002 is not None
    assert np.isclose(f1002[0, 0, 0], 0.6, atol=1e-2)


def test_main_window_loads_exr_and_dpx(qtbot, tmp_path):
    from openreview.ui.main_window import MainWindow

    exr_file = str(tmp_path / "vfx_plate.1001.exr")
    dpx_file = str(tmp_path / "vfx_plate.1001.dpx")

    img_data = np.full((64, 64, 4), 0.75, dtype=np.float32)
    img_data[:, :, 3] = 1.0
    write_exr(exr_file, img_data)
    write_dpx(dpx_file, img_data, bit_depth=10)

    window = MainWindow()
    qtbot.addWidget(window)

    # 1. Load EXR
    window._load_path(exr_file)
    qtbot.wait(100)
    assert window.viewport._image_a is not None
    assert not np.all(window.viewport._image_a[:, :, :3] == 0)
    assert np.isclose(window.viewport._image_a[0, 0, 0], 0.75, atol=1e-2)

    # 2. Load DPX
    window._load_path(dpx_file)
    qtbot.wait(100)
    assert window.viewport._image_a is not None
    assert not np.all(window.viewport._image_a[:, :, :3] == 0)
    assert np.isclose(window.viewport._image_a[0, 0, 0], 0.75, atol=1e-2)


def test_playcheck_real_dpx_files():
    """Verify reading actual industry SMPTE 268M DPX files if present in playcheck/."""
    playcheck_dir = os.path.abspath("playcheck")
    if not os.path.isdir(playcheck_dir):
        pytest.skip("playcheck folder not found")

    dpx_files = sorted([os.path.join(playcheck_dir, f) for f in os.listdir(playcheck_dir) if f.endswith(".dpx")])
    if not dpx_files:
        pytest.skip("No DPX files in playcheck")

    # Read first file
    first_file = dpx_files[0]
    frame = read_image_file(first_file)
    assert frame is not None
    assert frame.shape == (2160, 3840, 4)
    assert frame.dtype == np.float32
    assert frame.max() > 0.1
    assert not np.all(frame[:, :, :3] == 0)

    # Verify sequence detection
    seq = detect_image_sequence(first_file)
    assert seq is not None
    assert seq.start_frame == 1001
    assert seq.end_frame == 1010
    seq_reader = DiskSequenceReader(seq)
    f1001 = seq_reader.read_frame(1001)
    assert f1001 is not None
    assert f1001.shape == (2160, 3840, 4)


def test_xnview_image_formats_and_specialized_decoders(tmp_path):
    """Verify XnView image extensions registry and specialized Cineon, PFM, RGBE, SGI, Alias PIX, and SVG decoders."""
    import struct
    from openreview.core.image_io import IMAGE_EXTENSIONS, is_image_file

    # 1. Verify >= 700 XnView extensions are registered
    assert len(IMAGE_EXTENSIONS) >= 700
    for ext in [
        ".exr", ".dpx", ".cin", ".tif", ".tiff", ".psd", ".psb", ".avif", ".heic", ".heif",
        ".jxl", ".jxr", ".jp2", ".j2k", ".fits", ".dds", ".sgi", ".rgb", ".rgba", ".bw",
        ".pic", ".pct", ".pix", ".als", ".alias", ".rla", ".rpf", ".iff", ".ilbm", ".pcx",
        ".pbm", ".pgm", ".ppm", ".pnm", ".pam", ".pfm", ".ras", ".sun", ".ico", ".cur",
        ".icns", ".svg", ".svgz", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
        ".dcm", ".djvu", ".ecw", ".hdr", ".hdri", ".xbm", ".xpm", ".xwd", ".wbmp", ".xcf",
    ]:
        assert ext in IMAGE_EXTENSIONS
        assert is_image_file(f"sample{ext}")

    # 2. Test Portable FloatMap (.pfm) 32-bit float HDR decoder
    pfm_path = str(tmp_path / "test.pfm")
    w, h = 8, 6
    pfm_pixels = np.full((h, w, 3), 0.42, dtype="<f4")
    with open(pfm_path, "wb") as f:
        f.write(f"PF\n{w} {h}\n-1.0\n".encode("ascii"))
        f.write(pfm_pixels.tobytes())
    pfm_img = read_image_file(pfm_path)
    assert pfm_img is not None
    assert pfm_img.shape == (h, w, 4)
    assert np.isclose(pfm_img[0, 0, 0], 0.42, atol=1e-3)

    # 3. Test Kodak Cineon (.cin) 10-bit log decoder
    cin_path = str(tmp_path / "test.cin")
    header = bytearray(1024)
    struct.pack_into(">I", header, 0, 0x802A5FD7)  # magic
    struct.pack_into(">I", header, 4, 1024)        # offset
    header[193] = 3                                # 3 channels
    header[198] = 10                               # 10-bit
    struct.pack_into(">I", header, 200, w)
    struct.pack_into(">I", header, 204, h)
    val10 = 512
    word = (val10 << 22) | (val10 << 12) | (val10 << 2)
    words = np.full((w * h,), word, dtype=">u4")
    with open(cin_path, "wb") as f:
        f.write(header)
        f.write(words.tobytes())
    cin_img = read_image_file(cin_path)
    assert cin_img is not None
    assert cin_img.shape == (h, w, 4)
    assert np.isclose(cin_img[0, 0, 0], 512.0 / 1023.0, atol=1e-2)

    # 4. Test Alias/Wavefront PIX (.pix) 24-bit RLE decoder
    pix_path = str(tmp_path / "test.pix")
    pix_hdr = struct.pack(">HHHHH", w, h, 0, 0, 24)
    # Single RLE packet per row of length w with B=50, G=100, R=200
    packets = b"".join([struct.pack("BBBB", w, 50, 100, 200) for _ in range(h)])
    with open(pix_path, "wb") as f:
        f.write(pix_hdr + packets)
    pix_img = read_image_file(pix_path)
    assert pix_img is not None
    assert pix_img.shape == (h, w, 4)
    assert np.isclose(pix_img[0, 0, 0], 200.0 / 255.0, atol=1e-2)

    # 5. Test SGI IRIS (.sgi) uncompressed decoder
    sgi_path = str(tmp_path / "test.sgi")
    sgi_hdr = bytearray(512)
    struct.pack_into(">HBBHHHH", sgi_hdr, 0, 474, 0, 1, 3, w, h, 3)
    sgi_planes = np.full((3, h, w), 128, dtype=np.uint8)
    with open(sgi_path, "wb") as f:
        f.write(sgi_hdr + sgi_planes.tobytes())
    sgi_img = read_image_file(sgi_path)
    assert sgi_img is not None
    assert sgi_img.shape == (h, w, 4)
    assert np.isclose(sgi_img[0, 0, 0], 128.0 / 255.0, atol=1e-2)

    # 6. Test SVG (.svg) vector image decoder
    svg_path = str(tmp_path / "test.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="24"><rect width="32" height="24" fill="#ff0000"/></svg>')
    svg_img = read_image_file(svg_path)
    assert svg_img is not None
    assert svg_img.shape == (24, 32, 4)



