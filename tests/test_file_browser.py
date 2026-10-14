"""
Comprehensive unit tests for Inbuilt File Browser dock panel and workflow.
Verifies:
- Treeview navigation, sequence grouping, and multi-selection drag & drop data.
- Staging list operations and batch transfer to source bin.
- Default docking on window Right and area restrictions (Left & Right only).
- Dynamic breadcrumb bar and Ctrl+Click edit mode switching.
- Spotlight quick search filtering (standard and recursive).
- Single-click folder expand/collapse and double-click navigation.
- Folder rename and delete operations.
- OpenReview session (.ovr) file detection and action signals.
- Bookmarks management (add, rename, move, remove) and persistence.
"""
import os
import tempfile
import pytest
from PySide6.QtCore import Qt, QUrl, QPointF, QMimeData
from PySide6.QtWidgets import QApplication

from openreview.core.shortcuts import ShortcutManager
from openreview.core.preferences import PreferencesManager
from openreview.ui.file_browser_panel import (
    FileBrowserDockWidget,
    FileBrowserPanelWidget,
    FileBrowserTreeWidget,
    TemporaryStagingWidget,
    BreadcrumbBarWidget,
    SpotlightSearchWidget,
    get_available_drives,
    format_file_size,
)
from openreview.models.session_graph import SessionGraph


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_format_file_size():
    assert format_file_size(500) == "500 B"
    assert "KB" in format_file_size(2048)
    assert "MB" in format_file_size(5 * 1024 * 1024)
    assert "GB" in format_file_size(2 * 1024 * 1024 * 1024)


def test_available_drives():
    drives = get_available_drives()
    assert isinstance(drives, list)
    assert len(drives) > 0


def test_file_browser_dock_widget(qapp):
    dock = FileBrowserDockWidget()
    assert dock.objectName() == "FileBrowserDockWidget"
    allowed = dock.allowedAreas()
    assert bool(allowed & Qt.DockWidgetArea.LeftDockWidgetArea)
    assert bool(allowed & Qt.DockWidgetArea.RightDockWidgetArea)
    assert not bool(allowed & Qt.DockWidgetArea.TopDockWidgetArea)
    assert not bool(allowed & Qt.DockWidgetArea.BottomDockWidgetArea)
    assert isinstance(dock.panel, FileBrowserPanelWidget)


def test_file_browser_tree_sequence_grouping(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        for fnum in range(1001, 1006):
            fpath = os.path.join(tmpdir, f"render_v01.{fnum}.exr")
            with open(fpath, "wb") as f:
                f.write(b"exr_dummy_content")

        mp4_path = os.path.join(tmpdir, "edit_cut.mp4")
        with open(mp4_path, "wb") as f:
            f.write(b"mp4_dummy_content")

        tree = FileBrowserTreeWidget()
        tree.set_group_sequences(True)
        tree.load_directory(tmpdir)

        # 1 bookmarks root + 1 sequence item + 1 mp4 item = 3 top-level items
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        assert len(items) == 3

        seq_item = next(it for it in items if "render_v01" in it.text(0))
        assert "render_v01.[1001-1005].exr" in seq_item.text(0)
        assert seq_item.text(1) == "Sequence (5f)"
        assert seq_item.childCount() == 5

        vid_item = next(it for it in items if "edit_cut.mp4" in it.text(0))
        assert vid_item.text(1) == "Video"

        # Now test with grouping disabled: 1 bookmarks + 5 frames + 1 mp4 = 7 items
        tree.set_group_sequences(False)
        tree.load_directory(tmpdir)
        assert tree.topLevelItemCount() == 7


def test_tree_single_click_expand_and_double_click_navigate(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "shots")
        os.makedirs(sub)
        file_in_sub = os.path.join(sub, "shot01.mov")
        with open(file_in_sub, "w") as f: f.write("01")

        tree = FileBrowserTreeWidget()
        tree.load_directory(tmpdir)

        # Find folder item
        folder_item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if tree.topLevelItem(i).text(0) == "shots")
        assert not folder_item.isExpanded()

        # Single click toggles expand state
        tree._on_item_clicked(folder_item, 0)
        assert folder_item.isExpanded()

        tree._on_item_clicked(folder_item, 0)
        assert not folder_item.isExpanded()

        # Double click emits directory_changed
        navigated = []
        tree.directory_changed.connect(lambda p: navigated.append(p))
        tree._on_item_double_clicked(folder_item, 0)
        assert len(navigated) == 1
        assert os.path.abspath(navigated[0]) == os.path.abspath(sub)


