"""
Unit and Integration Tests for Sources Panel, Sequences, Image Stacks, and Layouts.
"""
import os
import tempfile
import numpy as np
from PIL import Image
import pytest
from PySide6.QtCore import Qt

from openreview.models.session_graph import (
    SessionGraph,
    SourceItem,
    FolderItem,
    SequenceView,
    SequenceClip,
    StackView,
    LayoutView,
    ViewType,
)
from openreview.ui.sources_panel import SourcesPanelWidget, SourcesDockWidget
from openreview.core.layout_compositor import composite_layout_grid, resize_frame_fast
from openreview.models.comparison import ComparisonMode
from openreview.ui.main_window import MainWindow


@pytest.fixture
def temp_media():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 3 image files
        paths = []
        for i in range(1, 4):
            img_path = os.path.join(tmpdir, f"render_v{i:03d}.png")
            img = Image.new("RGBA", (128, 128), color=(i * 60, i * 40, 200, 255))
            img.save(img_path)
            paths.append(img_path)
        yield paths


def test_sources_panel_hierarchy_and_folders(qtbot, temp_media):
    graph = SessionGraph()
    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)

    # 1. Add sources to graph
    s1 = graph.add_source_from_path(temp_media[0])
    s2 = graph.add_source_from_path(temp_media[1])
    assert s1 is not None and s2 is not None
    assert len(graph.sources) == 2

    # 2. Create folder
    folder = graph.create_folder("CG Elements")
    assert folder.name == "CG Elements"
    assert folder.id in graph.folders

    # Refresh panel tree
    panel.refresh_tree()
    assert panel.tree.topLevelItemCount() == 4  # Sources, Sequences, Stacks, Layouts

    # 3. Delete source
    graph.delete_source(s2.id)
    assert s2.id not in graph.sources
    assert len(graph.sources) == 1

    # 4. Delete folder
    graph.delete_folder(folder.id)
    assert folder.id not in graph.folders


def test_sequence_creation_and_reordering(qtbot, temp_media):
    graph = SessionGraph()
    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)

    s1 = graph.add_source_from_path(temp_media[0])
    s2 = graph.add_source_from_path(temp_media[1])
    s3 = graph.add_source_from_path(temp_media[2])

    # Create sequence
    seq = graph.create_sequence("Cut_v01", [s1.id, s2.id, s3.id])
    assert len(seq.clips) == 3
    assert graph.active_view_type == ViewType.SEQUENCE
    assert graph.active_view_id == seq.id

    panel.refresh_tree()
    panel._refresh_subpanels()

    # Inputs list should have 3 items
    assert panel.list_inputs.count() == 3

    # Reorder clips using Move Up / Move Down buttons
    panel.list_inputs.setCurrentRow(1)
    panel._on_input_move_up()
    assert seq.clips[0].source_id == s2.id
    assert seq.clips[1].source_id == s1.id

    # Remove clip
    panel.list_inputs.setCurrentRow(2)
    panel._on_input_remove()
    assert len(seq.clips) == 2


def test_stack_difference_and_inverted_difference(qtbot, temp_media):
    graph = SessionGraph()
    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)

    s1 = graph.add_source_from_path(temp_media[0])
    s2 = graph.add_source_from_path(temp_media[1])

    # Create stack
    stk = graph.create_stack("Comp_Compare", [s1.id, s2.id], compare_mode="difference")
    assert stk.compare_mode == "difference"
    assert stk.index_a == 0
    assert stk.index_b == 1

    panel.refresh_tree()
    panel._refresh_subpanels()

    # Change compare mode to difference_inverted
    panel.combo_stack_mode.setCurrentText("Inverted Diff")
    assert stk.compare_mode == "difference_inverted"

    # Change compare mode to wipe
    panel.combo_stack_mode.setCurrentText("Wipe")
    assert stk.compare_mode == "wipe"


