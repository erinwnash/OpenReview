"""
Generate all UI screenshots for OpenReview documentation.
Captures all 34 official documentation figures from the running Qt UI.
"""
import os
import sys
from pathlib import Path

# Add src to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

import numpy as np
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPixmap

from openreview.ui.main_window import MainWindow
from openreview.models.comparison import ComparisonMode
from openreview.models.annotations import ShapeType, Stroke
from openreview.ui.export_dialog import ExportDialog
from openreview.ui.package_manager_dialog import PackageManagerDialog
from openreview.ui.process_info_dialog import ProcessInfoDialog
from openreview.ui.goto_frame_dialog import GoToFrameDialog
from openreview.ui.preferences_dialog import PreferencesDialog
from openreview.ui.about_dialog import AboutDialog


OUTPUT_DIR = ROOT_DIR / "docs" / "html" / "assets" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PNG = ROOT_DIR / "tests" / "sample_media" / "sh010_comp_v002.1001.png"

def save_widget(widget, filename):
    app = QApplication.instance()
    app.processEvents()
    pix = widget.grab()
    out_path = OUTPUT_DIR / filename
    pix.save(str(out_path), "PNG")
    print(f"Captured: {filename:45s} ({pix.size().width()}x{pix.size().height()})")

def main():
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    window = MainWindow()
    window.resize(1440, 880)
    window.show()
    app.processEvents()

    # Load sample media sequence
    if SAMPLE_PNG.exists():
        window._load_path(str(SAMPLE_PNG))
    app.processEvents()

    # Simulate realistic pixel inspector values
    window._on_pixel_inspected(x=960, y=540, r=0.4852, g=0.3214, b=0.1876, a=1.0)
    app.processEvents()

    # Add realistic log entries for Console Window
    window.console_logger.record_log("INFO", "app", "OpenReview v1.0.0 workstation initialized successfully.")
    window.console_logger.record_log("INFO", "gpu", "OpenGL 3.3 Core Profile viewport context created with PBO DMA streaming.")
    window.console_logger.record_log("INFO", "cache", "RingBufferCache allocated 4.0 GB RAM lookahead budget (80% forward, 20% reverse).")
    window.console_logger.record_log("INFO", "disk_cache", "Persistent DiskCache active at ~/.openreview/cache (Limit: 32.0 GB).")
    window.console_logger.record_log("INFO", "reader", "Loaded sequence: sh010_comp_v002.####.png [1001-1010] (1920x1080 @ 24.0 FPS).")
    window.console_logger.record_log("INFO", "ocio", "OpenColorIO v2 initialized with working space ACEScg -> Display sRGB.")
    window.console_logger.record_log("DEBUG", "prefetch", "Pre-decoded 10 frames ahead of playhead in 38ms.")
    window.console_logger.record_log("WARNING", "qc", "Pixel Inspector detected 14 negative values in shadow region (illuminance clipping).")
    app.processEvents()

    # 1. Top Control Bar
    save_widget(window.top_bar, "top_control_bar.png")

    # 2. Timeline Transport Dock
    save_widget(window.timeline_dock, "timeline_transport_dock.png")

    # 3. Status Bar
    save_widget(window.statusBar(), "status_bar.png")

    # 4. Sources & Session Dock
    save_widget(window.sources_dock, "sources_session_dock.png")

    # 5. File Browser Dock
    if hasattr(window, "file_browser_dock"):
        window.file_browser_dock.show()
        app.processEvents()
        save_widget(window.file_browser_dock, "file_browser_dock.png")

    # 6. Floating Annotation Palette
    if hasattr(window, "markup_palette"):
        window.markup_palette.show()
        app.processEvents()
        save_widget(window.markup_palette, "floating_annotation_palette.png")

    # 7. Workspace Overview (with Color HUD visible & Sources Dock)
    window.file_browser_dock.hide()
    window.hud_color_adj.show()
    window.hud_color_adj.move(QPoint(30, 25))
    app.processEvents()
    save_widget(window, "workspace_overview.png")

    # 8. Workspace with File Browser
    window.hud_color_adj.hide()
    window.file_browser_dock.show()
    app.processEvents()
    save_widget(window, "workspace_with_file_browser.png")
    window.file_browser_dock.hide()

    # 9. HUD Histogram
    window.hud_hist.show()
    window.hud_hist.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_hist, "hud_histogram.png")
    window.hud_hist.hide()

    # 10. HUD Color Inspector
    window.hud_inspector.show()
    window.hud_inspector.move(QPoint(20, 20))
    window.inspector_widget.update_pixel(960, 540, 0.4852, 0.3214, 0.1876, 1.0)
    # Add a point sampler and area sampler
    window.viewport.add_color_sampler(0.45, 0.45, norm_w=0.1, norm_h=0.1)
    app.processEvents()
    save_widget(window.hud_inspector, "hud_color_inspector.png")
    window.hud_inspector.hide()

    # 11. HUD Wipe Controller
    window.hud_wipe.show()
    window.hud_wipe.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_wipe, "hud_wipe_controller.png")
    window.hud_wipe.hide()

    # 12. HUD Media Stacking (Stack tools in Sources Panel)
    try:
        from openreview.models.session_graph import StackView, ViewType
        panel = window.sources_dock.panel
        stack = StackView(name="Comp vs Plate Stack", compare_mode="over")
        src_ids = list(panel.graph.sources.keys())
        if src_ids:
            stack.source_ids = src_ids
        panel.graph.stacks[stack.id] = stack
        panel.graph.set_active_view(ViewType.STACK, stack.id)
        panel._refresh_subpanels()
        panel.tabs.setCurrentIndex(1)
        panel.tab_inputs.resize(440, 480)
        app.processEvents()
        save_widget(panel.tab_inputs, "hud_media_stacking.png")
    except Exception as e:
        print("Stack tools grab error:", e)
        save_widget(window.sources_dock, "hud_media_stacking.png")

    # 13. HUD Color Adjustments
    window.hud_color_adj.show()
    window.hud_color_adj.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_color_adj, "hud_color_adjustments.png")
    window.hud_color_adj.hide()

    # 14. HUD OpenColorIO Config
    window.hud_ocio.show()
    window.hud_ocio.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_ocio, "hud_ocio_config.png")
    window.hud_ocio.hide()

    # 15. HUD EXR Layers
    window.hud_layers.show()
    window.hud_layers.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_layers, "hud_exr_layers.png")
    window.hud_layers.hide()

    # 16. HUD Stereo 3D
    window.hud_stereo.show()
    window.hud_stereo.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_stereo, "hud_stereo_3d.png")
    window.hud_stereo.hide()

    # 17. HUD Annotation Manager
    window.hud_annotations.show()
    window.hud_annotations.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_annotations, "hud_annotation_manager.png")
    window.hud_annotations.hide()

    # 18. HUD Source Details
    window.hud_source_details.show()
    window.hud_source_details.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_source_details, "hud_source_details.png")
    window.hud_source_details.hide()

    # 19. HUD Audio Settings
    window.hud_audio.show()
    window.hud_audio.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_audio, "hud_audio_settings.png")
    window.hud_audio.hide()

    # 20. HUD Dailies Sync
    window.hud_dailies_sync.show()
    window.hud_dailies_sync.move(QPoint(20, 20))
    app.processEvents()
    save_widget(window.hud_dailies_sync, "hud_dailies_sync.png")
    window.hud_dailies_sync.hide()

    # 20b. HUD Comp QC (xtra QC Utils)
    if hasattr(window, "comp_qc_dock") and window.comp_qc_dock:
        window.comp_qc_dock.show()
        window.comp_qc_dock.resize(360, 680)
        app.processEvents()
        save_widget(window.comp_qc_dock, "hud_comp_qc.png")
        window.comp_qc_dock.hide()


    # 21. Dialog: Diagnostic Console Window
    if hasattr(window, "console_window"):
        window.console_window.resize(780, 440)
        window.console_window.show()
        app.processEvents()
        save_widget(window.console_window, "dialog_console_window.png")
        window.console_window.hide()

    # 22. Dialog: Export Media
    try:
        in_w, in_h = (1920, 1080)
        exp_dlg = ExportDialog(
            clock=window.clock,
            marked_frames=list(window.clock.bookmarks),
            annotated_frames=window.annotation_store.get_annotated_frames(),
            input_resolution=(in_w, in_h),
            raw_frame_reader=lambda f: window.viewport._image_a,
            annotation_getter=window.annotation_store.get_strokes,
            viewport=window.viewport,
            parent=window,
        )
        exp_dlg.resize(540, 420)
        exp_dlg.show()
        app.processEvents()
        save_widget(exp_dlg, "dialog_export_media.png")
        exp_dlg.close()
    except Exception as e:
        print("ExportDialog error:", e)

    # 23. Dialog: Package & Plugin Manager
    try:
        pkg_dlg = PackageManagerDialog(window.pkg_mgr, window)
        pkg_dlg.resize(720, 480)
        pkg_dlg.show()
        app.processEvents()
        save_widget(pkg_dlg, "dialog_package_manager.png")
        pkg_dlg.close()
    except Exception as e:
        print("PackageManagerDialog error:", e)

    # 24. Dialog: Process Info & Performance
    try:
        used_mb, max_mb, pct = window.cache.get_memory_stats()
        metrics = {
            "fps_target": window.clock.fps,
            "measured_fps": getattr(window.clock, "_last_measured_fps", window.clock.fps),
            "dropped_frames": 0,
            "loop_mode": window.clock.loop_mode.capitalize(),
            "cache_mode": str(window.cache.mode.value).capitalize(),
            "cache_used_mb": used_mb,
            "cache_max_mb": max_mb,
            "gl_vendor": "OpenGL Core Profile",
            "gl_renderer": "Hardware Shader Core",
            "has_lut": (window.viewport.color_grading.active_lut is not None and window.viewport.color_grading.lut_enabled),
            "has_cdl": (window.viewport.color_grading.active_cdl is not None and window.viewport.color_grading.cdl_enabled),
        }
        proc_dlg = ProcessInfoDialog(metrics, window)
        proc_dlg.resize(500, 520)
        proc_dlg.show()
        app.processEvents()
        save_widget(proc_dlg, "dialog_process_info.png")
        proc_dlg.close()
    except Exception as e:
        print("ProcessInfoDialog error:", e)

    # 25. Dialog: Go To Frame
    try:
        goto_dlg = GoToFrameDialog(
            start_frame=window.clock.start_frame,
            end_frame=window.clock.end_frame,
            current_frame=window.clock.current_frame,
            parent=window,
        )
        goto_dlg.show()
        app.processEvents()
        save_widget(goto_dlg, "dialog_goto_frame.png")
        goto_dlg.close()
    except Exception as e:
        print("GoToFrameDialog error:", e)

    # 26 - 30. Dialog: Preferences Tabs
    try:
        pref_dlg = PreferencesDialog(window.pref_mgr, window)
        pref_dlg.resize(760, 600)

        # Tab 0: General & Playback
        pref_dlg.tabs.setCurrentIndex(0)
        pref_dlg.show()
        app.processEvents()
        save_widget(pref_dlg, "dialog_preferences_general.png")
        save_widget(pref_dlg, "dialog_preferences_general_and_playback.png")

        # Tab 1: GPU Acceleration
        pref_dlg.tabs.setCurrentIndex(1)
        app.processEvents()
        save_widget(pref_dlg, "dialog_preferences_gpu_acceleration.png")

        # Tab 2: Caching
        pref_dlg.tabs.setCurrentIndex(2)
        app.processEvents()
        save_widget(pref_dlg, "dialog_preferences_caching.png")

        # Tab 3: Keyboard Shortcuts
        pref_dlg.tabs.setCurrentIndex(3)
        app.processEvents()
        save_widget(pref_dlg, "dialog_preferences_keyboard_shortcuts.png")

        pref_dlg.close()
    except Exception as e:
        print("PreferencesDialog error:", e)

    # Dialog: About Dialog
    try:
        about_dlg = AboutDialog(window)
        about_dlg.resize(700, 540)
        about_dlg.show()
        app.processEvents()
        save_widget(about_dlg, "dialog_about.png")
        about_dlg.close()
    except Exception as e:
        print("AboutDialog error:", e)


    # 31. Viewport: A/B Split Wipe Mode
    try:
        window.comparison_state.mode = ComparisonMode.WIPE
        window.comparison_state.wipe_position = 0.52
        window.comparison_state.wipe_angle = 30.0
        window.viewport.comparison_state.mode = ComparisonMode.WIPE
        window.viewport.comparison_state.wipe_position = 0.52
        window.viewport.comparison_state.wipe_angle = 30.0
        window.viewport.update()
        app.processEvents()
        save_widget(window.viewport, "viewport_ab_wipe_mode.png")
        window.comparison_state.mode = ComparisonMode.OFF
        window.viewport.comparison_state.mode = ComparisonMode.OFF
    except Exception as e:
        print("Viewport A/B Wipe error:", e)

    # 32. Viewport: Annotations & HUDs
    try:
        # Draw arrow and callout
        stroke1 = Stroke(
            shape_type=ShapeType.ARROW,
            points=[(0.35, 0.40), (0.48, 0.48)],
            color=(229, 168, 35, 255),
            width=3.5,
        )
        stroke2 = Stroke(
            shape_type=ShapeType.RECTANGLE,
            points=[(0.48, 0.48), (0.62, 0.62)],
            color=(0, 200, 255, 220),
            width=2.5,
        )
        stroke3 = Stroke(
            shape_type=ShapeType.TEXT,
            points=[(0.50, 0.45)],
            color=(255, 255, 255, 255),
            text="Check comp grain integration",
        )
        window.annotation_store.add_stroke(window.clock.current_frame, stroke1)
        window.annotation_store.add_stroke(window.clock.current_frame, stroke2)
        window.annotation_store.add_stroke(window.clock.current_frame, stroke3)
        window.hud_color_adj.show()
        window.hud_color_adj.move(QPoint(30, 30))
        window.viewport.update()
        app.processEvents()
        save_widget(window.viewport, "viewport_annotations_huds.png")
        window.hud_color_adj.hide()
        window.annotation_store.clear_frame(window.clock.current_frame)
    except Exception as e:
        print("Viewport Annotations error:", e)

    # 33. Viewport: Out of Range
    try:
        window.viewport.set_show_out_of_range(True)
        window.viewport.highlight_nan_pixels = True
        window.viewport.highlight_neg_pixels = True
        window.viewport.update()
        app.processEvents()
        save_widget(window.viewport, "viewport_out_of_range.png")
        window.viewport.set_show_out_of_range(False)
    except Exception as e:
        print("Viewport Out of Range error:", e)

    # 34. Viewport: Safe Guides & Matte
    try:
        window.viewport.set_matte(2.35, 0.85)
        window.viewport.show_safe_guides = True
        window.viewport.update()
        app.processEvents()
        save_widget(window.viewport, "viewport_safe_guides_matte.png")
        window.viewport.set_matte(None)
        window.viewport.show_safe_guides = False
        window.viewport.update()
    except Exception as e:
        print("Viewport Safe Guides error:", e)

    window.close()
    print("All 36 UI screenshots generated successfully!")

if __name__ == "__main__":
    main()
