import os
import pytest
import numpy as np
from PIL import Image

from openreview.core.image_io import (
    read_image_file,
    read_exr,
    read_dpx,
    read_tiff,
    read_tga,
    get_exr_channels,
    write_exr,
    write_dpx,
)
from openreview.core.stereo import detect_stereo_counterpart, StereoMode
from openreview.core.cache import RingBufferCache, CacheMode


def test_tga_reading(tmp_path):
    tga_path = str(tmp_path / "test_texture.tga")
    # Create 64x64 RGBA test pattern
    arr = np.zeros((64, 64, 4), dtype=np.uint8)
    arr[:, :, 0] = 200  # R
    arr[:, :, 1] = 100  # G
    arr[:, :, 2] = 50   # B
    arr[:, :, 3] = 255  # A
    Image.fromarray(arr).save(tga_path)

    # Read via read_tga and read_image_file
    decoded = read_tga(tga_path)
    assert decoded is not None
    assert decoded.shape == (64, 64, 4)
    assert decoded.dtype == np.float32
    assert np.isclose(decoded[0, 0, 0], 200.0 / 255.0, atol=1e-2)
    assert np.isclose(decoded[0, 0, 1], 100.0 / 255.0, atol=1e-2)
    assert np.isclose(decoded[0, 0, 2], 50.0 / 255.0, atol=1e-2)

    decoded_gen = read_image_file(tga_path)
    assert decoded_gen is not None
    assert decoded_gen.shape == (64, 64, 4)


def test_tiff_16bit_reading(tmp_path):
    tif_path = str(tmp_path / "test_16bit.tif")
    # Create 16-bit uint gradient ramp
    arr = np.linspace(0, 65535, 48 * 48, dtype=np.uint16).reshape((48, 48))
    Image.fromarray(arr).save(tif_path)

    decoded = read_tiff(tif_path)
    assert decoded is not None
    assert decoded.shape == (48, 48, 4)
    assert decoded.dtype == np.float32
    assert decoded.max() > 0.95
    assert decoded.min() == 0.0


def test_multichannel_exr_and_cryptomatte(tmp_path):
    import OpenEXR
    import Imath

    exr_path = str(tmp_path / "comp_multichannel.exr")
    w, h = 32, 32
    header = OpenEXR.Header(w, h)
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    channels = {
        "R": Imath.Channel(pt),
        "G": Imath.Channel(pt),
        "B": Imath.Channel(pt),
        "A": Imath.Channel(pt),
        "diffuse.R": Imath.Channel(pt),
        "diffuse.G": Imath.Channel(pt),
        "diffuse.B": Imath.Channel(pt),
        "depth.Z": Imath.Channel(pt),
        "crypto_object00.R": Imath.Channel(pt),
        "crypto_object00.G": Imath.Channel(pt),
        "crypto_object00.B": Imath.Channel(pt),
        "crypto_object00.A": Imath.Channel(pt),
    }
    header["channels"] = channels
    out = OpenEXR.OutputFile(exr_path, header)

    r_buf = np.full((h, w), 0.8, dtype=np.float32).tobytes()
    g_buf = np.full((h, w), 0.2, dtype=np.float32).tobytes()
    b_buf = np.full((h, w), 0.1, dtype=np.float32).tobytes()
    a_buf = np.full((h, w), 1.0, dtype=np.float32).tobytes()
    diff_r = np.full((h, w), 0.4, dtype=np.float32).tobytes()
    diff_g = np.full((h, w), 0.9, dtype=np.float32).tobytes()
    diff_b = np.full((h, w), 0.3, dtype=np.float32).tobytes()
    depth_z = np.full((h, w), 150.0, dtype=np.float32).tobytes()

    # Cryptomatte ID (hash) in R and coverage in G
    crypto_id = np.uint32(0x123456).view(np.float32)
    c_r = np.full((h, w), crypto_id, dtype=np.float32).tobytes()
    c_g = np.full((h, w), 1.0, dtype=np.float32).tobytes()

    out.writePixels({
        "R": r_buf, "G": g_buf, "B": b_buf, "A": a_buf,
        "diffuse.R": diff_r, "diffuse.G": diff_g, "diffuse.B": diff_b,
        "depth.Z": depth_z,
        "crypto_object00.R": c_r,
        "crypto_object00.G": c_g,
        "crypto_object00.B": b_buf,
        "crypto_object00.A": a_buf,
    })
    out.close()

    # 1. Test channel discovery
    info = get_exr_channels(exr_path)
    assert "beauty" in info["layers"]
    assert "diffuse" in info["layers"]
    assert "depth" in info["layers"]
    assert "crypto_object" in info["cryptomatte_layers"]

    # 2. Test reading beauty layer
    beauty = read_exr(exr_path, layer="beauty")
    assert beauty is not None
    assert np.isclose(beauty[0, 0, 0], 0.8, atol=1e-2)

    # 3. Test reading diffuse layer
    diffuse = read_exr(exr_path, layer="diffuse")
    assert diffuse is not None
    assert np.isclose(diffuse[0, 0, 0], 0.4, atol=1e-2)
    assert np.isclose(diffuse[0, 0, 1], 0.9, atol=1e-2)

    # 4. Test reading depth layer
    depth = read_exr(exr_path, layer="depth")
    assert depth is not None
    assert depth.shape == (h, w, 4)

    # 5. Test reading Cryptomatte preview
    crypto = read_exr(exr_path, layer="crypto_object")
    assert crypto is not None
    assert crypto.shape == (h, w, 4)
    assert not np.all(crypto[:, :, :3] == 0)


