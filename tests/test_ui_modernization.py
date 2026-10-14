"""
Comprehensive validation test suite for OpenReview UI Modernization.
Tests all features, layout optimizations, HUD widgets, hotkeys, and vector icons.
"""
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QInputDialog, QSplitter

from openreview.ui.main_window import MainWindow
from openreview.widgets.top_bar import NukeSlider
from openreview.widgets.viewport import ViewportCanvas
from openreview.widgets.timeline import MagnifiedTimelinePopup
from openreview.models.session_graph import StackView, SourceItem
from openreview.core.cache import CacheMode
from openreview.resources import get_app_icon, get_app_logo_path


def test_shotgun_module_completely_removed():
    """Ensure Shotgun module has been completely purged from integrations and ui."""
    with pytest.raises(ModuleNotFoundError):
        import openreview.integrations.shotgun  # type: ignore

    with pytest.raises(ModuleNotFoundError):
        import openreview.ui.shotgun_dialog  # type: ignore


def test_app_and_window_vector_icons(qtbot):
    """Verify SVG icon loading for window icon and about logo."""
    icon = get_app_icon()
    assert not icon.isNull()
    assert len(icon.availableSizes()) > 0

    logo_path = get_app_logo_path()
    assert logo_path.exists()
    assert logo_path.suffix == ".svg"

    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.windowIcon().isNull()


def test_about_dialog_content(qtbot, monkeypatch):
    """Verify About dialog uses openreview-logo and has no 3DEqualizer reference."""
    window = MainWindow()
    qtbot.addWidget(window)

    executed_dialog = {}

    from PySide6.QtWidgets import QDialog, QLabel

    def mock_exec(self):
        executed_dialog["title"] = self.windowTitle()
        labels = self.findChildren(QLabel)
        executed_dialog["text"] = " ".join(lbl.text() for lbl in labels)
        executed_dialog["has_pixmap"] = any(not lbl.pixmap().isNull() for lbl in labels if lbl.pixmap())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", mock_exec)
    window._show_about()

    assert executed_dialog["title"] == "About OpenReview"
    assert "3DEqualizer" not in executed_dialog["text"]
    assert "OpenReview" in executed_dialog["text"]
    assert executed_dialog["has_pixmap"] is True


def test_window_menu_modifications(qtbot):
    """Verify Window menu removes duplicate OCIO/Shotgun and includes EXR/Stereo HUDs."""
    window = MainWindow()
    qtbot.addWidget(window)

    menu_bar = window.menuBar()
    win_menu = None
    for action in menu_bar.actions():
        if "Window" in action.text():
            win_menu = action.menu()
            break
    assert win_menu is not None

    action_texts = [a.text() for a in win_menu.actions()]

    # Duplicate OCIO and Shotgun removed
    assert not any("OpenColorIO Configuration" in t for t in action_texts)
    assert not any("Shotgun" in t for t in action_texts)

    # Removed from Window menu as requested
    assert not any("Annotation & Notes Manager" in t for t in action_texts)
    assert not any("Remote Dailies Sync" in t for t in action_texts)
    assert not any("Media Stacking" in t for t in action_texts)
    assert not any("EXR Multilayer Pass Inspector" in t for t in action_texts)
    assert not any("Stereoscopic 3D Controls" in t for t in action_texts)
    assert not any("A/B Wipe Comparison" in t for t in action_texts)
    assert not any("Color Inspector" in t for t in action_texts)
    assert not any("Live RGB Histogram" in t for t in action_texts)
    assert not any("Source Media Details" in t for t in action_texts)
    assert not any("Interactive Color Adjustments" in t for t in action_texts)

    # Session Manager shortcut is backtick `
    assert any("Sources & Session Manager (`)" in t for t in action_texts)

    # Verify moved items in their new parent menus
    # Review: A/B Wipe Comparison, Live RGB Histogram
    review_menu = next((a.menu() for a in menu_bar.actions() if "Review" in a.text()), None)
    assert review_menu is not None
    review_texts = [a.text() for a in review_menu.actions()]
    assert any("A/B Wipe Comparison" in t for t in review_texts)
    assert any("Live RGB Histogram" in t for t in review_texts)

    # Color: Color Inspector
    color_menu = next((a.menu() for a in menu_bar.actions() if "Color" in a.text()), None)
    assert color_menu is not None
    color_texts = [a.text() for a in color_menu.actions()]
    assert any("Color Inspector" in t for t in color_texts)

    # View: Source Media Details
    view_menu = next((a.menu() for a in menu_bar.actions() if "View" in a.text()), None)
    assert view_menu is not None
    view_texts = [a.text() for a in view_menu.actions()]
    assert any("Source Media Details" in t for t in view_texts)

    # Layered input menu
    assert hasattr(window, "layered_input_menu")
    assert window.layered_input_menu.title() == "&Layered input"
    # Hidden initially since no media loaded
    assert not window.layered_input_menu.menuAction().isVisible()
    layered_texts = [a.text() for a in window.layered_input_menu.actions()]
    assert any("EXR Multilayer Pass Inspector" in t for t in layered_texts)
    assert any("Stereoscopic 3D Controls" in t for t in layered_texts)


