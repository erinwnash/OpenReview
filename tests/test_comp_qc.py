"""
Comprehensive Unit Tests for xtra QC Utils (Comp QC Built-in Plugin).
Covers package discovery, manifest validation, plugin lifecycle,
CompQCState reactive model, GLSL shader integration, HUD widget interaction,
smart latching, and MainWindow integration.
"""
import pytest
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QColor, QPainterPath, QKeyEvent, QWheelEvent

from openreview.packages.package_manager import PackageManager
from openreview.packages.builtin.comp_qc.qc_state import CompQCState, QcMode, HslMode
from openreview.packages.builtin.comp_qc.hud_comp_qc import (
    XtraQCWidget,
    XtraQCDockWidget,
    CompQCHUDWidget,
    CompQCDockWidget,
    BlenderScrollArea,
)
from openreview.packages.builtin.comp_qc.plugin import CompQCPlugin
from openreview.color.shader_builder import build_fragment_shader, ShaderUniforms


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


# =============================================================================
# 1. Package Discovery & Manifest Validation
# =============================================================================
def test_comp_qc_manifest_discovery(qapp):
    pkg_mgr = PackageManager()
    packages = pkg_mgr.discover_packages()
    qc_manifest = next((p for p in packages if p.name == "xtra-qc-Utils"), None)

    assert qc_manifest is not None, "xtra-qc-Utils package not discovered"
    assert qc_manifest.is_builtin is True
    assert qc_manifest.enabled is False
    assert qc_manifest.entrypoint == "plugin.py"
    assert "quality control" in qc_manifest.description.lower()


# =============================================================================
# 2. CompQCState Reactive Data Model Tests
# =============================================================================
def test_qc_state_defaults_and_mutation(qapp):
    state = CompQCState()
    assert state.qc_mode == QcMode.OFF
    assert state.qc_gamma == 1.0
    assert state.qc_gain == 1.0
    assert state.qc_softclip == 1.0
    assert state.qc_sat_multiplier == 1.0
    assert state.blur_radius == 3.0
    assert state.grain_boost == 5.0
    assert state.edge_threshold == 0.0
    assert state.compare_against_plate is False
    assert state.alpha_overlay_enabled is False
    assert state.clamp_alpha is False
    assert state.mix_overlay == 1.0
    assert state.overlay_color.isValid()
    assert state.hsl_mode == HslMode.OFF

    # Change tracking
    changes = []
    state.changed.connect(lambda: changes.append(True))

    state.qc_gamma = 1.8
    assert len(changes) == 1
    assert state.qc_gamma == 1.8

    state.qc_gain = 2.5
    assert len(changes) == 2
    assert state.qc_gain == 2.5

    state.qc_softclip = 0.4
    assert len(changes) == 3
    assert state.qc_softclip == 0.4

    state.qc_sat_multiplier = 2.0
    assert len(changes) == 4

    state.hsl_mode = HslMode.LUMINANCE
    assert state.hsl_mode == HslMode.LUMINANCE

    state.qc_mode = QcMode.GRAIN_CHECK
    assert state.qc_mode == QcMode.GRAIN_CHECK

    state.blur_radius = 6.0
    assert state.blur_radius == 6.0

    state.compare_against_plate = True
    assert state.compare_against_plate is True

    state.source_plate_path = "/path/to/plate.1001.exr"
    assert state.source_plate_path == "/path/to/plate.1001.exr"

    state.source_prefetch_progress = 0.75
    assert state.source_prefetch_progress == 0.75

    state.matte_path = "/path/to/matte.1001.exr"
    assert state.matte_path == "/path/to/matte.1001.exr"

    state.enable_red = False
    assert state.enable_red is False

    state.expr_red = "1 - a"
    assert state.expr_red == "1 - a"

    state.alpha_overlay_enabled = True
    assert state.alpha_overlay_enabled is True

    state.overlay_color = QColor(255, 0, 0)
    assert state.overlay_color == QColor(255, 0, 0)

    # Reset
    state.reset_defaults()
    assert state.qc_gamma == 1.0
    assert state.qc_gain == 1.0
    assert state.qc_softclip == 1.0
    assert state.qc_sat_multiplier == 1.0
    assert state.qc_mode == QcMode.OFF
    assert state.hsl_mode == HslMode.OFF
    assert state.compare_against_plate is False
    assert state.enable_red is True
    assert state.alpha_overlay_enabled is False
    assert state.clamp_alpha is False


# =============================================================================
# 3. GLSL Fragment Shader Integration Tests
# =============================================================================
def test_glsl_fragment_shader_qc_uniforms_and_functions():
    shader_code = build_fragment_shader()

    # Check uniform declarations
    assert "uniform int uQcMode;" in shader_code
    assert "uniform float uQcClippingThreshold;" in shader_code
    assert "uniform float uQcGamma;" in shader_code
    assert "uniform float uQcGain;" in shader_code
    assert "uniform float uQcSoftclip;" in shader_code
    assert "uniform float uQcSatMultiplier;" in shader_code
    assert "uniform float uQcEdgeThreshold;" in shader_code
    assert "uniform bool uQcCompareAgainstPlate;" in shader_code
    assert "uniform sampler2D uTextureMatte;" in shader_code
    assert "uniform bool uHasTextureMatte;" in shader_code
    assert "uniform vec4 uQcMatteChannels;" in shader_code
    assert "uniform float uQcMixOverlay;" in shader_code

    # Check shader helper functions
    assert "vec3 linear_to_cineon(vec3 c)" in shader_code
    assert "vec3 rgb2hsl(vec3 c)" in shader_code

    # Check shader execution logic
    assert "uQcCompareAgainstPlate" in shader_code
    assert "uQcSoftclip" in shader_code
    assert "uQcSatMultiplier" in shader_code
    assert "uQcAlphaMaskEnabled" in shader_code
    assert "uTextureMatte" in shader_code

    # Check ShaderUniforms dataclass
    u = ShaderUniforms()
    assert hasattr(u, "qc_gamma")
    assert hasattr(u, "qc_gain")
    assert hasattr(u, "qc_softclip")
    assert hasattr(u, "qc_sat_multiplier")
    assert hasattr(u, "qc_edge_threshold")
    assert hasattr(u, "qc_compare_against_plate")
    assert hasattr(u, "qc_matte_channels")
    assert hasattr(u, "qc_mix_overlay")