def test_layout_scale_percentages(qtbot, temp_media):
    graph = SessionGraph()
    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)

    s1 = graph.add_source_from_path(temp_media[0])
    s2 = graph.add_source_from_path(temp_media[1])

    # Create layout with 50% scale
    lay = graph.create_layout("Review_Grid", [s1.id, s2.id], scale_pct=50)
    assert lay.scale_pct == 50

    panel.refresh_tree()
    panel._refresh_subpanels()

    # Test scale percentage combo
    panel.combo_scale_pct.setCurrentText("25%")
    assert lay.scale_pct == 25

    panel.combo_scale_pct.setCurrentText("10%")
    assert lay.scale_pct == 10

    panel.combo_scale_pct.setCurrentText("100%")
    assert lay.scale_pct == 100


def test_clip_edit_panel_properties(qtbot, temp_media):
    graph = SessionGraph()
    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)

    s1 = graph.add_source_from_path(temp_media[0])
    graph.set_active_view(ViewType.SOURCE, s1.id)
    panel.refresh_tree()
    panel._refresh_subpanels()

    # Edit in/out frames
    panel.spin_in.setValue(1050)
    assert s1.frame_in == 1050

    panel.spin_out.setValue(1150)
    assert s1.frame_out == 1150

    # Edit FPS
    panel.spin_fps.setValue(30.0)
    assert s1.fps == 30.0

    # Edit Colorspace
    panel.combo_colorspace.setCurrentText("ACEScg")
    assert s1.colorspace == "ACEScg"


def test_main_window_sources_dock_integration(qtbot, temp_media):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # 1. Dock exists and starts visible
    assert hasattr(window, "sources_dock")
    assert window.sources_dock is not None

    # Toggle dock (P shortcut)
    init_hidden = window.sources_dock.isHidden()
    window._on_toggle_playlist()
    assert window.sources_dock.isHidden() != init_hidden
    window._on_toggle_playlist()
    assert window.sources_dock.isHidden() == init_hidden

    # 2. Add sources to main window session graph
    s1 = window.session_graph.add_source_from_path(temp_media[0])
    s2 = window.session_graph.add_source_from_path(temp_media[1])
    s3 = window.session_graph.add_source_from_path(temp_media[2])

    # 3. Create Sequence View and conform timeline
    seq = window.session_graph.create_sequence("Episode_Cut", [s1.id, s2.id, s3.id])
    window._on_active_view_changed("sequence", seq.id)

    assert window.clock.start_frame == seq.start_frame
    assert window.clock.end_frame == seq.end_frame

    # Render frame 1001
    window._on_frame_changed(window.clock.start_frame)
    assert window.viewport._img_width > 0

    # 4. Create Stack View with Difference mode
    stk = window.session_graph.create_stack("Comp_Diff", [s1.id, s2.id], compare_mode="difference")
    window._on_active_view_changed("stack", stk.id)
    assert window.comparison_state.mode == ComparisonMode.DIFFERENCE
    assert window.viewport.comparison_state.mode == ComparisonMode.DIFFERENCE

    # Render stack frame
    window._on_frame_changed(window.clock.start_frame)
    assert window.viewport._image_b is not None

    # 5. Create Layout View with 50% scale
    lay = window.session_graph.create_layout("Quad_Grid", [s1.id, s2.id, s3.id], scale_pct=50)
    window._on_active_view_changed("layout", lay.id)
    assert window.comparison_state.mode == ComparisonMode.OFF

    # Render layout frame
    window._on_frame_changed(window.clock.start_frame)
    assert window.viewport._img_width > 0
    assert "50%" in window.resolution_status_label.text()


