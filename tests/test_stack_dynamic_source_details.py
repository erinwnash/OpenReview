import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from openreview.ui.main_window import MainWindow
from openreview.models.session_graph import ViewType, StackView, SourceItem


@pytest.fixture
def stack_with_sources(tmp_path):
    p1 = str(tmp_path / "layer_a.exr")
    p2 = str(tmp_path / "layer_b.exr")
    for p, text in ((p1, b"LAYER_A_HEADER"), (p2, b"LAYER_B_HEADER")):
        with open(p, "wb") as f:
            f.write(text)
    return p1, p2


def test_stack_cycling_updates_source_details_hud(qtbot, stack_with_sources):
    p1, p2 = stack_with_sources
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    # Drop 2 items to top overlay -> creates Default stack
    mw._on_viewport_files_dropped_target([p1, p2], target="stack")
    stk = list(mw.session_graph.stacks.values())[0]
    assert stk.name == "Default stack"
    assert len(stk.source_ids) == 2

    # Open the Source Media Details HUD
    mw.hud_source_details.show()

    # Initially Layer A is active
    info_a = mw._get_current_source_info()
    assert os.path.normpath(info_a["file_path"]) == os.path.normpath(p1)

    # Cycle forward in stack (Z) -> Layer B becomes active
    mw._on_stack_cycle_forward()
    assert stk.current_layer_index == stk.index_b

    # Source Media Details HUD should have updated to Layer B
    info_b = mw._get_current_source_info()
    assert os.path.normpath(info_b["file_path"]) == os.path.normpath(p2)
    assert os.path.normpath(mw._current_media_path) == os.path.normpath(p2)

    # Viewport Info Strip should reflect Layer B
    assert mw.viewport.info_strip_data.get("file_path") == p2


def test_stack_edit_tab_updates_with_active_layer(qtbot, stack_with_sources):
    p1, p2 = stack_with_sources
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    mw._on_viewport_files_dropped_target([p1, p2], target="stack")
    stk = list(mw.session_graph.stacks.values())[0]
    panel = mw.sources_dock.panel

    src_a = mw.session_graph.sources[stk.source_ids[0]]
    src_b = mw.session_graph.sources[stk.source_ids[1]]

    src_a.start_frame = 100
    src_a.end_frame = 150
    src_a.fps = 24.0

    src_b.start_frame = 200
    src_b.end_frame = 280
    src_b.fps = 30.0

    # Layer A is active -> panel edit tab reflects Layer A
    panel._refresh_subpanels()
    assert panel.spin_in.value() == 100
    assert panel.spin_out.value() == 150
    assert panel.spin_fps.value() == 24.0

    # Cycle to Layer B -> panel edit tab reflects Layer B
    mw._on_stack_cycle_forward()
    assert panel.spin_in.value() == 200
    assert panel.spin_out.value() == 280
    assert panel.spin_fps.value() == 30.0


def test_stack_dual_mode_inputs_selection_updates_details(qtbot, stack_with_sources):
    p1, p2 = stack_with_sources
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    mw._on_viewport_files_dropped_target([p1, p2], target="stack")
    stk = list(mw.session_graph.stacks.values())[0]
    stk.compare_mode = "wipe"  # dual composite mode
    panel = mw.sources_dock.panel
    panel._refresh_subpanels()

    # In Wipe mode, defaults to Layer A
    info = mw._get_current_source_info()
    assert os.path.normpath(info["file_path"]) == os.path.normpath(p1)

    # User clicks on Layer B (row 1) in Inputs list
    panel.list_inputs.setCurrentRow(1)
    panel._on_input_selected()

    # Details HUD and Edit tab now inspect Layer B
    info_b = mw._get_current_source_info()
    assert os.path.normpath(info_b["file_path"]) == os.path.normpath(p2)
    assert os.path.normpath(mw._current_media_path) == os.path.normpath(p2)


def test_edit_tab_property_change_modifies_active_layer(qtbot, stack_with_sources):
    p1, p2 = stack_with_sources
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()

    mw._on_viewport_files_dropped_target([p1, p2], target="stack")
    stk = list(mw.session_graph.stacks.values())[0]
    panel = mw.sources_dock.panel

    # Cycle to Layer B
    mw._on_stack_cycle_forward()
    src_b = mw.session_graph.sources[stk.source_ids[1]]

    # Edit FPS from the Edit tab
    panel.spin_fps.setValue(48.0)
    assert src_b.fps == 48.0