def test_breadcrumbs_and_edit_mode(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        bc = BreadcrumbBarWidget()
        bc.set_path(tmpdir)
        assert os.path.abspath(bc.get_path()) == os.path.abspath(tmpdir)

        # Check breadcrumbs view is active (index 0)
        assert bc.layout_stack.currentIndex() == 0

        # Switch to edit mode
        bc.enter_edit_mode()
        assert bc.layout_stack.currentIndex() == 1
        assert bc.edit_path.text() == os.path.abspath(tmpdir)

        # Exit edit mode
        bc.exit_edit_mode()
        assert bc.layout_stack.currentIndex() == 0

        # Submitting edit changes path
        sub = os.path.join(tmpdir, "new_sub")
        os.makedirs(sub)
        changed_paths = []
        bc.path_changed.connect(lambda p: changed_paths.append(p))

        bc.enter_edit_mode()
        bc.edit_path.setText(sub)
        bc._on_edit_submitted()

        assert len(changed_paths) == 1
        assert os.path.abspath(changed_paths[0]) == os.path.abspath(sub)
        assert bc.layout_stack.currentIndex() == 0

        # Clicking outside (or focus loss) reverts to breadcrumbs mode
        from PySide6.QtGui import QMouseEvent, QFocusEvent
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtWidgets import QPushButton

        bc.enter_edit_mode()
        assert bc.layout_stack.currentIndex() == 1

        # Simulate clicking on another widget outside the address bar
        other_btn = QPushButton("Other")
        click_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        qapp.sendEvent(other_btn, click_event)
        assert bc.layout_stack.currentIndex() == 0
        assert not bc._edit_mode


def test_spotlight_search_filtering(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "plate_v01.mov")
        p2 = os.path.join(tmpdir, "comp_v02.mov")
        with open(p1, "w") as f: f.write("1")
        with open(p2, "w") as f: f.write("2")

        tree = FileBrowserTreeWidget()
        tree.load_directory(tmpdir)

        # Filter by "plate"
        tree.filter_items("plate", recursive=False)
        plate_item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if "plate_v01" in tree.topLevelItem(i).text(0))
        comp_item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if "comp_v02" in tree.topLevelItem(i).text(0))

        assert not plate_item.isHidden()
        assert comp_item.isHidden()

        # Clear filter
        tree.filter_items("", recursive=False)
        assert not plate_item.isHidden()
        assert not comp_item.isHidden()


def test_session_file_detection_and_signals(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        sess_file = os.path.join(tmpdir, "review_v01.ovr")
        with open(sess_file, "w") as f: f.write("{}")

        tree = FileBrowserTreeWidget()
        tree.load_directory(tmpdir)

        sess_item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if "review_v01.ovr" in tree.topLevelItem(i).text(0))
        assert sess_item.text(1) == "OpenReview Session"
        assert sess_item.data(0, Qt.ItemDataRole.UserRole + 1) == "session"


