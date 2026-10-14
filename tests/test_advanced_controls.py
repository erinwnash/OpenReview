"""
Unit & Integration Tests for Foundry Nuke-style Top Bar Controls,
Sources Panel Branch Visibility, and Vector Annotation Toolbar:
- Foundry Nuke viewer Gain slider (log 0.015625 to 64.0), f-stop stepper (◀ f/8 ▶)
- Gamma Y (0 to 4) and Saturation S (0 to 4) sliders with Ctrl+Click reset & interactive dragging
- Channel dropdown combobox
- Timeline volume button relocation
- Sources dock branch indicator visibility & Expand/Collapse All
- Modernized vector SVG annotation toolbar without dodge/burn/softness
"""
import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent, QPainter, QImage
from PySide6.QtWidgets import QWidget

from openreview.models.annotations import ShapeType, Stroke, AnnotationStore
from openreview.models.session_graph import SessionGraph, SequenceView, SequenceClip, SourceItem
from openreview.widgets.top_bar import TopControlBar, NukeSlider, ResetClickSlider, gain_to_fstop_label
from openreview.widgets.timeline import TimelineWidget
from openreview.widgets.markup_tools import MarkupToolPalette
from openreview.widgets.viewport import ViewportCanvas
from openreview.ui.main_window import MainWindow
from openreview.core.clock import PlaybackClock
from openreview.color.ocio_manager import OCIOManager


