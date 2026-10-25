"""
Inbuilt File Browser and Staging Manager Dock Panel for OpenReview.
Features:
- Treeview browsing of local/network media with intelligent image sequence grouping.
- Dynamic breadcrumb bar with sibling directory dropdowns and Ctrl+Click text edit mode.
- Spotlight quick search filter with optional recursive subfolder search.
- Single-click folder in-place expand/collapse; double-click navigates into root.
- Folder rename (F2) and permanent delete (Delete) with safety confirmation.
- OpenReview session (.ovr) detection, import to current session, or launch in new window instance.
- Integrated persistent '★ Bookmarks' section at top of tree with add/edit/organize/remove.
- Multi-selection drag-and-drop to Source Media Bin and temporary staging queue.
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple, Any

from PySide6.QtCore import Qt, Signal, QUrl, QMimeData, QPoint, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QDrag, QCursor, QColor, QPainter, QPen, QKeyEvent, QMouseEvent, QFocusEvent
from PySide6.QtWidgets import (
    QWidget,
    QDockWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QMenu,
    QAbstractItemView,
    QSplitter,
    QToolButton,
    QCheckBox,
    QHeaderView,
    QApplication,
    QMessageBox,
    QInputDialog,
    QStackedWidget,
    QScrollArea,
)

from openreview.widgets.draggable_scroll_area import BlenderScrollArea

from openreview.core.sequence_parser import (
    SEQUENCE_REGEX,
    detect_image_sequence,
    SequenceInfo,
    format_frame_ranges,
)
from openreview.core.video_reader import VIDEO_EXTENSIONS, is_video_file
from openreview.core.image_io import IMAGE_EXTENSIONS
from openreview.core.preferences import PreferencesManager
from openreview.ui.dock_title_bar import TabbedDockTitleBar

AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".aac", ".flac", ".ogg", ".aiff", ".m4a",
}

SESSION_EXTENSIONS = {
    ".ovr",
}


def format_file_size(num_bytes: int) -> str:
    """Format bytes into readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_available_drives() -> List[str]:
    """Retrieve available drives on Windows or root mounting points on POSIX systems."""
    drives = []
    if sys.platform.startswith("win"):
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        drives = ["/"]
        for mount in ["/Volumes", "/mnt", "/media"]:
            if os.path.exists(mount):
                drives.append(mount)
    return drives


# ==============================================================================
# Dynamic Breadcrumb Navigation Bar
# ==============================================================================

class BreadcrumbBarWidget(QWidget):
    """
    Dynamic Breadcrumb Navigation Bar.
    - Shows segmented buttons for each path component.
    - Separator dropdown arrows list sibling directories.
    - Ctrl+Click anywhere (or double click) enters into editable QLineEdit mode.
    - Pressing Enter navigates; Escape cancels.
    """
    path_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_path: str = ""
        self._edit_mode: bool = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.layout_stack = QStackedWidget(self)
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.layout_stack)

        # 1. Breadcrumb View (Page 0)
        self.crumb_container = QWidget()
        self.crumb_layout = QHBoxLayout(self.crumb_container)
        self.crumb_layout.setContentsMargins(2, 2, 2, 2)
        self.crumb_layout.setSpacing(2)
        self.crumb_layout.addStretch()

        self.scroll_area = BlenderScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.crumb_container)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #333333; background: #222222; border-radius: 3px; }")

        self.layout_stack.addWidget(self.scroll_area)

        # 2. Text Edit View (Page 1)
        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText("Enter directory path...")
        self.edit_path.returnPressed.connect(self._on_edit_submitted)
        self.edit_path.setStyleSheet("""
            QLineEdit {
                background-color: #222222;
                border: 1px solid #e5a823;
                color: #ffffff;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        self.layout_stack.addWidget(self.edit_path)

        # Install event filter on container and scroll area for Ctrl+Click detection
        self.crumb_container.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        self.edit_path.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if self._edit_mode:
            # Handle clicking outside the address bar when in edit mode
            if event.type() == QMouseEvent.Type.MouseButtonPress:
                if watched is not self.edit_path:
                    # Click occurred outside the QLineEdit address bar
                    self.exit_edit_mode()
                    return False
            elif event.type() == QKeyEvent.Type.KeyPress:
                if watched is self.edit_path and event.key() == Qt.Key.Key_Escape:
                    self.exit_edit_mode()
                    return True
            elif event.type() == QFocusEvent.Type.FocusOut:
                if watched is self.edit_path:
                    self.exit_edit_mode()
                    return False

        if event.type() == QMouseEvent.Type.MouseButtonPress:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier or event.button() == Qt.MouseButton.LeftButton:
                # Ctrl+Click or clicking background enters edit mode
                # Only switch if clicked on background or explicitly requested
                if watched is self.crumb_container or watched is self.scroll_area.viewport():
                    self.enter_edit_mode()
                    return True
        elif event.type() == QMouseEvent.Type.MouseButtonDblClick:
            self.enter_edit_mode()
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._edit_mode and event.key() == Qt.Key.Key_Escape:
            self.exit_edit_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def enter_edit_mode(self) -> None:
        if self._edit_mode:
            return
        self._edit_mode = True
        self.edit_path.setText(self._current_path)
        self.layout_stack.setCurrentIndex(1)
        self.edit_path.setFocus()
        self.edit_path.selectAll()
        # Install application-level event filter to intercept clicks anywhere in the app
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def exit_edit_mode(self) -> None:
        if not self._edit_mode:
            return
        self._edit_mode = False
        app = QApplication.instance()
        if app:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        self.layout_stack.setCurrentIndex(0)

    def hideEvent(self, event) -> None:
        if self._edit_mode:
            self.exit_edit_mode()
        super().hideEvent(event)

    def _on_edit_submitted(self) -> None:
        raw = self.edit_path.text().strip()
        self.exit_edit_mode()
        if raw and os.path.exists(raw):
            self.set_path(raw)
            self.path_changed.emit(self._current_path)

    def set_path(self, path: str) -> None:
        norm = os.path.abspath(path)
        self._current_path = norm
        self._rebuild_breadcrumbs(norm)

    def get_path(self) -> str:
        return self._current_path

    def _rebuild_breadcrumbs(self, norm_path: str) -> None:
        # Clear existing buttons
        while self.crumb_layout.count() > 0:
            item = self.crumb_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        parts: List[Tuple[str, str]] = []  # (segment_name, accumulated_path)
        p = Path(norm_path)
        cur = p
        while True:
            name = cur.name if cur.name else str(cur)
            parts.insert(0, (name, str(cur)))
            if cur.parent == cur:
                break
            cur = cur.parent

        for i, (seg_name, seg_path) in enumerate(parts):
            # Segment button
            btn = QPushButton(seg_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #d0d0d0;
                    border: none;
                    padding: 2px 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #e5a823;
                    background: #2a2a2a;
                    border-radius: 2px;
                }
            """)
            btn.clicked.connect(lambda _, sp=seg_path: self._on_crumb_clicked(sp))
            self.crumb_layout.addWidget(btn)

            # Separator / sibling dropdown arrow
            sep = QToolButton()
            sep.setText("›")
            sep.setCursor(Qt.CursorShape.PointingHandCursor)
            sep.setStyleSheet("""
                QToolButton {
                    background: transparent;
                    color: #777777;
                    border: none;
                    padding: 0px 1px;
                    font-size: 10px;
                }
                QToolButton:hover {
                    color: #e5a823;
                }
            """)
            sep.clicked.connect(lambda _, sp=seg_path: self._show_sibling_menu(sp))
            self.crumb_layout.addWidget(sep)

        # Stretch to right-align or left-pack
        self.crumb_layout.addStretch()

    def _on_crumb_clicked(self, path: str) -> None:
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            self.enter_edit_mode()
            return
        if os.path.isdir(path):
            self.set_path(path)
            self.path_changed.emit(self._current_path)

    def _show_sibling_menu(self, dir_path: str) -> None:
        if not os.path.isdir(dir_path):
            return
        try:
            subdirs = sorted([d for d in os.scandir(dir_path) if d.is_dir()], key=lambda e: e.name.lower())
        except (PermissionError, OSError):
            return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #222222; color: #cccccc; border: 1px solid #333333; }")
        if not subdirs:
            act = menu.addAction("(No subfolders)")
            act.setEnabled(False)
        else:
            for d in subdirs[:30]:  # limit to top 30
                act = menu.addAction(d.name)
                act.triggered.connect(lambda _, p=d.path: self._on_sibling_selected(p))

        menu.exec(QCursor.pos())

    def _on_sibling_selected(self, path: str) -> None:
        self.set_path(path)
        self.path_changed.emit(self._current_path)