def test_stereo_detection(tmp_path):
    # Test filename pair detection
    left_file = str(tmp_path / "shot_010_L.1001.exr")
    right_file = str(tmp_path / "shot_010_R.1001.exr")

    # Create dummy files
    open(left_file, "w").write("left")
    open(right_file, "w").write("right")

    pair = detect_stereo_counterpart(left_file)
    assert pair is not None
    assert os.path.normpath(pair.left_path) == os.path.normpath(left_file)
    assert os.path.normpath(pair.right_path) == os.path.normpath(right_file)

    # Test reverse detection from right
    pair_r = detect_stereo_counterpart(right_file)
    assert pair_r is not None
    assert os.path.normpath(pair_r.left_path) == os.path.normpath(left_file)
    assert os.path.normpath(pair_r.right_path) == os.path.normpath(right_file)


def test_two_tier_cache():
    cache = RingBufferCache(max_memory_mb=128.0, mode=CacheMode.PLAY_AHEAD)

    # Tier 1 Display Cache
    primary_data = np.zeros((100, 100, 4), dtype=np.float32)
    cache.put_source_frame("src_1", 1001, primary_data)
    assert cache.has_source_frame("src_1", 1001)
    assert cache.get_source_frame("src_1", 1001) is not None

    # Tier 2 Multi-channel Layer Cache
    diffuse_data = np.full((100, 100, 4), 0.5, dtype=np.float32)
    spec_data = np.full((100, 100, 4), 0.2, dtype=np.float32)

    cache.put_layer_frame("src_1", 1001, "diffuse", diffuse_data)
    cache.put_layer_frame("src_1", 1001, "specular", spec_data)

    assert cache.has_layer_frame("src_1", 1001, "diffuse")
    assert cache.has_layer_frame("src_1", 1001, "specular")
    cached_diff = cache.get_layer_frame("src_1", 1001, "diffuse")
    assert cached_diff is not None
    assert np.allclose(cached_diff[0, 0, 0], 0.5)

    # Clear source clears both tiers
    cache.clear_source("src_1")
    assert not cache.has_source_frame("src_1", 1001)
    assert not cache.has_layer_frame("src_1", 1001, "diffuse")