def test_top_bar_channel_popup_and_hidden_combos(qtbot):
    """Verify Channel button is a popup button and layer/stereo combos are hidden."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    top_bar = window.top_bar

    # Channel button exists and has popup menu trigger
    assert hasattr(top_bar, "btn_channel")
    assert not top_bar.btn_channel.isHidden()
    assert top_bar.btn_channel.text() == "RGB"

    # Layer and Stereo combos are hidden from top bar layout
    assert top_bar.layer_combo.isHidden()
    assert top_bar.stereo_combo.isHidden()

    # Input and view transforms are preserved and visible
    assert not top_bar.input_combo.isHidden()
    assert not top_bar.view_combo.isHidden()


def test_ctrl_click_resets_sliders(qtbot):
    """Verify Ctrl+Click on NukeSlider anywhere resets value to default."""
    slider = NukeSlider(default_val=500, min_v=0, max_v=1000)
    slider.resize(160, 34)
    slider.setValue(800)
    assert slider.value() == 800

    # Ctrl+Click at x=20
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(20, 15),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    slider.mousePressEvent(event)
    assert slider.value() == 500


def test_timeline_bottom_row_layout_and_magnifier_widget(qtbot):
    """Verify timeline bottom row ordering, missing Goto label, and Shift+T magnifier popup."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    tl = window.timeline

    # Magnifier popup toggle
    assert hasattr(tl, "magnified_popup")
    assert hasattr(tl, "btn_magnifier")
    assert not tl.btn_magnifier.isHidden()

    assert tl.magnified_popup is None or not tl.magnified_popup.isVisible()
    tl.toggle_magnifier_widget()
    assert tl.magnified_popup is not None and tl.magnified_popup.isVisible()
    assert tl.magnified_popup.parent() == window.viewport
    assert tl.magnified_popup.width() == 400
    assert tl.magnified_popup.height() == 32
    assert tl.magnified_popup.x() == (window.viewport.width() - 400) // 2
    assert tl.magnified_popup.y() == window.viewport.height() - 32 - 8
    tl.toggle_magnifier_widget()
    assert not tl.magnified_popup.isVisible()

    # Reordered bottom row items
    assert hasattr(tl, "goto_frame_box")
    assert hasattr(tl, "btn_clear_in_out")
    assert hasattr(tl, "btn_timecode")


def test_sources_panel_splitter_and_svg_icons(qtbot):
    """Verify Sources panel uses QSplitter and has SVG icons."""
    window = MainWindow()
    qtbot.addWidget(window)
    sp = window.sources_panel

    # Check splitter dividing tree and tabs
    assert hasattr(sp, "splitter")
    assert isinstance(sp.splitter, QSplitter)
    assert sp.splitter.orientation() == Qt.Orientation.Vertical

    # Check SVG icons on action buttons
    assert not sp.btn_expand_all.icon().isNull()
    assert not sp.btn_collapse_all.icon().isNull()
    assert not sp.btn_new_folder.icon().isNull()
    assert not sp.btn_delete.icon().isNull()