# ==============================================================================
# Spotlight Quick Search Widget
# ==============================================================================

class SpotlightSearchWidget(QWidget):
    """
    Spotlight Quick Search Widget for instant file filtering in Windows Explorer style.
    Provides real-time incremental query filtering with an optional recursive subfolder toggle.
    """
    search_changed = Signal(str, bool)  # (query_text, is_recursive)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search files & sequences... (Ctrl+F)")
        self.edit_search.setStyleSheet("""
            QLineEdit {
                background-color: #202020;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #e5a823;
            }
        """)
        self.edit_search.textChanged.connect(self._on_query_changed)
        layout.addWidget(self.edit_search, stretch=1)

        # Clear button
        self.btn_clear = QToolButton()
        self.btn_clear.setText("✕")
        self.btn_clear.setToolTip("Clear search")
        self.btn_clear.setStyleSheet("background: transparent; border: none; color: #888888; font-size: 10px;")
        self.btn_clear.clicked.connect(self.clear)
        self.btn_clear.hide()
        layout.addWidget(self.btn_clear)

        # Recursive search toggle button
        self.btn_recursive = QToolButton()
        self.btn_recursive.setText("Sub")
        self.btn_recursive.setCheckable(True)
        self.btn_recursive.setToolTip("Toggle recursive search across subdirectories")
        self.btn_recursive.setStyleSheet("""
            QToolButton {
                background-color: #252525;
                border: 1px solid #383838;
                color: #888888;
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 10px;
            }
            QToolButton:checked {
                background-color: #2c281e;
                color: #e5a823;
                border-color: #e5a823;
                font-weight: bold;
            }
        """)
        self.btn_recursive.toggled.connect(lambda _: self._on_query_changed())
        layout.addWidget(self.btn_recursive)

    def focus_input(self) -> None:
        self.edit_search.setFocus()
        self.edit_search.selectAll()

    def clear(self) -> None:
        self.edit_search.clear()

    def get_query(self) -> str:
        return self.edit_search.text().strip()

    def is_recursive(self) -> bool:
        return self.btn_recursive.isChecked()

    def _on_query_changed(self) -> None:
        q = self.get_query()
        self.btn_clear.setVisible(bool(q))
        self.search_changed.emit(q, self.is_recursive())


# ==============================================================================
# File Browser Tree Widget
# ==============================================================================