# =============================================================================
# 4. xtra QC Utils HUD Widget Controls
# =============================================================================
def test_xtra_qc_hud_widget_components(qapp):
    state = CompQCState()
    widget = XtraQCWidget(state)

    # 1. Test collapsible section headers defaults (Source Plate & Matte Loader expanded, others collapsed)
    assert hasattr(widget, "sec_source_header") and hasattr(widget, "sec_source_body")
    assert hasattr(widget, "sec_cc_header") and hasattr(widget, "sec_cc_body")
    assert hasattr(widget, "sec_hsl_header") and hasattr(widget, "sec_hsl_body")
    assert hasattr(widget, "sec_matte_loader_header") and hasattr(widget, "sec_matte_loader_body")
    assert hasattr(widget, "sec_matte_header") and hasattr(widget, "sec_matte_body")

    # Source Plate and Matte Loader are expanded by default
    assert widget.sec_source_header.is_expanded() is True
    assert widget.sec_source_body.isHidden() is False

    assert widget.sec_matte_loader_header.is_expanded() is True
    assert widget.sec_matte_loader_body.isHidden() is False
    assert widget.sec_matte_loader_header.lbl_title.text() == "Matte Loader"

    # Color correction, HSL, and Matte Check Controls are collapsed by default
    assert widget.sec_cc_header.is_expanded() is False
    assert widget.sec_cc_body.isHidden() is True
    assert widget.sec_cc_header.lbl_title.text() == "Color correction"

    assert widget.sec_hsl_header.is_expanded() is False
    assert widget.sec_hsl_body.isHidden() is True

    assert widget.sec_matte_header.is_expanded() is False
    assert widget.sec_matte_body.isHidden() is True
    assert widget.sec_matte_header.lbl_title.text() == "Matte Check Controls"

    # Test toggling Color correction section
    widget.sec_cc_header.set_expanded(True)
    assert widget.sec_cc_header.is_expanded() is True
    assert not widget.sec_cc_body.isHidden()
    widget.sec_cc_header.set_expanded(False)
    assert widget.sec_cc_header.is_expanded() is False
    assert widget.sec_cc_body.isHidden()

    # Test sliders
    widget.slider_gamma.set_value(2.2, emit_signal=True)
    assert abs(state.qc_gamma - 2.2) < 0.01

    widget.slider_gain.set_value(1.5, emit_signal=True)
    assert abs(state.qc_gain - 1.5) < 0.01

    widget.slider_softclip.set_value(0.5, emit_signal=True)
    assert abs(state.qc_softclip - 0.5) < 0.01

    widget.slider_sat.set_value(3.0, emit_signal=True)
    assert abs(state.qc_sat_multiplier - 3.0) < 0.01

    # 2. Test HSL Solo toggles
    widget.btn_hue.click()
    assert state.hsl_mode == HslMode.HUE
    widget.btn_hue.click()
    assert state.hsl_mode == HslMode.OFF

    widget.btn_sat.click()
    assert state.hsl_mode == HslMode.SATURATION
    widget.btn_lum.click()
    assert state.hsl_mode == HslMode.LUMINANCE

    # 3. Test 2x3 Grid QC Mode Buttons
    widget.btn_grain.click()
    assert state.qc_mode == QcMode.GRAIN_CHECK
    widget.btn_black.click()
    assert state.qc_mode == QcMode.BLACK_LEVELS
    widget.btn_neg.click()
    assert state.qc_mode == QcMode.NEGATIVE_PIXELS
    widget.btn_highpass.click()
    assert state.qc_mode == QcMode.HIGHPASS_COMP
    widget.btn_diff.click()
    assert state.qc_mode == QcMode.COMP_DIFF_PLATE
    widget.btn_nan.click()
    assert state.qc_mode == QcMode.NAN_INF_PIXELS

    # 4. Test Compare against plate
    assert state.compare_against_plate is False
    widget.btn_compare_plate.click()
    assert state.compare_against_plate is True
    widget.btn_compare_plate.click()
    assert state.compare_against_plate is False

    # 5. Test Matte channels
    widget.chk_red.setChecked(False)
    assert state.enable_red is False

    widget.txt_expr_r.setText("1-a")
    widget.txt_expr_r.returnPressed.emit()
    assert state.expr_red == "1-a"

    # 6. Test Alpha Overlay & Mix
    widget.btn_alpha_overlay.click()
    assert state.alpha_overlay_enabled is True

    # Clamp alpha defaults to Off/False; clicking turns it On/True
    assert state.clamp_alpha is False
    assert widget.btn_clamp.text() == "Off"
    widget.btn_clamp.click()
    assert state.clamp_alpha is True
    assert widget.btn_clamp.text() == "On"
    widget.btn_clamp.click()
    assert state.clamp_alpha is False
    assert widget.btn_clamp.text() == "Off"

    # Edge threshold was removed
    assert not hasattr(widget, "slider_edge_thresh")

    widget.slider_mix.setValue(50)
    assert abs(state.mix_overlay - 0.5) < 0.02
    assert abs(widget.spin_mix.value() - 0.5) < 0.02

    # 7. Test Reset Button
    widget.btn_reset.click()
    assert state.qc_gamma == 1.0
    assert state.qc_softclip == 1.0
    assert state.qc_mode == QcMode.OFF
    assert state.hsl_mode == HslMode.OFF
    assert state.alpha_overlay_enabled is False


# =============================================================================
# 5. Plugin Lifecycle & MainWindow Integration
# =============================================================================
def test_comp_qc_plugin_integration(qapp):
    from openreview.packages.manifest import PackageManifest
    from openreview.packages.plugin_base import PluginContext
    from openreview.widgets.floating_hud import FloatingHUDCard

    class MockViewport(QWidget):
        def __init__(self):
            super().__init__()
            self._img_width = 1920
            self._img_height = 1080
            self.comp_qc_state = None

    class MockMainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.viewport = MockViewport()
            self.hud_comp_qc = None
            self.comp_qc_state = None

    win = MockMainWindow()
    manifest = PackageManifest(
        name="xtra-qc-Utils",
        version="1.0.0",
        author="OpenReview",
        description="xtra QC Utils",
        entrypoint="plugin.py",
        is_builtin=True,
    )
    ctx = PluginContext(manifest, main_window=win)
    plugin = CompQCPlugin(ctx)

    plugin.initialize()
    assert win.hud_comp_qc is not None
    assert isinstance(win.hud_comp_qc, FloatingHUDCard)
    assert win.hud_comp_qc._title == "xtra QC Utils"
    assert win.comp_qc_state is not None
    assert win.viewport.comp_qc_state is win.comp_qc_state

    # Test toggle
    assert win.hud_comp_qc.isHidden()
    plugin.toggle_hud()
    assert not win.hud_comp_qc.isHidden()
    plugin.toggle_hud()
    assert win.hud_comp_qc.isHidden()

    # Shutdown
    plugin.shutdown()
    assert plugin.hud_card is None