def test_hotkeys_gain_gamma_saturation_invert(qtbot):
    """Test hotkeys: +/- (gain), Ctrl++/- (gamma), Shift++/- (saturation), Shift+I (invert), Shift+Home (reset)."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Gain: + / -
    g0 = window.top_bar.gain_spin.value()
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.NoModifier, "="))
    assert round(window.top_bar.gain_spin.value(), 2) == round(g0 + 0.10, 2)
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, "-"))
    assert round(window.top_bar.gain_spin.value(), 2) == round(g0, 2)

    # Gamma: Shift++ / Shift+-
    gam0 = window.top_bar.gam_spin.value()
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.ShiftModifier, "+"))
    assert round(window.top_bar.gam_spin.value(), 2) == round(gam0 + 0.05, 2)
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ShiftModifier, "-"))
    assert round(window.top_bar.gam_spin.value(), 2) == round(gam0, 2)

    # Saturation: Ctrl+Shift++ / Ctrl+Shift+-
    sat0 = window.top_bar.sat_spin.value()
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, "+"))
    assert round(window.top_bar.sat_spin.value(), 2) == round(sat0 + 0.05, 2)
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, "-"))
    assert round(window.top_bar.sat_spin.value(), 2) == round(sat0, 2)

    # Invert color toggle: Shift+I
    assert window.invert_colors_act.isChecked() is False
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ShiftModifier, "I"))
    assert window.invert_colors_act.isChecked() is True
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ShiftModifier, "I"))
    assert window.invert_colors_act.isChecked() is False

    # Shift+Home: Reset all color
    window.top_bar.set_gain(1.8)
    window.top_bar.set_gamma(1.5)
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ShiftModifier, ""))
    assert window.top_bar.gain_spin.value() == 1.0
    assert window.top_bar.gam_spin.value() == 1.0
    assert window.top_bar.sat_spin.value() == 1.0


def test_clear_in_out_backslash_shortcut(qtbot):
    """Test hotkey backslash clears timeline in/out."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.clock.set_in_mark(1020)
    window.clock.set_out_mark(1080)
    assert window.clock.in_frame == 1020
    assert window.clock.out_frame == 1080

    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Backslash, Qt.KeyboardModifier.NoModifier, "\\"))
    assert window.clock.in_frame == window.clock.start_frame
    assert window.clock.out_frame == window.clock.end_frame


def test_ctrl_g_goto_frame_modal_dialog(qtbot, monkeypatch):
    """Test Ctrl+G modal dialog and range clamping."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.clock.set_range(1001, 1200)

    # Test jumping within range
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (1150, True))
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier, "g"))
    assert window.clock.current_frame == 1150

    # Test clamping beyond last frame
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (9999, True))
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier, "g"))
    assert window.clock.current_frame == 1200

    # Test clamping before first frame
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (500, True))
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier, "g"))
    assert window.clock.current_frame == 1001


def test_inspect_top_level_source_in_stack(qtbot):
    """Test hotkey 'I' inspects top-level source of active StackView."""
    window = MainWindow()
    qtbot.addWidget(window)

    src1 = SourceItem(id="src_1", name="Plate", path="plate.exr", media_type="sequence")
    src2 = SourceItem(id="src_2", name="CG", path="cg.exr", media_type="sequence")
    stack = StackView(id="stack_1", name="CompStack", source_ids=["src_1", "src_2"])

    window.session_graph.sources[src1.id] = src1
    window.session_graph.sources[src2.id] = src2
    window.session_graph.stacks[stack.id] = stack
    from openreview.models.session_graph import ViewType
    window.session_graph.set_active_view(ViewType.STACK, "stack_1")

    info = window._get_current_source_info()
    assert info["file_path"] == "plate.exr"


def test_viewport_missing_frame_and_reload(qtbot):
    """Test missing frame detection in viewport and frame reload hotkey."""
    window = MainWindow()
    qtbot.addWidget(window)
    vp = window.viewport

    # Initial state
    assert vp.has_active_media is False
    assert vp.is_bad_frame is False

    # Setting valid frame sets active media
    import numpy as np
    valid_data = np.zeros((100, 100, 4), dtype=np.uint8)
    vp.set_primary_frame(1001, valid_data)
    assert vp.has_active_media is True
    assert vp.is_bad_frame is False

    # Setting None frame when media was active triggers bad/missing frame
    vp.set_primary_frame(1002, None)
    assert vp.has_active_media is True
    assert vp.is_bad_frame is True

    # Test reload methods
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier, "r"))
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, "R"))


def test_ctrl_middle_mouse_zoom(qtbot):
    """Test Ctrl+MiddleMouse drag zoom in ViewportCanvas."""
    vp = ViewportCanvas()
    vp.resize(400, 400)
    z0 = vp.zoom

    # Press Ctrl+MiddleMouse
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(100, 100),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    vp.mousePressEvent(press_ev)
    assert vp._is_zooming_drag is True

    # Move mouse up and right (dx=50, dy=-50) -> zoom in
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPoint(150, 50),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    vp.mouseMoveEvent(move_ev)
    assert vp.zoom > z0

    # Release mouse
    rel_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(150, 50),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mouseReleaseEvent(rel_ev)
    assert vp._is_zooming_drag is False


def test_delayed_caching_and_fullscreen_right_click_menu(qtbot):
    """Verify delayed prefetch timer on source drop and fullscreen right-click context menu handling."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # 1. Delayed prefetch scheduling
    assert hasattr(window, "_delayed_cache_timer")
    window.cache.set_mode(CacheMode.PLAY_AHEAD)
    window._schedule_delayed_prefetch(500)
    assert window._delayed_cache_timer.isActive()

    # Scrubber or playback cancels delay timer immediately
    window._on_viewport_scrub(1)
    assert not window._delayed_cache_timer.isActive()

    # 2. Right-click press and release on viewport
    vp = window.viewport
    vp.set_presentation_mode(True)
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(100, 100),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mousePressEvent(press_ev)
    assert press_ev.isAccepted()
    assert getattr(vp, "_right_press_pos", None) == QPoint(100, 100)

    # Context menu method handles presentation/fullscreen mode
    menu_called = []
    vp._show_context_menu = lambda pos: menu_called.append(pos)

    rel_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(100, 100),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vp.mouseReleaseEvent(rel_ev)
    assert rel_ev.isAccepted()
    assert len(menu_called) == 1


