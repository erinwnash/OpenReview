"""
Automated unit and integration tests for OpenReview Advanced Color Grading, Log Curves, and LUT Engine.
"""
import os
import tempfile
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
from PySide6.QtGui import QSurfaceFormat, QOffscreenSurface, QOpenGLContext

from openreview.color.lut_manager import CubeLut, AscCdl, ColorGradeSettings
from openreview.color.shader_builder import VERTEX_SHADER_SOURCE, FRAGMENT_SHADER_SOURCE, build_fragment_shader
from openreview.ui.color_dialog import ColorAdjustmentsDialog
from openreview.ui.main_window import MainWindow


def test_asc_cdl_xml_and_text_parsing(tmp_path):
    # 1. XML CDL
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <ColorDecisionList xmlns="urn:ASC:CDL:v1.01">
        <ColorDecision>
            <ColorCorrection id="shot_010">
                <SOPNode>
                    <Slope>1.20 1.05 0.95</Slope>
                    <Offset>-0.02 0.01 0.03</Offset>
                    <Power>0.98 1.00 1.02</Power>
                </SOPNode>
                <SatNode>
                    <Saturation>1.15</Saturation>
                </SatNode>
            </ColorCorrection>
        </ColorDecision>
    </ColorDecisionList>
    """
    cdl_xml_file = tmp_path / "grade.cdl"
    cdl_xml_file.write_text(xml_content, encoding="utf-8")

    cdl1 = AscCdl.from_file(str(cdl_xml_file))
    assert pytest.approx(cdl1.slope, 1e-4) == (1.20, 1.05, 0.95)
    assert pytest.approx(cdl1.offset, 1e-4) == (-0.02, 0.01, 0.03)
    assert pytest.approx(cdl1.power, 1e-4) == (0.98, 1.00, 1.02)
    assert pytest.approx(cdl1.saturation, 1e-4) == 1.15

    # 2. Plain Text CDL
    txt_content = """# Plain Text CDL
    slope 1.1 1.0 0.9
    offset 0.05 -0.05 0.0
    power 1.0 1.0 1.0
    sat 0.85
    """
    cdl_txt_file = tmp_path / "simple.cdl"
    cdl_txt_file.write_text(txt_content, encoding="utf-8")

    cdl2 = AscCdl.from_file(str(cdl_txt_file))
    assert pytest.approx(cdl2.slope, 1e-4) == (1.1, 1.0, 0.9)
    assert pytest.approx(cdl2.offset, 1e-4) == (0.05, -0.05, 0.0)
    assert pytest.approx(cdl2.saturation, 1e-4) == 0.85


def test_cube_lut_3d_and_1d_parsing(tmp_path):
    # 1. 3D Cube LUT
    cube_3d_lines = [
        'TITLE "Test 3D LUT"',
        'LUT_3D_SIZE 2',
        'DOMAIN_MIN 0.0 0.0 0.0',
        'DOMAIN_MAX 1.0 1.0 1.0',
    ]
    # 2^3 = 8 points (R varies fastest, then G, then B)
    for b in range(2):
        for g in range(2):
            for r in range(2):
                cube_3d_lines.append(f"{r * 0.9:.4f} {g * 0.8:.4f} {b * 0.7:.4f}")

    lut_3d_file = tmp_path / "test3d.cube"
    lut_3d_file.write_text("\n".join(cube_3d_lines), encoding="utf-8")

    lut3d = CubeLut.from_file(str(lut_3d_file))
    assert lut3d.title == "Test 3D LUT"
    assert lut3d.size_3d == 2
    assert lut3d.data_3d is not None
    assert lut3d.data_3d.shape == (2, 2, 2, 3)
    assert pytest.approx(lut3d.data_3d[0, 0, 1, 0], 1e-3) == 0.9

    # 2. 1D Cube LUT
    cube_1d_lines = [
        'TITLE "Test 1D LUT"',
        'LUT_1D_SIZE 4',
    ]
    for i in range(4):
        val = i / 3.0
        cube_1d_lines.append(f"{val * 0.5:.4f} {val * 0.7:.4f} {val * 1.0:.4f}")

    lut_1d_file = tmp_path / "test1d.cube"
    lut_1d_file.write_text("\n".join(cube_1d_lines), encoding="utf-8")

    lut1d = CubeLut.from_file(str(lut_1d_file))
    assert lut1d.size_1d == 4
    assert lut1d.size_3d > 0  # converted to 3D equivalent table
    assert lut1d.data_3d is not None
    assert lut1d.data_3d.shape == (lut1d.size_3d, lut1d.size_3d, lut1d.size_3d, 3)


def test_color_grade_settings_reset():
    s = ColorGradeSettings()
    assert s.gain == (1.0, 1.0, 1.0)
    assert s.gamma == 1.0
    assert s.contrast == 1.0
    assert s.saturation == 1.0
    assert not s.invert_colors
    assert not s.show_out_of_range

    s.gain = (2.0, 1.5, 0.5)
    s.gamma = 1.8
    s.contrast = 1.3
    s.saturation = 0.5
    s.hue = 45.0
    s.brightness = 0.5
    s.invert_colors = True
    s.show_out_of_range = True

    s.reset()
    assert s.gain == (1.0, 1.0, 1.0)
    assert s.gamma == 1.0
    assert s.contrast == 1.0
    assert s.hue == 0.0
    assert s.brightness == 0.0
    assert not s.invert_colors
    assert not s.show_out_of_range


def test_glsl_color_and_log_shader_code():
    frag_source = build_fragment_shader()
    assert "#version 330 core" in frag_source
    assert "cineon_to_linear" in frag_source
    assert "alexa_logc_to_linear" in frag_source
    assert "alexa_logc_film_to_linear" in frag_source
    assert "rec709_to_linear" in frag_source
    assert "gamma22_to_linear" in frag_source
    assert "uHasCdl" in frag_source
    assert "uCdlSlope" in frag_source
    assert "uCdlOffset" in frag_source
    assert "uCdlPower" in frag_source
    assert "uCdlSat" in frag_source
    assert "uHasLut3D" in frag_source
    assert "uLut3D" in frag_source
    assert "uGradingGain" in frag_source
    assert "uGradingOffset" in frag_source
    assert "uGradingGamma" in frag_source
    assert "uGradingContrast" in frag_source
    assert "uGradingSat" in frag_source
    assert "uGradingHue" in frag_source
    assert "uDisplayBrightness" in frag_source
    assert "uInvertColors" in frag_source
    assert "uShowOutOfRange" in frag_source
    assert "srgb_to_linear" in frag_source
    assert "linear_to_srgb" in frag_source
    assert "aces_filmic" in frag_source


def test_color_adjustments_dialog(qtbot):
    settings = ColorGradeSettings()
    dlg = ColorAdjustmentsDialog(settings)
    qtbot.addWidget(dlg)

    emitted_settings = []
    dlg.colorGradeChanged.connect(lambda s: emitted_settings.append(s))

    # Adjust master gain
    dlg.row_gain_m.set_value(1.5)
    dlg.row_gain_m.valueChanged.emit(1.5)
    assert len(emitted_settings) > 0
    assert pytest.approx(dlg.settings.gain[0], 1e-2) == 1.5
    assert pytest.approx(dlg.settings.gain[1], 1e-2) == 1.5
    assert pytest.approx(dlg.settings.gain[2], 1e-2) == 1.5

    # Toggle invert colors
    dlg.chk_invert.setChecked(True)
    assert dlg.settings.invert_colors is True

    # Toggle out of range
    dlg.chk_out_of_range.setChecked(True)
    assert dlg.settings.show_out_of_range is True

    # Reset all
    dlg.btn_reset_all.click()
    assert dlg.settings.gain == (1.0, 1.0, 1.0)
    assert dlg.settings.invert_colors is False
    assert dlg.settings.show_out_of_range is False


def test_main_window_color_and_lut_integration(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    # 1. Test Input Colorspace switching (Cineon Log = 3, ALEXA LogC = 4, etc.)
    window._on_set_input_space(3)
    assert window.viewport.input_space == 3
    assert window.top_bar.input_combo.currentIndex() == 3

    window._on_set_input_space(4)
    assert window.viewport.input_space == 4
    assert window.top_bar.input_combo.currentIndex() == 4

    # 2. Test View Transform switching (Rec.709 = 3, File Gamma 2.2 = 4, etc.)
    window._on_set_view_transform(3)
    assert window.viewport.view_transform == 3
    assert window.top_bar.view_combo.currentIndex() == 3

    # 3. Test Invert Colors toggle
    window._on_toggle_invert_colors(True)
    assert window.viewport.color_grading.invert_colors is True
    window._on_toggle_invert_colors(False)
    assert window.viewport.color_grading.invert_colors is False

    # 4. Test Out-of-Range toggle
    window._on_toggle_out_of_range(True)
    assert window.viewport.color_grading.show_out_of_range is True
    window._on_toggle_out_of_range(False)
    assert window.viewport.color_grading.show_out_of_range is False

    # 5. Test LUT and CDL upload to Viewport
    lut_lines = ['TITLE "TestLUT"', 'LUT_3D_SIZE 2']
    for b in range(2):
        for g in range(2):
            for r in range(2):
                lut_lines.append(f"{r:.2f} {g:.2f} {b:.2f}")
    lut_path = tmp_path / "lut.cube"
    lut_path.write_text("\n".join(lut_lines), encoding="utf-8")
    lut = CubeLut.from_file(str(lut_path))
    window.viewport.set_lut(lut)
    assert window.viewport.color_grading.active_lut is not None

    cdl_path = tmp_path / "grade.cdl"
    cdl_path.write_text("slope 1.2 1.0 0.8\noffset 0 0 0\npower 1 1 1\nsat 1.0", encoding="utf-8")
    cdl = AscCdl.from_file(str(cdl_path))
    window.viewport.set_cdl(cdl)
    assert window.viewport.color_grading.active_cdl is not None

    # Clear LUT and CDL
    window._on_clear_lut_and_cdl()
    assert window.viewport.color_grading.active_lut is None
    assert window.viewport.color_grading.active_cdl is None

    # 6. Test Reset All Colors
    window.top_bar.set_exposure(2.5)
    window.top_bar.set_gamma(1.5)
    window.viewport.color_grading.contrast = 1.8
    window._on_reset_all_colors()
    assert window.top_bar.exposure_ev == 0.0
    assert window.top_bar.gamma == 1.0
    assert window.viewport.color_grading.contrast == 1.0