# =============================================================================
# 6. XtraQCDockWidget, Smart Latch & Blender Scroll Tests
# =============================================================================
def test_xtra_qc_dock_and_smart_latch(qapp):
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent

    state = CompQCState()
    dock = XtraQCDockWidget(state)
    assert dock.objectName() == "CompQCDockWidget"
    assert "xtra QC Utils" in dock.windowTitle()
    assert dock.panel is not None

    # Latch starts False
    assert dock.is_latched() is False

    # Latch via pin button
    dock.panel.btn_pin.setChecked(True)
    assert dock.is_latched() is True
    dock.panel.btn_pin.setChecked(False)
    assert dock.is_latched() is False

    # Latch via user interaction
    dock.set_latched(True)
    assert dock.is_latched() is True

    # Closing unlatches
    dock.close()
    assert dock.is_latched() is False


def test_comp_qc_shortcut_definition():
    from openreview.core.shortcuts import ShortcutManager
    sm = ShortcutManager()
    action = sm.get_action("hud.comp_qc")
    assert action is not None
    assert action.default_shortcut == "Q"
    assert action.effective_shortcut == "Q"
    assert "xtra QC Utils" in action.name


def test_main_window_comp_qc_dock(qtbot):
    from openreview.packages.package_manager import PackageManager
    from openreview.ui.main_window import MainWindow

    pkg_mgr = PackageManager.instance()
    pkg_mgr.set_package_enabled("xtra-qc-Utils", True)
    try:
        win = MainWindow()
        qtbot.addWidget(win)

        assert hasattr(win, "comp_qc_dock")
        assert hasattr(win, "comp_qc_state")
        assert win.viewport.comp_qc_state is win.comp_qc_state

        # Hidden by default
        assert win.comp_qc_dock.isHidden() is True

        # Toggle open with Q callback
        win._on_toggle_comp_qc()
        assert win.comp_qc_dock.isHidden() is False

        # Toggle closed
        win._on_toggle_comp_qc()
        assert win.comp_qc_dock.isHidden() is True

        win.close()
    finally:
        pkg_mgr.set_package_enabled("xtra-qc-Utils", False)


def test_comp_qc_drop_plate_and_matte(tmp_path, qtbot):
    from PIL import Image
    from openreview.ui.main_window import MainWindow
    from openreview.core.reader import ReaderEngine

    # Create dummy image file
    img_path = str(tmp_path / "test_plate.1001.png")
    img = Image.new("RGBA", (64, 64), (200, 100, 50, 255))
    img.save(img_path)

    # 1. Verify ReaderEngine.create_reader works directly
    reader = ReaderEngine.create_reader(img_path)
    assert reader is not None
    frame_data = reader.read_frame(1001)
    assert frame_data is not None
    assert frame_data.shape[0] == 64 and frame_data.shape[1] == 64

    # 2. Test MainWindow drop slots
    win = MainWindow()
    qtbot.addWidget(win)

    # Drop plate
    win._on_comp_qc_source_dropped(img_path)
    assert win.comp_qc_state.source_plate_path == img_path
    assert win._reader_b is not None
    assert win.viewport._image_b is not None

    # Unload plate
    win._on_comp_qc_unload_source()
    assert win.comp_qc_state.source_plate_path is None
    assert win._reader_b is None
    assert win.viewport._image_b is None

    # Drop matte
    win._on_comp_qc_matte_dropped(img_path)
    assert win.comp_qc_state.matte_path == img_path
    assert win._reader_matte is not None
    assert win.viewport._image_matte is not None

    # Unload matte
    win._on_comp_qc_unload_matte()
    assert win.comp_qc_state.matte_path is None
    assert win._reader_matte is None
    assert win.viewport._image_matte is None

    # Test invalid path handling does not raise NameError or unhandled exception
    win._on_comp_qc_source_dropped("non_existent_folder/missing_file.exr")
    win._on_comp_qc_matte_dropped("non_existent_folder/missing_file.exr")

    win.close()


def test_xtra_qc_new_controls(qapp):
    """Test dedicated HSL mode, Hipass value, Grain Boost [0-100], Compare plates, Overlay Matte, and diagnostic modes."""
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF

    state = CompQCState()
    widget = XtraQCWidget(state)

    # 1. Dedicated HSL Mode button
    assert state.hsl_mode == HslMode.OFF
    widget.btn_hsl_mode.click()
    assert state.hsl_mode == HslMode.FULL_HSL
    widget.btn_hsl_mode.click()
    assert state.hsl_mode == HslMode.OFF

    # 2. Hipass slider (0-10)
    widget.slider_hipass.set_value(7.5, emit_signal=True)
    assert abs(state.hipass_value - 7.5) < 0.01
    assert abs(state.blur_radius - 7.5) < 0.01

    # 3. Grain Boost slider (0-100 raw mapped to 0-10)
    widget.slider_grain_boost.set_value(80.0, emit_signal=True)
    assert abs(state.grain_boost_raw - 80.0) < 0.01
    assert abs(state.grain_boost - 8.0) < 0.01

    # 4. Compare plates button
    assert state.compare_plates is False
    widget.btn_compare_plate.click()
    assert state.compare_plates is True
    assert state.compare_against_plate is True
    widget.btn_compare_plate.click()
    assert state.compare_plates is False

    # 5. Overlay Matte button (O)
    assert state.overlay_matte_enabled is False
    assert widget.btn_overlay_matte.text() == "Overlay Matte  (O)"
    widget.btn_overlay_matte.click()
    assert state.overlay_matte_enabled is True
    widget.btn_overlay_matte.click()
    assert state.overlay_matte_enabled is False

    # 6. greycheck and Checkerboard preview icons and mutual exclusivity
    assert not widget.btn_greycheck.icon().isNull()
    assert not widget.btn_checkerboard.icon().isNull()
    assert state.greycheck_enabled is False
    assert state.checkerboard_enabled is False

    widget.btn_greycheck.click()
    assert state.greycheck_enabled is True
    assert state.checkerboard_enabled is False

    widget.btn_checkerboard.click()
    assert state.checkerboard_enabled is True
    assert state.greycheck_enabled is False  # Mutually exclusive

    widget.btn_checkerboard.click()
    assert state.checkerboard_enabled is False

    # 7. Diagnostic sliders
    widget.slider_grey_val.set_value(0.75, emit_signal=True)
    assert abs(state.grey_value - 0.75) < 0.01

    widget.slider_grid_scale.set_value(64.0, emit_signal=True)
    assert abs(state.grid_scale - 64.0) < 0.01

    widget.slider_checker_contrast.set_value(0.4, emit_signal=True)
    assert abs(state.checker_contrast - 0.4) < 0.01

    # 8. Wheel scroll suppression on sliders and spinboxes
    slider = widget.slider_gamma.slider
    initial_val = slider.value()
    wheel_ev = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    slider.wheelEvent(wheel_ev)
    assert slider.value() == initial_val
    assert wheel_ev.isAccepted() is False


