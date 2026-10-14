import pytest
from PySide6.QtWidgets import QApplication
from openreview.models.annotations import AnnotationStore
from openreview.widgets.viewport import ViewportCanvas


def test_viewport_geometry_transforms(qapp):
    store = AnnotationStore()
    vp = ViewportCanvas(store)

    # Defaults
    assert vp.flip_x is False
    assert vp.flip_y is False
    assert vp.rotation == 0
    assert vp.pixel_aspect_ratio == 1.0

    # Flip / Flop
    vp.set_flip_x(True)
    assert vp.flip_x is True
    vp.toggle_flop_x()
    assert vp.flip_x is False

    vp.set_flip_y(True)
    assert vp.flip_y is True
    vp.toggle_flip_y()
    assert vp.flip_y is False

    # Rotation
    vp.set_rotation(90)
    assert vp.rotation == 90
    vp.set_rotation(450)  # 450 % 360 = 90
    assert vp.rotation == 90
    vp.set_rotation(180)
    assert vp.rotation == 180

    # PAR
    vp.set_pixel_aspect_ratio(2.0)
    assert vp.pixel_aspect_ratio == 2.0

    # Reset
    vp.reset_transforms()
    assert vp.flip_x is False
    assert vp.flip_y is False
    assert vp.rotation == 0
    assert vp.pixel_aspect_ratio == 1.0
    assert vp.zoom == 1.0


def test_viewport_mattes_and_background(qapp):
    store = AnnotationStore()
    vp = ViewportCanvas(store)

    assert vp.matte_ratio is None
    assert vp.matte_opacity == 1.0
    assert vp.background_mode == "black"

    # Set Matte
    vp.set_matte(2.35, 0.5)
    assert abs(vp.matte_ratio - 2.35) < 0.001
    assert abs(vp.matte_opacity - 0.5) < 0.001

    vp.set_matte(None)
    assert vp.matte_ratio is None

    # Background modes
    for mode in ["black", "grey18", "grey50", "white", "checker"]:
        vp.set_background_mode(mode)
        assert vp.background_mode == mode


def test_viewport_scale_presets(qapp):
    store = AnnotationStore()
    vp = ViewportCanvas(store)
    vp.resize(1920, 1080)

    vp.set_scale_preset(1.0)
    assert vp.zoom > 0

    vp.set_scale_preset(2.0)
    assert vp.zoom > 0

    vp.fit_width()
    assert vp.zoom > 0