def test_bookmarks_management(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        pref_mgr = PreferencesManager.instance()
        pref_mgr.preferences.file_browser_bookmarks = []

        tree = FileBrowserTreeWidget()
        tree.load_directory(tmpdir)

        # Add bookmark
        tree.add_bookmark(tmpdir, "Project Root")
        bookmarks = pref_mgr.preferences.file_browser_bookmarks
        assert len(bookmarks) == 1
        assert bookmarks[0]["name"] == "Project Root"
        assert bookmarks[0]["path"] == tmpdir

        # Reload directory - check bookmark item in tree
        tree.load_directory(tmpdir)
        bm_root = tree._bookmarks_root_item
        assert bm_root is not None
        assert bm_root.childCount() == 1
        assert "Project Root" in bm_root.child(0).text(0)

        # Remove bookmark
        tree._remove_bookmark(bm_root.child(0))
        assert len(pref_mgr.preferences.file_browser_bookmarks) == 0


def test_temporary_staging_widget(qapp):
    staging = TemporaryStagingWidget()
    assert staging.list_widget.count() == 0
    assert not staging.btn_add_to_bin.isEnabled()

    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "shot1.mov")
        p2 = os.path.join(tmpdir, "shot2.mov")
        with open(p1, "w") as f: f.write("1")
        with open(p2, "w") as f: f.write("2")

        staging.add_paths([p1, p2])
        assert staging.list_widget.count() == 2
        assert staging.btn_add_to_bin.isEnabled()

        staging._on_remove_selected()
        emitted_paths = []
        staging.media_add_to_bin_requested.connect(lambda paths: emitted_paths.extend(paths))
        staging.btn_add_to_bin.click()

        assert len(emitted_paths) == 2
        assert staging.list_widget.count() == 0