def test_xtra_qc_source_bin_caching_and_session_reset(qtbot, tmp_path):
    """Test source bin filing under 'QC References', thumbnails, caching eviction, and session clear."""
    from PIL import Image
    from openreview.packages.package_manager import PackageManager
    from openreview.ui.main_window import MainWindow
    from PySide6.QtGui import QKeyEvent

    pkg_mgr = PackageManager.instance()
    pkg_mgr.set_package_enabled("xtra-qc-Utils", True)
    try:
        img_path = str(tmp_path / "test_qc_plate.png")
        img = Image.new("RGBA", (128, 128), (40, 180, 90, 255))
        img.save(img_path)

        win = MainWindow()
        qtbot.addWidget(win)

        # Precondition: active view exists or is created
        assert win.session_graph is not None

        # Drop plate onto QC
        win._on_comp_qc_source_dropped(img_path)

        # 1. Verify filed into 'QC References' folder
        qc_folder = next((f for f in win.session_graph.folders.values() if f.name == "QC References"), None)
        assert qc_folder is not None, "QC References folder not created in session graph"
        assert win.comp_qc_state.source_item_id is not None
        assert win.comp_qc_state.source_item_id in qc_folder.source_ids

        # 2. Verify thumbnail was set in drop placeholder
        dock = getattr(win, "comp_qc_dock", None)
        panel = getattr(dock, "panel", dock) if dock else getattr(win, "hud_comp_qc", None)
        assert panel is not None
        assert not panel.drop_source.lbl_thumb.isHidden()
        assert panel.drop_source.lbl_thumb.pixmap() is not None

        # 3. Test caching and cache eviction
        win._on_comp_qc_prefetch_source()
        win._on_background_caching_progress(win.comp_qc_state.source_item_id, 10, 10)
        assert win.comp_qc_state.source_prefetch_progress == 1.0

        win._on_clear_cache()
        assert win.comp_qc_state.source_prefetch_progress == 0.0

        # 4. Test Key_O and Key_0 shortcuts toggle Overlay Matte
        assert win.comp_qc_state.overlay_matte_enabled is False
        key_event_o = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_O, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(key_event_o)
        assert win.comp_qc_state.overlay_matte_enabled is True
        win.keyPressEvent(key_event_o)
        assert win.comp_qc_state.overlay_matte_enabled is False

        key_event_0 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_0, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(key_event_0)
        assert win.comp_qc_state.overlay_matte_enabled is True
        win.keyPressEvent(key_event_0)
        assert win.comp_qc_state.overlay_matte_enabled is False

        # 5. Test session reset unloads plates
        win._perform_atomic_session_reset()
        assert win.comp_qc_state.source_plate_path is None
        assert win.comp_qc_state.matte_path is None
        assert win._reader_b is None
        assert win._reader_matte is None
        assert panel.drop_source.lbl_thumb.isHidden()

        win.close()
    finally:
        pkg_mgr.set_package_enabled("xtra-qc-Utils", False)


def test_compare_plates_effective_dimensions_preserves_aspect_ratio(qtbot):
    """Verify Compare Plates doubles canvas width to preserve 100% native aspect ratio."""
    from openreview.widgets.viewport import ViewportCanvas
    from openreview.models.annotations import AnnotationStore
    from PySide6.QtOpenGL import QOpenGLTexture

    store = AnnotationStore()
    vp = ViewportCanvas(store)
    qtbot.addWidget(vp)

    vp._img_width = 1920
    vp._img_height = 1080
    vp.pixel_aspect_ratio = 1.0

    state = CompQCState()
    vp.comp_qc_state = state

    # Normal mode
    w, h = vp._effective_image_dimensions()
    assert w == 1920.0
    assert h == 1080.0

    # Compare plates ON without texture B -> single image
    state.compare_plates = True
    w, h = vp._effective_image_dimensions()
    assert w == 1920.0

    # Compare plates ON with mock texture B -> double canvas width
    vp._texture_b = object()  # mock non-None
    w, h = vp._effective_image_dimensions()
    assert w == 3840.0
    assert h == 1080.0
    # Native aspect ratio of each plate is 1920 / 1080 = 1.777, preserved exactly in side-by-side quad
    assert (w / 2.0) / h == 1920.0 / 1080.0

    vp.close()