def test_source_click_activates_and_renders(qtbot, temp_media):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Add 2 sources with custom frame ranges
    s1 = window.session_graph.add_source_from_path(temp_media[0])
    s1.frame_in = 100
    s1.frame_out = 150
    s2 = window.session_graph.add_source_from_path(temp_media[1])
    s2.frame_in = 200
    s2.frame_out = 250

    window.sources_dock.panel.refresh_tree()

    # Set up playback and custom In/Out marks within source 2 range
    window.clock.set_range(50, 300, reset_in_out=False)
    window.clock.set_in_mark(210)
    window.clock.set_out_mark(240)
    window.clock.play()
    assert window.clock.is_playing is True

    # Find tree item for source 2
    tree = window.sources_dock.panel.tree
    root_sources = tree.topLevelItem(0)  # SOURCES root
    s2_item = None
    for i in range(root_sources.childCount()):
        child = root_sources.child(i)
        data = child.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("id") == s2.id:
            s2_item = child
            break

    assert s2_item is not None

    # Single-click source 2 selects but does NOT switch active view
    tree.itemClicked.emit(s2_item, 0)
    assert window.session_graph.active_view_id != s2.id

    # Double-click source 2 activates it ("Select current view")
    tree.itemDoubleClicked.emit(s2_item, 0)

    # 1. Playback should pause
    assert window.clock.is_playing is False

    # 2. Timeline range should be [200, 250]
    assert window.clock.start_frame == 200
    assert window.clock.end_frame == 250

    # 3. In/Out marks auto-snap to new source range [200, 250]
    assert window.clock.in_frame == 200
    assert window.clock.out_frame == 250

    # 4. Playhead should jump to frame_in (200)
    assert window.clock.current_frame == 200

    # 5. Viewport should render frame data
    assert window.viewport._img_width > 0
    assert window.viewport._image_a is not None

    # 6. Test double-clicking a folder toggles expansion
    folder = window.session_graph.create_folder("VFX Shots")
    window.sources_dock.panel.refresh_tree()
    root_sources = tree.topLevelItem(0)
    folder_item = None
    for i in range(root_sources.childCount()):
        child = root_sources.child(i)
        data = child.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "folder":
            folder_item = child
            break
    assert folder_item is not None
    init_expanded = folder_item.isExpanded()
    tree.itemDoubleClicked.emit(folder_item, 0)
    assert folder_item.isExpanded() != init_expanded

    # 7. Test double-clicking inside list_inputs switches to that source
    seq = window.session_graph.create_sequence("TestSeq", [s1.id, s2.id])
    window.session_graph.set_active_view(ViewType.SEQUENCE, seq.id)
    window.sources_dock.panel._refresh_subpanels()
    assert window.sources_dock.panel.list_inputs.count() == 2

    # Double click first item in list_inputs (s1)
    input_item_0 = window.sources_dock.panel.list_inputs.item(0)
    window.sources_dock.panel.list_inputs.itemDoubleClicked.emit(input_item_0)
    assert window.session_graph.active_view_type == ViewType.SOURCE
    assert window.session_graph.active_view_id == s1.id
    assert window.clock.start_frame == 100
    assert window.clock.end_frame == 150
    assert window.clock.current_frame == 100