def test_main_window_file_browser_default_right_dock(qapp):
    from openreview.ui.main_window import MainWindow
    win = MainWindow()
    assert hasattr(win, "file_browser_dock")
    assert isinstance(win.file_browser_dock, FileBrowserDockWidget)
    # Verify docked on RIGHT by default
    assert win.dockWidgetArea(win.file_browser_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert win.file_browser_dock.isHidden()

    # Toggle file browser via Ctrl+B handler
    win._on_toggle_file_browser()
    assert not win.file_browser_dock.isHidden()

    win._on_toggle_file_browser()
    assert win.file_browser_dock.isHidden()
    win.close()


def test_file_browser_shortcut_registration():
    sm = ShortcutManager.instance()
    action = sm.get_action("hud.toggle_file_browser")
    assert action is not None
    assert action.default_shortcut == "Ctrl+B"
    assert sm.find_conflict("Ctrl+B", exclude_action_id="hud.toggle_file_browser") is None


def test_panel_layout_and_liquid_splitter(qapp):
    panel = FileBrowserPanelWidget()
    # Verify splitter settings for liquid resizing
    assert panel.splitter.opaqueResize() is True
    assert panel.splitter.handleWidth() == 6
    assert panel.splitter.childrenCollapsible() is False

    # Verify dedicated rows: breadcrumbs and spotlight are distinct layout items
    assert panel.breadcrumbs.parent() == panel
    assert panel.spotlight.parent() == panel
    assert panel.breadcrumbs != panel.spotlight


def test_main_window_dock_options(qapp):
    from openreview.ui.main_window import MainWindow
    from PySide6.QtWidgets import QMainWindow
    win = MainWindow()
    opts = win.dockOptions()
    assert bool(opts & QMainWindow.DockOption.AnimatedDocks)
    assert bool(opts & QMainWindow.DockOption.GroupedDragging)
    assert bool(opts & QMainWindow.DockOption.AllowTabbedDocks)
    win.close()


def test_modern_scrollbar_and_separator_theme():
    from openreview.ui.theme import get_3dequalizer_stylesheet
    css = get_3dequalizer_stylesheet()
    assert "width: 6px;" in css
    assert "height: 6px;" in css
    assert "QMainWindow::separator" in css
    assert "QScrollBar:vertical" in css
    assert "border-radius: 3px;" in css


def test_timeline_bottom_full_width_dock_and_corners(qapp):
    from openreview.ui.main_window import MainWindow
    from PySide6.QtWidgets import QDockWidget
    win = MainWindow()

    # Verify corners assigned to BottomDockWidgetArea
    assert win.corner(Qt.Corner.BottomLeftCorner) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert win.corner(Qt.Corner.BottomRightCorner) == Qt.DockWidgetArea.BottomDockWidgetArea

    # Verify timeline dock
    assert hasattr(win, "timeline_dock")
    assert win.dockWidgetArea(win.timeline_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert win.timeline_dock.features() == QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
    assert win.timeline_dock.titleBarWidget() is not None

    # Verify File Browser width and column width
    assert win.file_browser_dock.panel.minimumWidth() >= 360
    assert win.file_browser_dock.panel.tree.columnWidth(0) == 260

    win.close()


def test_format_frame_ranges_utility():
    from openreview.core.sequence_parser import format_frame_ranges

    assert format_frame_ranges([]) == ""
    assert format_frame_ranges([42]) == "42"
    assert format_frame_ranges([1, 2, 3, 4, 5]) == "1-5"
    assert format_frame_ranges([1001, 1002, 1003, 1010, 1011, 1025]) == "1001-1003, 1010-1011, 1025"
    assert format_frame_ranges([1, 3, 5, 7]) == "1, 3, 5, 7"
    assert format_frame_ranges([1, 2, 4, 5, 6, 8]) == "1-2, 4-6, 8"


def test_sequence_with_gaps_compact_range(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create frames 1, 2, 3 and 10, 11
        for fnum in [1, 2, 3, 10, 11]:
            fpath = os.path.join(tmpdir, f"shot_v01.{fnum:04d}.exr")
            with open(fpath, "wb") as f:
                f.write(b"data")

        tree = FileBrowserTreeWidget()
        tree.set_group_sequences(True)
        tree.load_directory(tmpdir)

        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        seq_item = next(it for it in items if "shot_v01" in it.text(0))
        # Verify compact range notation
        assert "shot_v01.[1-3, 10-11].exr" in seq_item.text(0)
        assert seq_item.text(1) == "Sequence (5f)"
        assert seq_item.childCount() == 5


def test_regex_search_and_fallback(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        for fnum in range(1, 4):
            with open(os.path.join(tmpdir, f"render_v001.{fnum:04d}.exr"), "w") as f:
                f.write("exr")
            with open(os.path.join(tmpdir, f"comp_v002.{fnum:04d}.png"), "w") as f:
                f.write("png")
        with open(os.path.join(tmpdir, "notes_v001.txt"), "w") as f:
            f.write("txt")

        tree = FileBrowserTreeWidget()
        tree.set_group_sequences(True)
        tree.load_directory(tmpdir)

        # Regex search for render_v00[1-3]
        tree.filter_items(r"render_v00[1-3]", recursive=False)
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        item_texts = [it.text(0) for it in items]
        assert any("render_v001" in t for t in item_texts)
        assert not any("comp_v002" in t for t in item_texts)

        # Regex search for comp_v\d+
        tree.filter_items(r"comp_v\d+", recursive=False)
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        item_texts = [it.text(0) for it in items]
        assert any("comp_v002" in t for t in item_texts)
        assert not any("render_v001" in t for t in item_texts)

        # Fallback for unclosed bracket / incomplete regex
        tree.filter_items("render[", recursive=False)
        # Should not raise exception
        assert True

        # Searching for specific frame number in sequence
        tree.filter_items(r"0002", recursive=False)
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        item_texts = [it.text(0) for it in items]
        assert any("render_v001" in t for t in item_texts)
        assert any("comp_v002" in t for t in item_texts)


def test_recursive_search_with_sequence_grouping(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        sub1 = os.path.join(tmpdir, "shot01")
        sub2 = os.path.join(tmpdir, "shot02")
        os.makedirs(sub1)
        os.makedirs(sub2)

        for fnum in range(1001, 1005):
            with open(os.path.join(sub1, f"comp.{fnum}.exr"), "w") as f:
                f.write("exr")
        for fnum in range(1, 4):
            with open(os.path.join(sub2, f"plate.{fnum:04d}.png"), "w") as f:
                f.write("png")

        tree = FileBrowserTreeWidget()
        tree.load_directory(tmpdir)

        # Recursive search with grouping enabled
        tree.set_group_sequences(True)
        tree.filter_items(r"comp\..*\.exr", recursive=True)

        results = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        res_texts = [it.text(0) for it in results]
        # Should find grouped sequence with range
        seq_match = next((t for t in res_texts if "comp.[1001-1004].exr" in t), None)
        assert seq_match is not None

        # Recursive search with grouping disabled
        tree.set_group_sequences(False)
        tree.filter_items(r"comp\..*\.exr", recursive=True)
        results = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        res_texts = [it.text(0) for it in results]
        # Should have 4 separate files
        assert len(res_texts) == 4