def test_overlay_matte_expressions_and_sync(qtbot, tmp_path):
    """Verify channel expressions compilation and Overlay Matte frame synchronization."""
    from PIL import Image
    from openreview.ui.main_window import MainWindow
    from openreview.color.shader_builder import compile_channel_expression, build_fragment_shader

    # 1. Test expression compiler
    assert compile_channel_expression("", "r") == "mRaw.r"
    assert "1.0 - mRaw.a" in compile_channel_expression("1-a", "a")
    assert "mRaw.r * 2.0" in compile_channel_expression("r*2", "r")
    assert "max ( mRaw.r , mRaw.g )" in compile_channel_expression("max(r, g)", "r")
    assert "((mRaw.r + mRaw.g) * 0.5)" in compile_channel_expression("avg(r, g)", "b")

    # 2. Test shader compilation with expressions
    frag_src = build_fragment_shader(expr_r="1-a", expr_g="g", expr_b="b", expr_a="max(r, g)")
    assert "1.0 - mRaw.a" in frag_src
    assert "max ( mRaw.r , mRaw.g )" in frag_src

    # 3. Test MainWindow matte drop and toggle synchronization
    matte_path = str(tmp_path / "test_matte.png")
    m_img = Image.new("RGBA", (64, 64), (255, 0, 0, 200))
    m_img.save(matte_path)

    win = MainWindow()
    qtbot.addWidget(win)

    win._on_comp_qc_matte_dropped(matte_path)
    assert win._reader_matte is not None

    # Toggling overlay matte syncs the matte frame
    win.comp_qc_state.overlay_matte_enabled = True
    win._sync_matte_frame()
    assert win.viewport._image_matte is not None

    # Expression changes update the shader on the viewport
    win.comp_qc_state.expr_alpha = "1-a"
    win._on_comp_qc_state_changed()

    win.close()


def test_difference_and_clamp_alpha_shader():
    """Verify shader code for Difference overlay (red constant) and strict Clamp Alpha."""
    frag_src = build_fragment_shader()
    
    # 1. Difference mode overlay logic (mix red constant where diffAmt > 0.005)
    assert "float diffAmt = length(linearRgb - linB);" in frag_src
    assert "if (diffAmt > 0.005)" in frag_src
    assert "mix(displayRgb, vec3(1.0, 0.0, 0.0), 0.75)" in frag_src

    # 2. Strict clamp alpha (values < 1.0 become 0.0)
    assert "(colMatte.a >= 0.999) ? 1.0 : 0.0" in frag_src


def test_image_sequence_loading_and_playback(tmp_path, qtbot):
    """Verify image sequence detection, multi-frame playback with DiskSequenceReader, and timeline frame mapping."""
    import numpy as np
    from PIL import Image
    from openreview.core.sequence_parser import detect_image_sequence, DiskSequenceReader
    from openreview.ui.main_window import MainWindow

    # 1. Create a dummy 5-frame image sequence (1001-1005) with different colors
    seq_dir = tmp_path / "seq"
    seq_dir.mkdir()
    for f in range(1001, 1006):
        arr = np.full((32, 32, 4), [f - 1000, 50, 100, 255], dtype=np.uint8)
        Image.fromarray(arr).save(str(seq_dir / f"plate.{f:04d}.png"))

    first_file = str(seq_dir / "plate.1001.png")
    seq = detect_image_sequence(first_file)
    assert seq is not None
    assert len(seq.available_frames) == 5
    assert seq.start_frame == 1001
    assert seq.end_frame == 1005

    # 2. Test DiskSequenceReader reading sequential frames
    reader = DiskSequenceReader(seq)
    f1 = reader.read_frame(1001)
    f2 = reader.read_frame(1002)
    f3 = reader.read_frame(1003)
    assert f1 is not None and f2 is not None and f3 is not None
    # Ensure sequential read returns distinct frames and does NOT freeze on frame 1001
    assert abs(f1[0, 0, 0] - 1.0 / 255.0) < 1e-4
    assert abs(f2[0, 0, 0] - 2.0 / 255.0) < 1e-4
    assert abs(f3[0, 0, 0] - 3.0 / 255.0) < 1e-4

    # 3. Test MainWindow sequence drop and frame resolution
    win = MainWindow()
    qtbot.addWidget(win)

    win._on_comp_qc_source_dropped(first_file)
    assert win._reader_b is not None
    assert isinstance(win._reader_b, DiskSequenceReader)
    assert "plate.####.png [1001-1005]" in win.comp_qc_dock.panel.drop_source.lbl_text.text()

    # Test timeline mapping when timeline is at frame 1..5 but sequence is 1001..1005
    win.clock.set_range(1, 5)
    assert win._resolve_qc_frame(win._reader_b, 1) == 1001
    assert win._resolve_qc_frame(win._reader_b, 3) == 1003
    assert win._resolve_qc_frame(win._reader_b, 5) == 1005

    # Test matte sequence drop
    win._on_comp_qc_matte_dropped(first_file)
    assert win._reader_matte is not None
    assert isinstance(win._reader_matte, DiskSequenceReader)
    assert "plate.####.png [1001-1005]" in win.comp_qc_dock.panel.drop_matte.lbl_text.text()
    assert win._resolve_qc_frame(win._reader_matte, 2) == 1002

    win.close()


def test_compare_plates_split_qc_processing():
    """Verify that when Compare Plates is active, toggle checks (Grain, Highpass, Blacks, Negatives, NAN/inf, HSL)
    replicate behavior on both Left (Comp) and Right (Source Plate), while Difference stays on Left only."""
    frag_src = build_fragment_shader()

    # 1. Coordinate normalization and split check
    assert "bool isRightPlate = (uQcComparePlates && uHasTextureB && tc.x >= 0.5);" in frag_src
    assert "sCoord = isRightPlate ? vec2((tc.x - 0.5) * 2.0, tc.y) : vec2(tc.x * 2.0, tc.y);" in frag_src

    # 2. Left side Comp vs Right side clean Plate sampling
    assert "if (isRightPlate) {" in frag_src
    assert "vec4 cB = texture(uTextureB, sCoord);" in frag_src
    assert "vec4 cA = sample_layer_a(sCoord);" in frag_src

    # 3. High-Pass and Grain Check replicate on both Left Comp and Right Plate
    assert "if (uQcMode == 3)" in frag_src
    assert "if (uQcMode == 7)" in frag_src
    assert "clamp(sCoord + vec2(hpOff.x, 0.0), vec2(0.0), vec2(1.0))" in frag_src
    assert "clamp(sCoord + vec2(gOff.x, 0.0), vec2(0.0), vec2(1.0))" in frag_src

    # 4. Difference mode red overlay applied on Left side only (!isRightPlate)
    assert "if (!isRightPlate && uQcMode == 8 && uHasTextureB)" in frag_src
    assert "float diffAmt = length(linearRgb - linB);" in frag_src

    # 5. Diagnostic grading sliders applied to both sides; Overlay Matte gated on Left side only
    assert "linearRgb = linearRgb * uQcGain;" in frag_src
    assert "if (!isRightPlate) {" in frag_src
    assert "if (uHasTextureMatte && uQcOverlayMatte)" in frag_src

    # 6. Post-transform diagnostic checks apply to both sides
    assert "if (uQcMode == 1)" in frag_src
    assert "if (uQcMode == 2)" in frag_src
    assert "vec4 rawSample = isRightPlate ? texture(uTextureB, sCoord) : texture(uTextureA, sCoord);" in frag_src
    assert "if (uQcMode == 6)" in frag_src
    assert "if (uQcHslMode > 0)" in frag_src


