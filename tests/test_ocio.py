"""
Unit tests for OCIO Manager and Shader Builder.
"""
from openreview.color.ocio_manager import OCIOManager
from openreview.color.shader_builder import build_fragment_shader


def test_ocio_manager_initialization():
    mgr = OCIOManager()
    assert mgr.has_ocio is True or mgr.has_ocio is False
    assert len(mgr.get_displays()) > 0
    assert len(mgr.get_views()) > 0
    assert len(mgr.get_color_spaces()) > 0


def test_ocio_pixel_processing():
    mgr = OCIOManager()
    # Test black
    r, g, b = mgr.process_rgb(0.0, 0.0, 0.0)
    assert r >= 0.0 and g >= 0.0 and b >= 0.0

    # Test mid grey
    r, g, b = mgr.process_rgb(0.18, 0.18, 0.18)
    assert 0.0 < r < 1.0

    # Test exposure gain
    mgr.exposure_ev = 1.0
    r_exp, _, _ = mgr.process_rgb(0.18, 0.18, 0.18)
    assert r_exp > r


def test_fragment_shader_generation():
    shader_code = build_fragment_shader()
    assert "#version 330 core" in shader_code
    assert "uExposure" in shader_code
    assert "uGamma" in shader_code
    assert "uChannelMode" in shader_code
    assert "uComparisonMode" in shader_code
    assert "uWipePos" in shader_code
    assert "uInputSpace" in shader_code
    assert "uViewTransform" in shader_code