class FileBrowserTreeWidget(QTreeWidget):
    """
    QTreeWidget for browsing filesystem directories and media files.
    - Integrated '★ Bookmarks' pinned top section.
    - Single-click folder expands/collapses in-place.
    - Double-click folder navigates into it as active root.
    - OpenReview session (.ovr) import or new-instance launch.
    - Folder rename (F2) and safe permanent delete (Delete) with confirmation.
    - Real-time Spotlight search filtering.
    """
    media_open_requested = Signal(str)           # Single media path to load immediately
    media_add_to_bin_requested = Signal(list)    # List of paths to add to Source Bin
    media_add_to_staging_requested = Signal(list)# List of paths to add to Staging List
    session_import_requested = Signal(str)       # OpenReview session path to import
    session_new_instance_requested = Signal(str) # OpenReview session path to launch in new app
    directory_changed = Signal(str)              # Emitted when active root directory changes
    bookmark_selected = Signal(str)             # Emitted when a bookmark is clicked/jumped

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setAnimated(True)
        self.setHeaderLabels(["Name", "Type / Range", "Size"])
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.setColumnWidth(0, 260)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemExpanded.connect(self._on_item_expanded)

        self._group_sequences: bool = True
        self._current_directory: str = ""
        self._current_query: str = ""
        self._recursive_search: bool = False

        self._bookmarks_root_item: Optional[QTreeWidgetItem] = None

    def set_group_sequences(self, enabled: bool) -> None:
        self._group_sequences = enabled

    def get_selected_paths(self) -> List[str]:
        """Return real filesystem paths for currently selected items."""
        paths = []
        for item in self.selectedItems():
            p = item.data(0, Qt.ItemDataRole.UserRole)
            if p:
                paths.append(p)
        return paths

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._drag_occurred = False
        super().mousePressEvent(event)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Initiate drag carrying QUrls so MediaSourcesTreeWidget accepts the drop directly."""
        self._drag_occurred = True
        paths = self.get_selected_paths()
        if not paths:
            return

        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in paths if os.path.exists(p)]
        if not urls:
            return
        mime_data.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)

    def load_directory(self, dir_path: str) -> None:
        """Populate tree with Bookmarks pinned on top, followed by directory contents."""
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            return

        self._current_directory = os.path.abspath(dir_path)
        self.clear()

        # 1. Pinned Bookmarks Section
        self._populate_bookmarks_section()

        # 2. Directory Contents
        try:
            entries = sorted(os.scandir(self._current_directory), key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            return

        subdirs = []
        files = []
        for e in entries:
            try:
                if e.is_dir():
                    subdirs.append(e)
                else:
                    files.append(e)
            except OSError:
                continue

        # Add subdirectories
        for d in subdirs:
            item = QTreeWidgetItem(self)
            item.setText(0, d.name)
            item.setText(1, "Folder")
            item.setText(2, "")
            item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirIcon))
            item.setData(0, Qt.ItemDataRole.UserRole, d.path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
            # Dummy child for lazy expand
            dummy = QTreeWidgetItem(item)
            dummy.setText(0, "...")

        # Process and group files
        self._populate_files(files, parent_item=None)

        # Apply active search query filter if present
        if self._current_query:
            self.filter_items(self._current_query, self._recursive_search)

    def _populate_bookmarks_section(self) -> None:
        """Create and populate the pinned '★ Bookmarks' top group."""
        pref_mgr = PreferencesManager.instance()
        bookmarks = getattr(pref_mgr.preferences, "file_browser_bookmarks", [])

        self._bookmarks_root_item = QTreeWidgetItem(self)
        self._bookmarks_root_item.setText(0, f"★ Bookmarks ({len(bookmarks)})")
        self._bookmarks_root_item.setText(1, "Favorites")
        self._bookmarks_root_item.setForeground(0, QColor("#e5a823"))
        self._bookmarks_root_item.setData(0, Qt.ItemDataRole.UserRole + 1, "bookmarks_header")
        self._bookmarks_root_item.setExpanded(True)

        for b in bookmarks:
            b_name = b.get("name", "Bookmark")
            b_path = b.get("path", "")
            child = QTreeWidgetItem(self._bookmarks_root_item)
            child.setText(0, f"★ {b_name}")
            child.setText(1, "Bookmark")
            child.setText(2, b_path)
            child.setData(0, Qt.ItemDataRole.UserRole, b_path)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, "bookmark")
            child.setData(0, Qt.ItemDataRole.UserRole + 2, b_name)
            child.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirIcon))

    def _populate_files(self, file_entries: List[os.DirEntry], parent_item: Optional[QTreeWidgetItem] = None) -> None:
        """Add files to the tree, grouping image sequences if enabled."""
        if not self._group_sequences:
            for f in file_entries:
                self._add_single_file_item(f.name, f.path, f.stat().st_size, parent_item=parent_item)
            return

        seq_groups: Dict[Tuple[str, str, str], List[Tuple[int, str, int]]] = {}
        standalone_files = []

        for f in file_entries:
            name = f.name
            m = SEQUENCE_REGEX.match(name)
            ext = os.path.splitext(name)[1].lower()
            if m and ext in IMAGE_EXTENSIONS and not is_video_file(name):
                prefix = m.group(1)
                sep = m.group(2)
                fnum = int(m.group(3))
                key = (prefix, sep, ext)
                if key not in seq_groups:
                    seq_groups[key] = []
                try:
                    size = f.stat().st_size
                except OSError:
                    size = 0
                seq_groups[key].append((fnum, f.path, size))
            else:
                standalone_files.append(f)

        # Sequences
        for (prefix, sep, ext), frames in sorted(seq_groups.items(), key=lambda x: x[0][0].lower()):
            frames.sort(key=lambda x: x[0])
            if len(frames) > 1:
                frame_nums = [fn for fn, _, _ in frames]
                range_str = format_frame_ranges(frame_nums)
                total_size = sum(sz for _, _, sz in frames)
                rep_path = frames[0][1]

                item = QTreeWidgetItem(self if parent_item is None else parent_item)
                display_name = f"{prefix}{sep}[{range_str}]{ext}"
                item.setText(0, display_name)
                item.setText(1, f"Sequence ({len(frames)}f)")
                item.setText(2, format_file_size(total_size))
                item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
                item.setData(0, Qt.ItemDataRole.UserRole, rep_path)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, "sequence")
                item.setData(0, Qt.ItemDataRole.UserRole + 2, [p for _, p, _ in frames])

                for fn, fp, sz in frames:
                    child = QTreeWidgetItem(item)
                    child.setText(0, os.path.basename(fp))
                    child.setText(1, f"Frame {fn}")
                    child.setText(2, format_file_size(sz))
                    child.setData(0, Qt.ItemDataRole.UserRole, fp)
                    child.setData(0, Qt.ItemDataRole.UserRole + 1, "image")
            else:
                fn, fp, sz = frames[0]
                self._add_single_file_item(os.path.basename(fp), fp, sz, parent_item=parent_item)

        # Standalone files
        for f in standalone_files:
            try:
                sz = f.stat().st_size
            except OSError:
                sz = 0
            self._add_single_file_item(f.name, f.path, sz, parent_item=parent_item)

    def _add_single_file_item(self, name: str, path: str, size: int, parent_item: Optional[QTreeWidgetItem] = None) -> QTreeWidgetItem:
        ext = os.path.splitext(name)[1].lower()
        if ext in SESSION_EXTENSIONS:
            ftype = "OpenReview Session"
        elif is_video_file(name):
            ftype = "Video"
        elif ext in IMAGE_EXTENSIONS:
            ftype = "Image"
        elif ext in AUDIO_EXTENSIONS:
            ftype = "Audio"
        else:
            ftype = f"File ({ext})" if ext else "File"

        item = QTreeWidgetItem(self if parent_item is None else parent_item)
        item.setText(0, name)
        item.setText(1, ftype)
        item.setText(2, format_file_size(size))
        item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, "session" if ext in SESSION_EXTENSIONS else ftype.lower())

        if ext in SESSION_EXTENSIONS:
            item.setForeground(0, QColor("#e5a823"))
            item.setForeground(1, QColor("#e5a823"))

        return item

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Lazy load child directories when an item is expanded."""
        itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if itype != "dir":
            return

        if item.childCount() > 0 and item.child(0).text(0) != "...":
            return

        item.takeChildren()

        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or not os.path.isdir(dir_path):
            return

        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            return

        subdirs = []
        files = []
        for e in entries:
            try:
                if e.is_dir():
                    subdirs.append(e)
                else:
                    files.append(e)
            except OSError:
                continue

        for d in subdirs:
            child = QTreeWidgetItem(item)
            child.setText(0, d.name)
            child.setText(1, "Folder")
            child.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirIcon))
            child.setData(0, Qt.ItemDataRole.UserRole, d.path)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
            dummy = QTreeWidgetItem(child)
            dummy.setText(0, "...")

        self._populate_files(files, parent_item=item)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Single click on a folder toggles its expanded state in-place."""
        if getattr(self, "_drag_occurred", False):
            return
        itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if itype == "dir":
            item.setExpanded(not item.isExpanded())

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Double click navigates into folders as active root, or handles sessions/media."""
        itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        if itype == "dir" or itype == "bookmark":
            # Navigate root directory into that folder
            self.directory_changed.emit(path)
        elif itype == "session":
            # Prompt user: import into current session or launch in new window
            self._prompt_session_action(path)
        else:
            # Media or sequence: load into viewport immediately
            self.media_open_requested.emit(path)

    def _prompt_session_action(self, path: str) -> None:
        """Ask user whether to import session into active workspace or launch separate window instance."""
        box = QMessageBox(self)
        box.setWindowTitle("OpenReview Session")
        box.setText(f"Open session file:\n{os.path.basename(path)}")
        btn_import = box.addButton("Import into Current Session", QMessageBox.ButtonRole.AcceptRole)
        btn_new = box.addButton("Open in New Window", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)

        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_import:
            self.session_import_requested.emit(path)
        elif clicked == btn_new:
            self.session_new_instance_requested.emit(path)

    # --------------------------------------------------------------------------
    # Spotlight Search & Filter
    # --------------------------------------------------------------------------
    @staticmethod
    def _compile_search_regex(query: str) -> Optional[re.Pattern]:
        """Compile search query into a case-insensitive regex with graceful literal fallback."""
        trimmed = query.strip()
        if not trimmed:
            return None
        try:
            return re.compile(trimmed, re.IGNORECASE)
        except re.error:
            return re.compile(re.escape(trimmed), re.IGNORECASE)

    def _clear_search_results(self) -> None:
        """Remove any dynamically generated search result items from the tree."""
        to_remove = []
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole + 3) == "search_result":
                to_remove.append(it)
        for it in to_remove:
            idx = self.indexOfTopLevelItem(it)
            if idx >= 0:
                self.takeTopLevelItem(idx)

    def _add_search_result_item(self, rel_path: str, full_path: str, fsize: int) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self)
        item.setText(0, rel_path)
        ext = os.path.splitext(full_path)[1].lower()
        itype = "session" if ext in SESSION_EXTENSIONS else "file"
        item.setText(1, "Session" if ext in SESSION_EXTENSIONS else "File")
        item.setText(2, format_file_size(fsize))
        item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
        item.setData(0, Qt.ItemDataRole.UserRole, full_path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, itype)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, "search_result")
        return item

    def filter_items(self, query: str, recursive: bool = False) -> None:
        """Filter visible items based on query string using regular expressions with smart fallback."""
        self._current_query = query.strip()
        self._recursive_search = recursive

        if not self._current_query:
            self._clear_search_results()
            # Restore all visibility
            for i in range(self.topLevelItemCount()):
                item = self.topLevelItem(i)
                item.setHidden(False)
                self._show_all_children(item)
            return

        regex = self._compile_search_regex(self._current_query)

        if not recursive:
            self._clear_search_results()
            # Filter top-level items in current directory
            for i in range(self.topLevelItemCount()):
                item = self.topLevelItem(i)
                if item is self._bookmarks_root_item:
                    # Filter bookmark children
                    has_match = False
                    for b_idx in range(item.childCount()):
                        b_child = item.child(b_idx)
                        matches = bool(
                            regex and (regex.search(b_child.text(0)) or regex.search(b_child.text(2)))
                        )
                        b_child.setHidden(not matches)
                        if matches:
                            has_match = True
                    item.setHidden(not has_match)
                    continue

                itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if itype == "sequence":
                    # Match sequence pattern/name or type
                    seq_match = bool(regex and (regex.search(item.text(0)) or regex.search(item.text(1))))
                    child_match = False
                    for c_idx in range(item.childCount()):
                        child_item = item.child(c_idx)
                        c_matched = bool(regex and (regex.search(child_item.text(0)) or regex.search(child_item.text(1))))
                        child_item.setHidden(not c_matched)
                        if c_matched:
                            child_match = True
                    if seq_match:
                        self._show_all_children(item)
                    item.setHidden(not (seq_match or child_match))
                else:
                    matches = bool(regex and (regex.search(item.text(0)) or regex.search(item.text(1))))
                    item.setHidden(not matches)
        else:
            # Recursive scan and display matching files under current directory
            self._run_recursive_filter(regex)

    def _show_all_children(self, item: QTreeWidgetItem) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setHidden(False)
            self._show_all_children(child)

    def _run_recursive_filter(self, regex: Optional[re.Pattern]) -> None:
        """Search recursively under the current directory and display matching results with sequence grouping."""
        if not self._current_directory or not os.path.isdir(self._current_directory) or regex is None:
            return

        self._clear_search_results()

        # Hide current directory tree items
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            it.setHidden(True)

        matching_files: List[Tuple[str, str, str, int]] = []
        try:
            for root, dirs, files in os.walk(self._current_directory):
                for f in files:
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, self._current_directory)
                    if regex.search(f) or regex.search(rel):
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            sz = 0
                        matching_files.append((root, f, fp, sz))
                # Stop if too many matches to keep UI fast
                if len(matching_files) > 1000:
                    break
        except (PermissionError, OSError):
            pass

        if not matching_files:
            return

        if not self._group_sequences:
            for root, f, fp, sz in matching_files:
                rel = os.path.relpath(fp, self._current_directory)
                self._add_search_result_item(rel, fp, sz)
            return

        # Group image sequences by (directory, prefix, sep, ext)
        seq_groups: Dict[Tuple[str, str, str, str], List[Tuple[int, str, int]]] = {}
        standalone: List[Tuple[str, str, str, int]] = []

        for root, f, fp, sz in matching_files:
            m = SEQUENCE_REGEX.match(f)
            ext = os.path.splitext(f)[1].lower()
            if m and ext in IMAGE_EXTENSIONS and not is_video_file(f):
                prefix = m.group(1)
                sep = m.group(2)
                fnum = int(m.group(3))
                key = (root, prefix, sep, ext)
                if key not in seq_groups:
                    seq_groups[key] = []
                seq_groups[key].append((fnum, fp, sz))
            else:
                standalone.append((root, f, fp, sz))

        # Add sequence search results
        for (root, prefix, sep, ext), frames in sorted(seq_groups.items(), key=lambda x: (x[0][0].lower(), x[0][1].lower())):
            frames.sort(key=lambda x: x[0])
            if len(frames) > 1:
                frame_nums = [fn for fn, _, _ in frames]
                range_str = format_frame_ranges(frame_nums)
                total_size = sum(sz for _, _, sz in frames)
                rep_path = frames[0][1]

                rel_dir = os.path.relpath(root, self._current_directory)
                seq_label = f"{prefix}{sep}[{range_str}]{ext}"
                display_name = seq_label if rel_dir == "." else os.path.join(rel_dir, seq_label)

                item = QTreeWidgetItem(self)
                item.setText(0, display_name)
                item.setText(1, f"Sequence ({len(frames)}f)")
                item.setText(2, format_file_size(total_size))
                item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
                item.setData(0, Qt.ItemDataRole.UserRole, rep_path)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, "sequence")
                item.setData(0, Qt.ItemDataRole.UserRole + 2, [p for _, p, _ in frames])
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "search_result")

                for fn, fp, sz in frames:
                    child = QTreeWidgetItem(item)
                    child.setText(0, os.path.basename(fp))
                    child.setText(1, f"Frame {fn}")
                    child.setText(2, format_file_size(sz))
                    child.setData(0, Qt.ItemDataRole.UserRole, fp)
                    child.setData(0, Qt.ItemDataRole.UserRole + 1, "image")
                    child.setData(0, Qt.ItemDataRole.UserRole + 3, "search_result")
            else:
                fn, fp, sz = frames[0]
                rel = os.path.relpath(fp, self._current_directory)
                self._add_search_result_item(rel, fp, sz)

        # Add standalone file search results
        for root, f, fp, sz in standalone:
            rel = os.path.relpath(fp, self._current_directory)
            self._add_search_result_item(rel, fp, sz)

    # --------------------------------------------------------------------------
    # Context Menu, Rename, Delete, Bookmarks
    # --------------------------------------------------------------------------
    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if not item:
            return

        itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        selected_paths = self.get_selected_paths()

        menu = QMenu(self)

        if itype == "bookmarks_header":
            act_add_cur = menu.addAction("★ Bookmark Current Folder")
            act_add_cur.triggered.connect(lambda: self.add_bookmark(self._current_directory))
            menu.exec(self.viewport().mapToGlobal(pos))
            return

        if itype == "bookmark":
            act_jump = menu.addAction("Jump to Folder")
            act_rename = menu.addAction("Rename Bookmark...")
            act_up = menu.addAction("Move Up")
            act_down = menu.addAction("Move Down")
            menu.addSeparator()
            act_remove = menu.addAction("Remove Bookmark")

            chosen = menu.exec(self.viewport().mapToGlobal(pos))
            if chosen == act_jump:
                self.directory_changed.emit(path)
            elif chosen == act_rename:
                self._rename_bookmark(item)
            elif chosen == act_up:
                self._reorder_bookmark(item, -1)
            elif chosen == act_down:
                self._reorder_bookmark(item, 1)
            elif chosen == act_remove:
                self._remove_bookmark(item)
            return

        if itype == "dir":
            act_nav = menu.addAction("Navigate Into Folder")
            act_bookmark = menu.addAction("★ Bookmark Folder")
            act_staging = menu.addAction("Add Files in Folder to Staging List")
            menu.addSeparator()
            act_rename = menu.addAction("Rename Folder... (F2)")
            act_delete = menu.addAction("Delete Folder... (Delete)")
            menu.addSeparator()
            act_reveal = menu.addAction("Reveal in File Explorer")

            chosen = menu.exec(self.viewport().mapToGlobal(pos))
            if chosen == act_nav:
                self.directory_changed.emit(path)
            elif chosen == act_bookmark:
                self.add_bookmark(path)
            elif chosen == act_staging:
                self._add_dir_files_to_staging(path)
            elif chosen == act_rename:
                self.rename_folder(item)
            elif chosen == act_delete:
                self.delete_folder(item)
            elif chosen == act_reveal:
                self._reveal_in_explorer(path)
            return

        if itype == "session":
            act_import = menu.addAction("Import into Current Session")
            act_new = menu.addAction("Open in New App Instance")
            menu.addSeparator()
            act_reveal = menu.addAction("Reveal in File Explorer")

            chosen = menu.exec(self.viewport().mapToGlobal(pos))
            if chosen == act_import:
                self.session_import_requested.emit(path)
            elif chosen == act_new:
                self.session_new_instance_requested.emit(path)
            elif chosen == act_reveal:
                self._reveal_in_explorer(path)
            return

        # General media or sequence
        act_open = menu.addAction("Open in Viewport")
        act_add_staging = menu.addAction("Add to Temporary List")
        act_add_bin = menu.addAction("Add to Source Bin")
        menu.addSeparator()
        act_reveal = menu.addAction("Reveal in File Explorer")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_open:
            self.media_open_requested.emit(selected_paths[0])
        elif chosen == act_add_staging:
            self.media_add_to_staging_requested.emit(selected_paths)
        elif chosen == act_add_bin:
            self.media_add_to_bin_requested.emit(selected_paths)
        elif chosen == act_reveal:
            self._reveal_in_explorer(selected_paths[0])

    def rename_folder(self, item: QTreeWidgetItem) -> None:
        """Rename directory with prompt dialog."""
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not old_path or not os.path.isdir(old_path):
            return

        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "New folder name:", text=old_name)
        if ok and new_name and new_name.strip() and new_name != old_name:
            parent_dir = os.path.dirname(old_path)
            new_path = os.path.join(parent_dir, new_name.strip())
            try:
                os.rename(old_path, new_path)
                self.load_directory(self._current_directory)
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", f"Could not rename folder:\n{e}")

    def delete_folder(self, item: QTreeWidgetItem) -> None:
        """Permanently delete folder after confirmation dialog."""
        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or not os.path.isdir(dir_path):
            return

        folder_name = os.path.basename(dir_path)
        ans = QMessageBox.warning(
            self,
            "Confirm Delete Folder",
            f"Are you sure you want to permanently delete the folder:\n'{folder_name}'\n\nPath: {dir_path}\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(dir_path)
                self.load_directory(self._current_directory)
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Could not delete folder:\n{e}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        items = self.selectedItems()
        if items:
            item = items[0]
            itype = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if event.key() == Qt.Key.Key_F2 and itype == "dir":
                self.rename_folder(item)
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and itype == "dir":
                self.delete_folder(item)
                event.accept()
                return

        super().keyPressEvent(event)

    def _add_dir_files_to_staging(self, dir_path: str) -> None:
        files = []
        try:
            for entry in os.scandir(dir_path):
                if entry.is_file():
                    files.append(entry.path)
        except OSError:
            pass
        if files:
            self.media_add_to_staging_requested.emit(files)

    # --------------------------------------------------------------------------
    # Bookmarks Operations
    # --------------------------------------------------------------------------
    def add_bookmark(self, folder_path: str, name: Optional[str] = None) -> None:
        if not folder_path or not os.path.isdir(folder_path):
            return
        b_name = name or os.path.basename(folder_path) or folder_path
        pref_mgr = PreferencesManager.instance()
        b_list = list(getattr(pref_mgr.preferences, "file_browser_bookmarks", []))

        # Avoid exact duplicate paths
        if any(b.get("path") == folder_path for b in b_list):
            return

        b_list.append({"name": b_name, "path": folder_path})
        pref_mgr.preferences.file_browser_bookmarks = b_list
        pref_mgr.save_preferences()

        self.load_directory(self._current_directory)

    def _rename_bookmark(self, item: QTreeWidgetItem) -> None:
        cur_name = item.data(0, Qt.ItemDataRole.UserRole + 2)
        cur_path = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename Bookmark", "Bookmark Name:", text=cur_name)
        if ok and new_name.strip():
            pref_mgr = PreferencesManager.instance()
            b_list = list(getattr(pref_mgr.preferences, "file_browser_bookmarks", []))
            for b in b_list:
                if b.get("path") == cur_path:
                    b["name"] = new_name.strip()
                    break
            pref_mgr.preferences.file_browser_bookmarks = b_list
            pref_mgr.save_preferences()
            self.load_directory(self._current_directory)

    def _reorder_bookmark(self, item: QTreeWidgetItem, delta: int) -> None:
        cur_path = item.data(0, Qt.ItemDataRole.UserRole)
        pref_mgr = PreferencesManager.instance()
        b_list = list(getattr(pref_mgr.preferences, "file_browser_bookmarks", []))
        idx = next((i for i, b in enumerate(b_list) if b.get("path") == cur_path), -1)
        if idx >= 0:
            target_idx = idx + delta
            if 0 <= target_idx < len(b_list):
                b_list[idx], b_list[target_idx] = b_list[target_idx], b_list[idx]
                pref_mgr.preferences.file_browser_bookmarks = b_list
                pref_mgr.save_preferences()
                self.load_directory(self._current_directory)

    def _remove_bookmark(self, item: QTreeWidgetItem) -> None:
        cur_path = item.data(0, Qt.ItemDataRole.UserRole)
        pref_mgr = PreferencesManager.instance()
        b_list = [b for b in getattr(pref_mgr.preferences, "file_browser_bookmarks", []) if b.get("path") != cur_path]
        pref_mgr.preferences.file_browser_bookmarks = b_list
        pref_mgr.save_preferences()
        self.load_directory(self._current_directory)

    def _reveal_in_explorer(self, target_path: str) -> None:
        """Reveal file or folder in OS file manager."""
        from openreview.core.system_utils import reveal_in_os_file_manager
        reveal_in_os_file_manager(target_path)


# ==============================================================================
# Temporary Staging Widget
# ==============================================================================

class TemporaryStagingWidget(QWidget):
    """
    Temporary Staging List widget for queuing selected media files.
    Allows reviewing, removing unwanted items, and batch-adding to the Source Bin.
    """
    media_add_to_bin_requested = Signal(list)
    media_open_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_title = QLabel("Temporary Staging List (0)")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #e5a823; font-size: 11px;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_remove.setToolTip("Remove selected items from list (Delete key)")
        self.btn_remove.clicked.connect(self._on_remove_selected)
        header_layout.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_clear.setToolTip("Clear all staged items")
        self.btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(self.btn_clear)

        layout.addLayout(header_layout)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemDoubleClicked.connect(lambda item: self.media_open_requested.emit(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.list_widget, stretch=1)

        self.btn_add_to_bin = QPushButton("Add to Source Bin")
        self.btn_add_to_bin.setFixedHeight(30)
        self.btn_add_to_bin.setStyleSheet("""
            QPushButton {
                background-color: #2c281e;
                color: #e5a823;
                border: 1px solid #e5a823;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e5a823;
                color: #141414;
            }
            QPushButton:disabled {
                background-color: #1f1f1f;
                color: #555555;
                border: 1px solid #333333;
            }
        """)
        self.btn_add_to_bin.clicked.connect(self._on_add_to_bin_clicked)
        self.btn_add_to_bin.setEnabled(False)
        layout.addWidget(self.btn_add_to_bin)

    def add_paths(self, paths: List[str]) -> None:
        """Add media paths into the staging list avoiding duplicates."""
        existing_paths = {self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())}
        for p in paths:
            if not p or p in existing_paths:
                continue
            item = QListWidgetItem(self.list_widget)
            item.setText(os.path.basename(p))
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
            existing_paths.add(p)

        self._update_counter()

    def get_all_paths(self) -> List[str]:
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]

    def clear(self) -> None:
        self.list_widget.clear()
        self._update_counter()

    def _on_remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self._update_counter()

    def _on_add_to_bin_clicked(self) -> None:
        paths = self.get_all_paths()
        if paths:
            self.media_add_to_bin_requested.emit(paths)
            self.clear()

    def _update_counter(self) -> None:
        count = self.list_widget.count()
        self.lbl_title.setText(f"Temporary Staging List ({count})")
        self.btn_add_to_bin.setEnabled(count > 0)
        self.btn_remove.setEnabled(count > 0)
        self.btn_clear.setEnabled(count > 0)

    def _on_context_menu(self, pos: QPoint) -> None:
        if not self.list_widget.selectedItems():
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open in Viewport")
        act_remove = menu.addAction("Remove from List")
        menu.addSeparator()
        act_clear = menu.addAction("Clear All")

        chosen = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if chosen == act_open:
            item = self.list_widget.selectedItems()[0]
            self.media_open_requested.emit(item.data(Qt.ItemDataRole.UserRole))
        elif chosen == act_remove:
            self._on_remove_selected()
        elif chosen == act_clear:
            self.clear()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._on_remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)