def test_softclip_knee_math_and_continuity():
    """Verify hyperbolic tangent (tanh) softclip mathematical properties, asymptote, and continuity."""
    import numpy as np
    from openreview.packages.builtin.comp_qc.qc_state import apply_soft_clip

    # 1. Test linear zone preservation (x <= knee_start must be 100% untouched)
    knee = 0.7
    linear_vals = np.array([0.0, 0.1, 0.35, 0.5, 0.7], dtype=np.float32)
    res_linear = apply_soft_clip(linear_vals, knee_start=knee)
    np.testing.assert_allclose(res_linear, linear_vals, rtol=1e-6, atol=1e-6)

    # 2. Test compression zone (x > knee_start must be compressed and < 1.0)
    high_vals = np.array([0.75, 1.0, 1.5, 2.5, 5.0, 10.0, 100.0], dtype=np.float32)
    res_high = apply_soft_clip(high_vals, knee_start=knee)

    # Monotonically increasing across dynamic range, capped at 1.0
    assert np.all(np.diff(res_high) >= 0)
    assert res_high[0] < res_high[1] < res_high[2] < res_high[3] <= 1.0
    # Strictly compressed: res_high <= high_vals
    assert np.all(res_high <= high_vals)
    # Strictly bounded by 1.0
    assert np.all(res_high <= 1.0)
    # Asymptote check for ultra-bright highlight (e.g. 100.0 approaches 1.0)
    assert abs(res_high[-1] - 1.0) < 1e-4

    # 3. Test C1 continuity at knee boundary
    eps = 1e-4
    at_knee = float(apply_soft_clip(np.array([knee], dtype=np.float32), knee_start=knee)[0])
    just_above = float(apply_soft_clip(np.array([knee + eps], dtype=np.float32), knee_start=knee)[0])
    num_deriv = (just_above - at_knee) / eps
    assert abs(at_knee - knee) < 1e-6, "Value at knee must equal knee"
    assert abs(num_deriv - 1.0) < 5e-3, "First derivative at knee must equal 1.0 for smooth transition"

    # 4. Test knee_start >= 0.999 is transparent pass-through (no-op)
    img = np.array([0.5, 1.2, 3.0], dtype=np.float32)
    res_noop = apply_soft_clip(img, knee_start=1.0)
    np.testing.assert_array_equal(res_noop, img)

    # 5. Verify shader contains tanh softclip formula
    frag_src = build_fragment_shader()
    assert "uQcSoftclip < 0.999" in frag_src
    assert "float knee = max(0.001, uQcSoftclip);" in frag_src
    assert "float headroom = 1.0 - knee;" in frag_src
    assert "linearRgb[i] = knee + headroom * tanh((linearRgb[i] - knee) / headroom);" in frag_src


def test_nuke_expression_node_features(qapp):
    """
    Verify complete Foundry Nuke Expression node features:
    - Advanced variables (r, g, b, a, red, green, blue, alpha, cx, cy, x, y, w, h, f, frame)
    - Math functions (clamp, min, max, abs, pow, sqrt, sin, cos, smoothstep, mix, lerp, step)
    - Ternary conditional expressions (cond ? t : f)
    - Syntax error detection & non-crashing safe fallbacks
    - Interactive input controls, presets dropdown menu, reset buttons, and channel bypass toggles
    """
    from openreview.color.shader_builder import validate_and_compile_expression

    # 1. Advanced variable & math expression compilation
    expr1, err1 = validate_and_compile_expression("a > 0.5 ? 1.0 : 0.0", "a")
    assert err1 is None
    assert "a > 0.5 ? 1.0 : 0.0" in expr1 or "mRaw.a" in expr1

    expr2, err2 = validate_and_compile_expression("smoothstep(0.2, 0.8, cx)", "a")
    assert err2 is None
    assert "smoothstep" in expr2 and "cx" in expr2

    expr3, err3 = validate_and_compile_expression("lerp(mRaw.r, mRaw.g, cx)", "r")
    assert err3 is None
    assert "mix" in expr3  # lerp auto-mapped to GLSL mix

    expr4, err4 = validate_and_compile_expression("sin(f * 0.1)", "b")
    assert err4 is None
    assert "sin" in expr4 and "f" in expr4

    # 2. Syntax error validation without shader crash
    _, err_paren = validate_and_compile_expression("1 - a)", "a")
    assert err_paren is not None and "closing parenthesis" in err_paren.lower()

    _, err_unclosed = validate_and_compile_expression("(1 - a", "a")
    assert err_unclosed is not None and "unclosed parenthesis" in err_unclosed.lower()

    _, err_ident = validate_and_compile_expression("custom_unknown_var + 1", "r")
    assert err_ident is not None and "unknown identifier" in err_ident.lower()

    _, err_ternary = validate_and_compile_expression("a > 0.5 ? 1.0", "a")
    assert err_ternary is not None and "ternary" in err_ternary.lower()

    # 3. Interactive UI Controls on XtraQCWidget
    state = CompQCState()
    widget = XtraQCWidget(state)

    # Per-channel checkboxes removed from UI (hidden stubs for backward-compatibility)
    assert widget.chk_red.isHidden() is True
    assert widget.chk_green.isHidden() is True
    assert widget.chk_blue.isHidden() is True
    assert widget.chk_alpha.isHidden() is True

    # Primary color preset swatches & custom picker
    widget.btn_swatch_red.click()
    assert state.overlay_color.red() > 200 and state.overlay_color.green() < 50
    widget.btn_swatch_green.click()
    assert state.overlay_color.green() > 200 and state.overlay_color.red() < 50
    widget.btn_swatch_blue.click()
    assert state.overlay_color.blue() > 200 and state.overlay_color.red() < 50

    # Live typing with valid expression (debounced timer or Return/Enter commit)
    widget.txt_expr_a.setText("1 - a")
    assert widget._expr_debounce_timer.isActive() is True
    widget.txt_expr_a.returnPressed.emit()
    assert widget._expr_debounce_timer.isActive() is False
    assert state.expr_alpha == "1 - a"
    assert "Compiled GLSL" in widget.txt_expr_a.toolTip()

    # Reset single channel expression button
    widget.btn_rst_a.click()
    assert state.expr_alpha == ""
    assert widget.txt_expr_a.text() == ""

    # Live typing with invalid syntax shows error style & tooltip, keeps last valid in state
    widget.txt_expr_a.setText("1 - a)")
    widget.txt_expr_a.returnPressed.emit()
    assert "Syntax Error" in widget.txt_expr_a.toolTip()
    # State not corrupted by broken syntax
    assert state.expr_alpha == ""

    # 4. Presets dropdown menu execution
    menu = widget.btn_expr_presets.menu()
    assert menu is not None
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}

    # Invert Alpha preset
    assert "Invert Alpha (1 - a)" in actions
    actions["Invert Alpha (1 - a)"].trigger()
    assert state.expr_alpha == "1 - a"
    assert widget.txt_expr_a.text() == "1 - a"

    # Luma to Alpha preset
    assert "Luma to Alpha (0.2126*r + 0.7152*g + 0.0722*b)" in actions
    actions["Luma to Alpha (0.2126*r + 0.7152*g + 0.0722*b)"].trigger()
    assert "0.2126" in state.expr_alpha

    # Reset to Default preset
    assert "Reset to Default (r, g, b, a)" in actions
    actions["Reset to Default (r, g, b, a)"].trigger()
    assert state.expr_red == ""
    assert state.expr_green == ""
    assert state.expr_blue == ""
    assert state.expr_alpha == ""

    # Debounce timer auto-commit on typing pause (without Enter key)
    widget.txt_expr_r.setText("1.0 - r")
    assert widget._expr_debounce_timer.isActive() is True
    assert state.expr_red == ""  # Untouched during active typing
    widget._expr_debounce_timer.timeout.emit()
    assert state.expr_red == "1.0 - r"
    assert "Compiled GLSL" in widget.txt_expr_r.toolTip()