def test_clear_in_out_button_resets_clip_duration(qtbot, temp_media):
    """Verify that Clear In/Out button resets modified clip duration back to original detected media bounds."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    s = window.session_graph.add_source_from_path(temp_media[0])
    s.orig_start_frame = 1
    s.orig_end_frame = 100
    s.start_frame = 1
    s.end_frame = 100

    window.sources_dock.panel.refresh_tree()
    window.session_graph.set_active_view(ViewType.SOURCE, s.id)

    panel = window.sources_dock.panel
    panel.tabs.setCurrentIndex(1)  # Edit tab
    panel._refresh_subpanels()

    assert panel.btn_clear_in_out is not None
    assert panel.btn_clear_in_out.text() == "Clear In/Out"

    # User trims the clip using spinboxes
    panel.spin_in.setValue(25)
    panel.spin_out.setValue(75)

    assert s.start_frame == 25
    assert s.end_frame == 75
    assert window.clock.start_frame == 25
    assert window.clock.end_frame == 75

    # Click Clear In/Out button
    panel.btn_clear_in_out.click()

    # Original frame bounds should be restored
    assert s.start_frame == 1
    assert s.end_frame == 100
    assert panel.spin_in.value() == 1
    assert panel.spin_out.value() == 100

    # MainWindow timeline should reflect the restored full range
    assert window.clock.start_frame == 1
    assert window.clock.end_frame == 100
    assert window.clock.in_frame == 1
    assert window.clock.out_frame == 100


def test_folder_creation_button_and_organizing(qtbot, monkeypatch, temp_media):
    from PySide6.QtWidgets import QInputDialog
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    s1 = window.session_graph.add_source_from_path(temp_media[0])
    s2 = window.session_graph.add_source_from_path(temp_media[1])

    panel = window.sources_dock.panel
    panel.refresh_tree()

    # 1. Test clicking btn_new_folder creates a folder
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Comp Renders", True))
    panel.btn_new_folder.click()

    assert any(f.name == "Comp Renders" for f in window.session_graph.folders.values())
    created_f = [f for f in window.session_graph.folders.values() if f.name == "Comp Renders"][0]
    assert created_f.folder_type == "source"

    # 2. Test organizing: move s1 into Comp Renders via internal move
    panel._on_internal_move(
        {"type": "source", "id": s1.id},
        {"type": "folder", "id": created_f.id},
    )
    assert s1.parent_folder_id == created_f.id
    assert s1.id in created_f.source_ids

    # 3. Test moving back to root
    panel._on_internal_move(
        {"type": "source", "id": s1.id},
        {"type": "group", "id": "sources"},
    )
    assert s1.parent_folder_id is None
    assert s1.id not in created_f.source_ids


def test_close_session_and_delete_all_sources_clears_sources_panel(qtbot, temp_media):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    s1 = window.session_graph.add_source_from_path(temp_media[0])
    s2 = window.session_graph.add_source_from_path(temp_media[1])
    f = window.session_graph.create_folder("Daily")
    window.session_graph.move_item_to_folder("source", s1.id, f.id)
    window.sources_dock.panel.refresh_tree()

    assert len(window.session_graph.sources) == 2
    assert len(window.session_graph.folders) == 1

    # Close session
    window._on_close_session(prompt=False)

    # Session graph should be cleared
    assert len(window.session_graph.sources) == 0
    assert len(window.session_graph.folders) == 0
    assert window.resolution_status_label.text() == "No Media"

    # Sources panel tree should be completely empty under categories
    panel = window.sources_dock.panel
    for i in range(panel.tree.topLevelItemCount()):
        top_item = panel.tree.topLevelItem(i)
        assert top_item.childCount() == 0
    assert panel.list_inputs.count() == 0


def test_source_and_folder_rename(qtbot, temp_media, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from PySide6.QtGui import QKeyEvent
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    s1 = window.session_graph.add_source_from_path(temp_media[0])
    fld = window.session_graph.create_folder("Shot_A")
    panel = window.sources_dock.panel
    panel.refresh_tree()

    # 1. Rename source via panel._on_rename_item
    monkeypatch.setattr(QInputDialog, "getText", lambda parent, title, label, echo, text: ("Renamed_Source_01", True))
    s1_item = panel._find_item_by_id(s1.id)
    assert s1_item is not None
    panel._on_rename_item(s1_item)

    assert s1.name == "Renamed_Source_01"
    assert "Renamed_Source_01" in panel.lbl_active_title.text() or panel.lbl_active_title.text() != ""

    # 2. Rename folder via panel._on_rename_item
    monkeypatch.setattr(QInputDialog, "getText", lambda parent, title, label, echo, text: ("Renamed_Folder_01", True))
    fld_item = panel._find_item_by_id(fld.id)
    assert fld_item is not None
    panel._on_rename_item(fld_item)

    assert fld.name == "Renamed_Folder_01"

    # 3. F2 keypress on selected item
    monkeypatch.setattr(QInputDialog, "getText", lambda parent, title, label, echo, text: ("F2_Renamed_Source", True))
    s1_item = panel._find_item_by_id(s1.id)
    panel.tree.clearSelection()
    s1_item.setSelected(True)
    panel.tree.setCurrentItem(s1_item)

    f2_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
    panel.tree.keyPressEvent(f2_event)

    assert s1.name == "F2_Renamed_Source"


def test_tree_expand_collapse_single_click_and_state_preservation(qtbot):
    graph = SessionGraph()
    f1 = FolderItem(name="FolderA")
    graph.folders[f1.id] = f1
    graph.root_folder_ids.append(f1.id)

    s1 = SourceItem(name="Shot01", parent_folder_id=f1.id)
    graph.sources[s1.id] = s1

    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)
    panel.show()

    # 1. Folder item starts expanded
    f1_item = panel._find_item_by_id(f1.id)
    assert f1_item is not None
    assert f1_item.isExpanded() is True

    # 2. Single click on folder toggles it to collapsed
    panel._on_tree_item_clicked(f1_item, 0)
    assert f1_item.isExpanded() is False

    # 3. Single click on root_sources group toggles it to collapsed
    assert panel.root_sources.isExpanded() is True
    panel._on_tree_item_clicked(panel.root_sources, 0)
    assert panel.root_sources.isExpanded() is False

    # 4. Refreshing the tree preserves the collapsed state
    panel.refresh_tree()
    assert panel.root_sources.isExpanded() is False
    f1_item_after = panel._find_item_by_id(f1.id)
    assert f1_item_after is not None
    assert f1_item_after.isExpanded() is False

    # 5. Clicking folder again expands it
    panel._on_tree_item_clicked(f1_item_after, 0)
    assert f1_item_after.isExpanded() is True

    # 6. Refreshing again preserves folder expanded state
    panel.refresh_tree()
    f1_item_refreshed = panel._find_item_by_id(f1.id)
    assert f1_item_refreshed.isExpanded() is True


def test_start_at_option_shifts_frames(qtbot):
    graph = SessionGraph()
    s1 = SourceItem(
        name="Shot01",
        start_frame=1001,
        end_frame=1050,
        orig_start_frame=1001,
        orig_end_frame=1050,
    )
    graph.sources[s1.id] = s1
    graph.set_active_view(ViewType.SOURCE, s1.id)

    panel = SourcesPanelWidget(graph)
    qtbot.addWidget(panel)
    panel.show()
    panel.refresh_tree()
    panel._refresh_subpanels()

    # Initial state
    assert panel.spin_start_at.value() == 1001
    assert panel.combo_start_at.currentData() == 1001
    assert s1.duration == 50

    # 1. Select "Frame 1" preset
    f1_idx = panel.combo_start_at.findData(1)
    assert f1_idx >= 0
    panel.combo_start_at.setCurrentIndex(f1_idx)

    assert s1.start_frame == 1
    assert s1.end_frame == 50
    assert s1.duration == 50
    assert panel.spin_in.value() == 1
    assert panel.spin_out.value() == 50
    assert panel.spin_start_at.value() == 1

    # 2. Modify spin_start_at to custom frame 500
    panel.spin_start_at.setValue(500)
    assert s1.start_frame == 500
    assert s1.end_frame == 549
    assert s1.duration == 50
    assert panel.spin_in.value() == 500
    assert panel.spin_out.value() == 549
    assert panel.combo_start_at.currentData() == "custom"

    # 3. Select "Source Original" preset
    orig_idx = panel.combo_start_at.findData("original")
    assert orig_idx >= 0
    panel.combo_start_at.setCurrentIndex(orig_idx)

    assert s1.start_frame == 1001
    assert s1.end_frame == 1050
    assert s1.duration == 50
    assert panel.spin_start_at.value() == 1001