def test_coalesced_prefetch_and_scrub_responsiveness(qapp):
    """Verify background prefetch pacing, scrub pausing, and cache UI coalescing."""
    from openreview.ui.main_window import MainWindow
    from openreview.core.cache import CacheMode
    window = MainWindow()

    # 1. Paced thread pool: worker thread count is capped at 6 or half cores
    assert window.reader_engine.thread_pool.maxThreadCount() <= 6

    # 2. Scrub pauses background prefetch
    window.reader_engine.resume_prefetch()
    assert not window.reader_engine.is_paused

    window._on_viewport_scrub(1)
    assert window.reader_engine.is_paused
    assert window._scrub_settle_timer.isActive()

    # 3. Scrub settle resumes prefetch after pause
    window._on_scrub_settled()
    assert not window.reader_engine.is_paused

    # 4. Cache UI update coalescing
    update_count = [0]
    orig_on_cache_updated = window._on_cache_updated
    window._on_cache_updated = lambda: update_count.append(1)

    # Trigger burst of cache updates
    for _ in range(20):
        window._schedule_cache_ui_update()

    # The timer should be active and coalescing 20 bursts into 1 pending execution
    assert window._cache_ui_timer.isActive()
    assert len(update_count) == 1  # Not fired synchronously 20 times

    window._cache_ui_timer.timeout.emit()
    assert len(update_count) == 2  # Fired once upon timer expiry


def test_playback_on_uncached_area_decodes_without_missing_frame(qapp):
    """Verify that playing on an uncached area synchronously decodes rather than flashing MISSING FRAME."""
    from openreview.ui.main_window import MainWindow
    from openreview.core.cache import CacheMode
    from openreview.core.reader import SyntheticPatternReader
    window = MainWindow()

    # Enable cache, clear cache, and simulate playback state
    window.cache.set_mode(CacheMode.PLAY_AHEAD)
    window.cache.clear()
    window.reader = SyntheticPatternReader()
    window.clock.play()
    assert window.clock.is_playing

    # Change frame to 321 while playing on uncached area
    window._on_frame_changed(321)

    # Viewport must show the decoded frame, and NOT show missing frame error
    assert not window.viewport.is_bad_frame
    assert window.viewport._image_a is not None
    assert window.cache.has_frame(321)


def test_help_menu_documentation_actions(qtbot, monkeypatch):
    """Verify Help menu contains all HTML documentation actions and opens them."""
    from openreview.ui.main_window import MainWindow
    from PySide6.QtGui import QDesktopServices
    window = MainWindow()
    qtbot.addWidget(window)

    mb = window.menuBar()
    help_menu = None
    for action in mb.actions():
        if "Help" in action.text():
            help_menu = action.menu()
            break
    assert help_menu is not None

    action_texts = [a.text() for a in help_menu.actions()]
    assert "Application Documentation" in action_texts
    assert "Features & Shortcuts Guide" in action_texts
    assert "Use Cases & Workflows" in action_texts
    assert "Python SDK Documentation" in action_texts
    assert "Open Documentation Folder..." in action_texts

    opened_urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url.toLocalFile()))

    window._open_html_doc("index.html")
    assert len(opened_urls) == 1
    assert opened_urls[0].endswith("index.html")

    window._open_docs_folder()
    assert len(opened_urls) == 2
    assert "html" in opened_urls[1]