def test_default_cycle_stacking_with_qc_source_plate(qtbot, tmp_path):
    """Verify default cycle stacking (Z / Shift+Z) toggles strictly between active viewport media and QC Source Plate."""
    from PIL import Image
    from openreview.ui.main_window import MainWindow
    from openreview.models.session_graph import ViewType

    win = MainWindow()
    qtbot.addWidget(win)

    # Create dummy primary media and QC plate
    media_path = str(tmp_path / "primary_shot.png")
    Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(media_path)
    plate_path = str(tmp_path / "qc_plate.png")
    Image.new("RGBA", (64, 64), (100, 200, 255, 255)).save(plate_path)

    primary_item = win.session_graph.add_source_from_path(media_path)
    win.session_graph.set_active_view(ViewType.SOURCE, primary_item.id)
    assert win.session_graph.active_view_id == primary_item.id

    # Load QC plate
    win._on_comp_qc_source_dropped(plate_path)
    qc_sid = win.comp_qc_state.source_item_id
    assert qc_sid is not None

    # Set timeline range and seek to frame 42
    win.clock.set_range(1, 100)
    win.clock.set_frame(42)
    assert win.clock.current_frame == 42

    # Default cycle forward (Z) switches to QC Source Plate while strictly preserving playhead frame 42
    win._on_stack_cycle_forward()
    assert win.session_graph.active_view_id == qc_sid
    assert win.clock.current_frame == 42, "Cycle stacking must preserve playhead frame, never fall back to frame 1"

    # Cycle forward again switches back to primary media while strictly preserving frame 42
    win._on_stack_cycle_forward()
    assert win.session_graph.active_view_id == primary_item.id
    assert win.clock.current_frame == 42

    # Seek to frame 75 and cycle backward (Shift+Z)
    win.clock.set_frame(75)
    win._on_stack_cycle_backward()
    assert win.session_graph.active_view_id == qc_sid
    assert win.clock.current_frame == 75

    # Cycle backward again switches back to primary media while strictly preserving frame 75
    win._on_stack_cycle_backward()
    assert win.session_graph.active_view_id == primary_item.id
    assert win.clock.current_frame == 75

    win.close()


def test_window_menu_excludes_comp_qc_toolset(qtbot):
    """Verify Comp QC Toolset menu item is removed from Window menu."""
    from PySide6.QtWidgets import QMenu
    from openreview.ui.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)

    win_menu = next((m for m in win.menuBar().findChildren(QMenu) if "Window" in m.title()), None)
    assert win_menu is not None
    action_texts = [a.text() for a in win_menu.actions()]
    assert "Comp QC Toolset (Q)" not in action_texts

    win.close()


def test_overlay_matte_premult_linear_over(qtbot):
    """Verify linear Over compositing and 'Matte is Premultiplied' toggle in shader and widget."""
    from openreview.packages.builtin.comp_qc.qc_state import CompQCState
    from openreview.packages.builtin.comp_qc.hud_comp_qc import XtraQCWidget
    from openreview.color.shader_builder import build_fragment_shader

    state = CompQCState()
    widget = XtraQCWidget(state)
    qtbot.addWidget(widget)

    # 1. UI Checkbox exists, defaults to True, toggling updates state
    assert hasattr(widget, "chk_matte_premult")
    assert widget.chk_matte_premult.isChecked() is True
    assert state.matte_is_premult is True

    widget.chk_matte_premult.setChecked(False)
    assert state.matte_is_premult is False

    widget.chk_matte_premult.setChecked(True)
    assert state.matte_is_premult is True

    # 2. Fragment shader contains uQcMatteIsPremult and linear Over composite logic
    src = build_fragment_shader()
    assert "uniform bool uQcMatteIsPremult;" in src
    assert "if (uQcMatteIsPremult)" in src
    assert "compLinear = linMatte + linearRgb * (1.0 - mA);" in src
    assert "compLinear = linMatte * mA + linearRgb * (1.0 - mA);" in src