# ==============================================================================
# File Browser Panel Widget
# ==============================================================================

class FileBrowserPanelWidget(QWidget):
    """
    Main interactive File Browser Panel containing:
    1. Navigation Bar with Drive selector, Back, Up, Dynamic Breadcrumbs, Sequence toggle, Bookmark, Refresh.
    2. Spotlight Search filter bar with instant query matching and recursive subfolder toggle.
    3. Splitter holding FileBrowserTreeWidget (with Bookmarks pinned on top) and TemporaryStagingWidget.
    """
    media_open_requested = Signal(str)
    media_add_to_bin_requested = Signal(list)
    session_import_requested = Signal(str)
    session_new_instance_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._history: List[str] = []
        self._history_idx: int = -1

        self._setup_ui()
        self._init_default_location()

    def _setup_ui(self) -> None:
        panel_css = """
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QTreeWidget, QListWidget {
                background-color: #141414;
                border: 1px solid #2e2e2e;
                color: #cccccc;
                font-size: 12px;
            }
            QTreeWidget::item, QListWidget::item {
                padding: 3px 2px;
                border-bottom: 1px solid #1f1f1f;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #2c281e;
                color: #e5a823;
                font-weight: bold;
            }
            QTreeWidget::item:hover, QListWidget::item:hover {
                background-color: #242424;
            }
            QHeaderView::section {
                background-color: #222222;
                color: #888888;
                padding: 4px;
                border: 1px solid #2e2e2e;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                background-color: #222222;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton, QToolButton {
                background-color: #252525;
                border: 1px solid #383838;
                color: #cccccc;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #333333;
                color: #e5a823;
                border-color: #e5a823;
            }
            /* Modern minimal rounded scrollbars */
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3d3d3d;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed {
                background: #e5a823;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #3d3d3d;
                min-width: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed {
                background: #e5a823;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            QScrollBar::corner {
                background: transparent;
            }
        """
        from openreview.ui.theme import get_spinbox_arrow_stylesheet
        self.setStyleSheet(panel_css + get_spinbox_arrow_stylesheet())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. Row 1: Navigation Controls Bar
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        self.combo_drives = QComboBox()
        self.combo_drives.setFixedWidth(65)
        for d in get_available_drives():
            self.combo_drives.addItem(d)
        self.combo_drives.currentTextChanged.connect(self._on_drive_changed)
        nav_layout.addWidget(self.combo_drives)

        self.btn_back = QToolButton()
        self.btn_back.setText("◀")
        self.btn_back.setToolTip("Back in history")
        self.btn_back.clicked.connect(self._on_navigate_back)
        nav_layout.addWidget(self.btn_back)

        self.btn_up = QToolButton()
        self.btn_up.setText("▲")
        self.btn_up.setToolTip("Up to parent folder")
        self.btn_up.clicked.connect(self._on_navigate_up)
        nav_layout.addWidget(self.btn_up)

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("⟳")
        self.btn_refresh.setToolTip("Refresh current directory")
        self.btn_refresh.clicked.connect(self.refresh)
        nav_layout.addWidget(self.btn_refresh)

        nav_layout.addStretch()

        # Sequence Grouping Checkbox
        self.chk_seq = QCheckBox("Seq")
        self.chk_seq.setToolTip("Group numbered frame sequences into single entries")
        self.chk_seq.setChecked(True)
        self.chk_seq.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self.chk_seq.toggled.connect(self._on_group_sequences_toggled)
        nav_layout.addWidget(self.chk_seq)

        # Quick Bookmark button
        self.btn_bookmark = QToolButton()
        self.btn_bookmark.setText("★")
        self.btn_bookmark.setToolTip("Bookmark current folder")
        self.btn_bookmark.clicked.connect(self._on_bookmark_current_folder)
        nav_layout.addWidget(self.btn_bookmark)

        main_layout.addLayout(nav_layout)

        # 2. Row 2: Dynamic Breadcrumb Bar (Dedicated full-width row)
        self.breadcrumbs = BreadcrumbBarWidget(self)
        self.breadcrumbs.path_changed.connect(lambda p: self.navigate_to(p))
        main_layout.addWidget(self.breadcrumbs)

        # 3. Row 3: Spotlight Quick Search Bar
        self.spotlight = SpotlightSearchWidget(self)
        self.spotlight.search_changed.connect(self._on_search_changed)
        main_layout.addWidget(self.spotlight)

        # 4. Vertical Splitter with liquid 6px handle
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setOpaqueResize(True)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #232323;
                height: 6px;
            }
            QSplitter::handle:hover {
                background-color: #e5a823;
            }
        """)

        self.tree = FileBrowserTreeWidget(self.splitter)
        self.tree.media_open_requested.connect(self.media_open_requested.emit)
        self.tree.media_add_to_bin_requested.connect(self.media_add_to_bin_requested.emit)
        self.tree.media_add_to_staging_requested.connect(self._on_add_to_staging)
        self.tree.session_import_requested.connect(self.session_import_requested.emit)
        self.tree.session_new_instance_requested.connect(self.session_new_instance_requested.emit)
        self.tree.directory_changed.connect(self.navigate_to)
        self.splitter.addWidget(self.tree)

        self.staging = TemporaryStagingWidget(self.splitter)
        self.staging.media_open_requested.connect(self.media_open_requested.emit)
        self.staging.media_add_to_bin_requested.connect(self.media_add_to_bin_requested.emit)
        self.splitter.addWidget(self.staging)

        self.splitter.setSizes([450, 180])
        main_layout.addWidget(self.splitter, stretch=1)

    def _init_default_location(self) -> None:
        """Start in current working directory or user home."""
        start_dir = os.getcwd()
        if not os.path.exists(start_dir):
            start_dir = str(Path.home())
        self.navigate_to(start_dir)

    def navigate_to(self, dir_path: str, add_to_history: bool = True) -> None:
        """Navigate the tree and breadcrumbs to the specified folder path."""
        norm_path = os.path.abspath(dir_path)
        if not os.path.exists(norm_path) or not os.path.isdir(norm_path):
            return

        if add_to_history:
            if self._history_idx < len(self._history) - 1:
                self._history = self._history[:self._history_idx + 1]
            self._history.append(norm_path)
            self._history_idx = len(self._history) - 1

        self.breadcrumbs.set_path(norm_path)
        self.tree.load_directory(norm_path)

        drive = os.path.splitdrive(norm_path)[0]
        if drive:
            drive_root = drive + "\\" if sys.platform.startswith("win") else drive
            idx = self.combo_drives.findText(drive_root, Qt.MatchFlag.MatchStartsWith)
            if idx >= 0:
                self.combo_drives.blockSignals(True)
                self.combo_drives.setCurrentIndex(idx)
                self.combo_drives.blockSignals(False)

        self._update_nav_buttons()

    def refresh(self) -> None:
        cur = self.breadcrumbs.get_path()
        if cur and os.path.isdir(cur):
            self.tree.load_directory(cur)

    def _on_drive_changed(self, drive_path: str) -> None:
        if drive_path and os.path.exists(drive_path):
            self.navigate_to(drive_path)

    def _on_navigate_back(self) -> None:
        if self._history_idx > 0:
            self._history_idx -= 1
            prev_dir = self._history[self._history_idx]
            self.navigate_to(prev_dir, add_to_history=False)

    def _on_navigate_up(self) -> None:
        cur = self.breadcrumbs.get_path()
        if not cur:
            return
        parent_dir = os.path.dirname(os.path.abspath(cur))
        if parent_dir and parent_dir != cur and os.path.exists(parent_dir):
            self.navigate_to(parent_dir)

    def _on_group_sequences_toggled(self, checked: bool) -> None:
        self.tree.set_group_sequences(checked)
        if getattr(self.tree, "_current_query", ""):
            self.tree.filter_items(self.tree._current_query, getattr(self.tree, "_recursive_search", False))
        else:
            self.refresh()

    def _on_bookmark_current_folder(self) -> None:
        cur = self.breadcrumbs.get_path()
        if cur and os.path.isdir(cur):
            self.tree.add_bookmark(cur)

    def _on_search_changed(self, query: str, recursive: bool) -> None:
        self.tree.filter_items(query, recursive)

    def _on_add_to_staging(self, paths: List[str]) -> None:
        self.staging.add_paths(paths)

    def _update_nav_buttons(self) -> None:
        self.btn_back.setEnabled(self._history_idx > 0)
        cur = self.breadcrumbs.get_path()
        parent_dir = os.path.dirname(os.path.abspath(cur)) if cur else ""
        self.btn_up.setEnabled(bool(parent_dir and parent_dir != cur and os.path.exists(parent_dir)))


# ==============================================================================
# Host Dock Widget
# ==============================================================================

class FileBrowserDockWidget(QDockWidget):
    """
    Host QDockWidget for the Inbuilt File Browser.
    Restricted strictly to Left and Right dock areas, defaulted on the Right.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("File Browser", parent)
        self.setObjectName("FileBrowserDockWidget")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setTitleBarWidget(TabbedDockTitleBar(self))
        self.panel = FileBrowserPanelWidget(self)
        self.setWidget(self.panel)

    def __getattr__(self, name):
        if hasattr(self, "panel") and hasattr(self.panel, name):
            return getattr(self.panel, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