def test_top_bar_nuke_sliders_and_fstop_stepper(qtbot):
    ocio = OCIOManager()
    bar = TopControlBar(ocio)
    qtbot.addWidget(bar)

    # 1. Sliders should expand equally (1:1:1) to fill free window width
    bar.resize(1920, 38)
    bar.show()
    bar.layout().activate()
    assert bar.gain_slider.width() > 300
    assert bar.gam_slider.width() > 300
    assert bar.sat_slider.width() > 300
    assert abs(bar.gain_slider.width() - bar.gam_slider.width()) <= 2
    assert abs(bar.gam_slider.width() - bar.sat_slider.width()) <= 2

    # 2. Nuke ranges
    assert bar.gain_slider.minimum() == -600
    assert bar.gain_slider.maximum() == 600
    assert bar.gain_spin.minimum() <= 0.02
    assert bar.gain_spin.maximum() >= 64.0

    assert bar.gam_slider.minimum() == 0
    assert bar.gam_slider.maximum() == 1000
    assert bar.gam_spin.minimum() == 0.0
    assert bar.gam_spin.maximum() == 4.0

    assert bar.sat_slider.minimum() == 0
    assert bar.sat_slider.maximum() == 1000
    assert bar.sat_spin.minimum() == 0.0
    assert bar.sat_spin.maximum() == 4.0

    # 3. F-stop stepper functionality
    assert bar.btn_fstop_label.text() == "f/8"
    assert bar.gain == 1.0

    # Step up (+1 EV stop -> gain 2.0, f/11)
    bar.btn_fstop_next.click()
    assert round(bar.gain, 2) == 2.0
    assert bar.btn_fstop_label.text() == "f/11"

    # Step down 2 stops (-2 EV -> gain 0.5, f/5.6)
    bar.btn_fstop_prev.click()
    bar.btn_fstop_prev.click()
    assert round(bar.gain, 2) == 0.5
    assert bar.btn_fstop_label.text() == "f/5.6"

    # Reset via f-stop label click
    bar.btn_fstop_label.click()
    assert bar.gain == 1.0
    assert bar.btn_fstop_label.text() == "f/8"

    # 4. Setting values directly
    bar.set_gain(4.0)
    assert bar.gain_spin.value() == 4.0
    assert bar.btn_fstop_label.text() == "f/16"

    bar.set_gamma(2.0)
    assert bar.gam_spin.value() == 2.0

    bar.set_saturation(0.5)
    assert bar.sat_spin.value() == 0.5

    # 5. Ctrl + Click resets to default 1.0
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    bar.gain_slider.mousePressEvent(press_event)
    assert bar.gain_slider.value() == 0
    assert bar.gain == 1.0

    bar.gam_slider.mousePressEvent(press_event)
    assert bar.gam_slider.value() == 500
    assert bar.gamma == 1.0

    bar.sat_slider.mousePressEvent(press_event)
    assert bar.sat_slider.value() == 500
    assert bar.saturation == 1.0

    # 6. Interactive Dragging test on NukeSlider
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(bar.gain_slider.width() * 0.75, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    bar.gain_slider.mouseMoveEvent(move_event)
    assert bar.gain_slider.value() > 0
    assert bar.gain > 1.0


def test_channel_dropdown_combobox(qtbot):
    ocio = OCIOManager()
    bar = TopControlBar(ocio)
    qtbot.addWidget(bar)

    assert hasattr(bar, "chan_combo")
    assert bar.chan_combo.count() == 6

    received_modes = []
    bar.channel_changed.connect(received_modes.append)

    # Switch to Red (1)
    bar.set_channel_mode(1)
    assert bar.channel_mode == 1
    assert bar.chan_combo.currentData() == 1
    assert received_modes[-1] == 1

    # Switch to Alpha (4)
    bar.chan_combo.setCurrentIndex(4)
    assert bar.channel_mode == 4
    assert received_modes[-1] == 4


def test_timeline_volume_button_and_signal(qtbot):
    clock = PlaybackClock()
    store = AnnotationStore()
    tl = TimelineWidget(clock, store)
    qtbot.addWidget(tl)
    tl.show()

    assert hasattr(tl, "btn_audio")
    assert tl.btn_audio.isVisible() or not tl.btn_audio.icon().isNull() or tl.btn_audio.text() == "🔊"

    audio_signal_fired = []
    tl.audio_clicked.connect(lambda: audio_signal_fired.append(True))
    tl.btn_audio.click()
    assert audio_signal_fired == [True]


def test_sequence_in_out_navigation(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    graph = window.session_graph
    s1 = SourceItem(name="Shot01", path="C:/shot01.mov", start_frame=1, end_frame=100)
    s2 = SourceItem(name="Shot02", path="C:/shot02.mov", start_frame=1, end_frame=50)
    graph.sources[s1.id] = s1
    graph.sources[s2.id] = s2

    seq = SequenceView(
        name="Test Sequence",
        start_frame=1001,
        clips=[
            SequenceClip(source_id=s1.id, trim_in=1, trim_out=100),
            SequenceClip(source_id=s2.id, trim_in=1, trim_out=50),
        ],
    )
    graph.sequences[seq.id] = seq
    graph.set_active_view("sequence", seq.id)

    window.clock.seek(1001)

    window._on_step_clip_or_segment_next()
    assert window.clock.in_frame == 1101
    assert window.clock.out_frame == 1150
    assert window.clock.current_frame == 1101

    window._on_step_clip_or_segment_prev()
    assert window.clock.in_frame == 1001
    assert window.clock.out_frame == 1100
    assert window.clock.current_frame == 1001

    window.close()


def test_sources_panel_expand_and_collapse_all(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    panel = window.sources_dock.panel
    assert hasattr(panel, "btn_expand_all")
    assert hasattr(panel, "btn_collapse_all")

    # Click Expand All
    panel.btn_expand_all.click()
    assert panel.root_sources.isExpanded()
    assert panel.root_sequences.isExpanded()

    # Click Collapse All
    panel.btn_collapse_all.click()
    assert not panel.root_sources.isExpanded()

    window.close()


def test_annotation_palette_vector_icons_and_clean_tools(qtbot):
    bar = MarkupToolPalette()
    qtbot.addWidget(bar)

    # 1. Doubled slider widths
    assert bar.slider_size.width() >= 100 or bar.slider_size.minimumWidth() >= 100
    assert bar.slider_opacity.width() >= 90 or bar.slider_opacity.minimumWidth() >= 90

    # 2. Softness and dodge/burn/blur removed completely
    assert not hasattr(bar, "slider_softness")
    assert not hasattr(bar, "btn_dodge")
    assert not hasattr(bar, "btn_burn")
    assert not hasattr(bar, "btn_blur")

    # 3. Vector SVG icons loaded on buttons
    assert not bar.btn_select.icon().isNull()
    assert not bar.btn_pen.icon().isNull()
    assert not bar.btn_line.icon().isNull()
    assert not bar.btn_arrow.icon().isNull()
    assert not bar.btn_box.icon().isNull()
    assert not bar.btn_circle.icon().isNull()
    assert not bar.btn_text.icon().isNull()
    assert not bar.btn_undo.icon().isNull()
    assert not bar.btn_redo.icon().isNull()
    assert not bar.btn_clear.icon().isNull()
    assert not bar.btn_custom_color.icon().isNull()
    assert not bar.btn_close.icon().isNull()

    # 4. Redo button signal
    redo_called = []
    bar.redo_requested.connect(lambda: redo_called.append(True))
    bar.btn_redo.click()
    assert redo_called == [True]


def test_stroke_clean_serialization_and_render(qtbot):
    store = AnnotationStore()
    viewport = ViewportCanvas(store)
    qtbot.addWidget(viewport)

    stroke = Stroke(
        shape_type=ShapeType.PEN,
        points=[(0.1, 0.1), (0.5, 0.5)],
        color=(255, 255, 255, 200),
        width=5.0,
    )
    d = stroke.to_dict()
    assert d["shape_type"] == "pen"
    assert "softness" not in d

    restored = Stroke.from_dict(d)
    assert restored.shape_type == ShapeType.PEN

    img = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.darkGray)
    p = QPainter(img)
    viewport._render_stroke(p, stroke)
    p.end()
    assert not img.isNull()