def test_mix_overlay_reset_button_and_ctrl_click(qtbot):
    """Verify reset button resets Mix Overlay to 1.0 and slider resets on Ctrl+Click."""
    from openreview.packages.builtin.comp_qc.qc_state import CompQCState
    from openreview.packages.builtin.comp_qc.hud_comp_qc import XtraQCWidget
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF

    state = CompQCState()
    widget = XtraQCWidget(state)
    qtbot.addWidget(widget)

    # Initial state is 1.0
    assert widget.slider_mix.value() == 100
    assert widget.spin_mix.value() == 1.0
    assert state.mix_overlay == 1.0

    # Modify to 0.35
    widget.spin_mix.setValue(0.35)
    assert abs(state.mix_overlay - 0.35) < 0.01
    assert widget.slider_mix.value() == 35

    # Click reset button
    assert hasattr(widget, "btn_rst_mix")
    widget.btn_rst_mix.click()
    assert abs(state.mix_overlay - 1.0) < 0.001
    assert widget.slider_mix.value() == 100
    assert abs(widget.spin_mix.value() - 1.0) < 0.001

    # Modify again to 0.2
    widget.spin_mix.setValue(0.2)
    assert abs(state.mix_overlay - 0.2) < 0.01

    # Simulate Ctrl+Click on slider
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    widget.slider_mix.mousePressEvent(press_event)
    assert abs(state.mix_overlay - 1.0) < 0.001
    assert widget.slider_mix.value() == 100
    assert abs(widget.spin_mix.value() - 1.0) < 0.001


def test_hue_rotation_slider_and_shader(qtbot):
    """Verify Hue Rotation slider in Color correction, state synchronization, and shader generation."""
    from openreview.packages.builtin.comp_qc.qc_state import CompQCState
    from openreview.packages.builtin.comp_qc.hud_comp_qc import XtraQCWidget
    from openreview.color.shader_builder import build_fragment_shader

    state = CompQCState()
    assert state.qc_hue_rotation == 0.0

    # Test clamping
    state.qc_hue_rotation = 200.0
    assert state.qc_hue_rotation == 180.0
    state.qc_hue_rotation = -250.0
    assert state.qc_hue_rotation == -180.0
    state.qc_hue_rotation = 45.0
    assert state.qc_hue_rotation == 45.0

    # Reset
    state.reset_defaults()
    assert state.qc_hue_rotation == 0.0

    # UI Widget verification
    widget = XtraQCWidget(state)
    qtbot.addWidget(widget)

    assert hasattr(widget, "slider_hue")
    assert widget.slider_hue.lbl_name.text() == "Hue Rotation"
    assert widget.slider_hue.value() == 0.0

    # Change via UI spinbox
    widget.slider_hue.spin.setValue(90.0)
    assert abs(state.qc_hue_rotation - 90.0) < 0.1

    # Reset button on slider row
    widget.slider_hue.btn_reset.click()
    assert abs(state.qc_hue_rotation - 0.0) < 0.1
    assert abs(widget.slider_hue.value() - 0.0) < 0.1

    # Shader verification
    frag_src = build_fragment_shader()
    assert "uniform float uQcHueRotation;" in frag_src
    assert "if (abs(uQcHueRotation) > 0.01)" in frag_src
    assert "hsv.x = fract(hsv.x + uQcHueRotation / 360.0);" in frag_src


def test_xtra_qc_disabled_by_default_and_tabbed_cycling(qtbot):
    """Verify xtra-qc-Utils is disabled by default, ignores Q shortcut, and supports tabbed dock cycling."""
    from openreview.packages.package_manager import PackageManager
    from openreview.ui.main_window import MainWindow
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import Qt, QEvent

    # 1. Package manager check
    pkg_mgr = PackageManager.instance()
    pkg_mgr.discover_packages()
    assert pkg_mgr.is_plugin_enabled("xtra-qc-Utils") is False

    win = MainWindow()
    qtbot.addWidget(win)

    # comp_qc_dock should be hidden
    assert win.comp_qc_dock.isHidden() is True

    # Pressing Q should do nothing silently when plugin is disabled
    press_q = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(press_q)
    assert win.comp_qc_dock.isHidden() is True

    # _on_toggle_comp_qc should do nothing silently
    win._on_toggle_comp_qc()
    assert win.comp_qc_dock.isHidden() is True

    # 2. Test enabling xtra-qc-Utils
    try:
        pkg_mgr.set_package_enabled("xtra-qc-Utils", True)
        assert pkg_mgr.is_plugin_enabled("xtra-qc-Utils") is True

        # Now toggling or pressing Q should work
        win._on_toggle_comp_qc()
        assert win.comp_qc_dock.isHidden() is False

        # Show file browser as well
        win.file_browser_dock.show()
        assert win.file_browser_dock.isHidden() is False

        # Both right docks are tabified and share RightDockWidgetArea
        assert win.dockWidgetArea(win.comp_qc_dock) == Qt.DockWidgetArea.RightDockWidgetArea
        assert win.dockWidgetArea(win.file_browser_dock) == Qt.DockWidgetArea.RightDockWidgetArea

        # Cycle tabs forward: comp_qc_dock -> file_browser_dock
        win.comp_qc_dock.raise_()
        next_d = win.cycle_dock_tab(win.comp_qc_dock, forward=True)
        assert next_d == win.file_browser_dock

        # Cycle tabs backward: file_browser_dock -> comp_qc_dock
        prev_d = win.cycle_dock_tab(win.file_browser_dock, forward=False)
        assert prev_d == win.comp_qc_dock

        # Verify TabbedDockTitleBar buttons on title bar
        tb = win.comp_qc_dock.titleBarWidget()
        assert tb is not None
        assert hasattr(tb, "btn_prev")
        assert hasattr(tb, "btn_next")
        assert hasattr(tb, "lbl_title")

        # Test clicking title bar next button
        tb.btn_next.click()

        # Test clicking title bar prev button
        tb_fb = win.file_browser_dock.titleBarWidget()
        assert tb_fb is not None
        tb_fb.btn_prev.click()

        win.close()
    finally:
        # Reset back to disabled by default
        pkg_mgr.set_package_enabled("xtra-qc-Utils", False)
        assert pkg_mgr.is_plugin_enabled("xtra-qc-Utils") is False










