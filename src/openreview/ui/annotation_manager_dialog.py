"""
Annotation Manager Dialog for OpenReview.
Provides studio-grade inspection, review notes management, keyframe navigation,
and comprehensive export / import of frame-keyed vector annotations and dailies reports.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Callable
import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QTextEdit,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QComboBox,
    QProgressDialog,
    QApplication,
)

from openreview.models.annotations import AnnotationStore, frame_to_timecode
from openreview.core.clock import PlaybackClock
from openreview.core.exporter import MediaExporter


class AnnotationManagerWidget(QWidget):
    """
    Studio-grade Annotation & Markup Manager Widget.
    Lists all annotated keyframes, provides live frame jumping, per-frame notes,
    and multi-format export/import.
    """

    frame_jump_requested = Signal(int)
    annotations_cleared = Signal()

    def __init__(
        self,
        annotation_store: AnnotationStore,
        clock: PlaybackClock,
        render_frame_callback: Optional[Callable[[int], np.ndarray]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setMaximumHeight(520)

        self.store = annotation_store
        self.clock = clock
        self.render_frame_callback = render_frame_callback
        self._updating_table = False

        self._setup_ui()
        self._connect_signals()
        self.refresh_table()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1c;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #333333;
                margin-top: 6px;
                padding-top: 10px;
                color: #e5a823;
                font-weight: bold;
            }
            QLabel {
                color: #cccccc;
            }
            QTableWidget {
                background-color: #141414;
                border: 1px solid #2e2e2e;
                gridline-color: #262626;
                color: #e0e0e0;
                selection-background-color: #e5a823;
                selection-color: #121212;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #242424;
                color: #b0b0b0;
                padding: 4px;
                border: 1px solid #2e2e2e;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #121212;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 6px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #e5a823;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #e5a823;
            }
            QPushButton:pressed {
                background-color: #e5a823;
                color: #121212;
            }
            QPushButton#danger_btn:hover {
                border-color: #e74c3c;
                color: #ff6b6b;
            }
            QComboBox {
                background-color: #141414;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 4px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Info Banner
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        self.lbl_title = QLabel("Annotation & Markup Manager", self)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.lbl_title.setFont(font)
        self.lbl_title.setStyleSheet("color: #e5a823;")

        self.lbl_summary = QLabel("Loading annotated frames...", self)
        self.lbl_summary.setStyleSheet("color: #888888; font-size: 11px;")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_summary)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        from openreview.resources import get_vfx_icon

        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.setIcon(get_vfx_icon("refresh"))
        self.btn_refresh.clicked.connect(self.refresh_table)
        header_layout.addWidget(self.btn_refresh)
        main_layout.addLayout(header_layout)

        # Splitter: Table on top/left, Frame Notes & Details on bottom/right
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Top: Table of Keyframes
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Frame", "Timecode", "Strokes", "Breakdown", "Review Note"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        splitter.addWidget(self.table)

        # Bottom: Note Editor & Details
        bottom_widget = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 6, 0, 0)
        bottom_layout.setSpacing(6)

        note_header = QHBoxLayout()
        self.lbl_selected_frame = QLabel("Selected Frame: None", bottom_widget)
        self.lbl_selected_frame.setStyleSheet("font-weight: bold; color: #e5a823;")
        note_header.addWidget(self.lbl_selected_frame)
        note_header.addStretch()

        self.btn_save_note = QPushButton("Update Note", bottom_widget)
        self.btn_save_note.setIcon(get_vfx_icon("save"))
        self.btn_save_note.clicked.connect(self._on_save_current_note)
        note_header.addWidget(self.btn_save_note)
        bottom_layout.addLayout(note_header)

        self.edit_note = QTextEdit(bottom_widget)
        self.edit_note.setPlaceholderText("Type director review notes or dailies feedback for the selected frame here...")
        self.edit_note.textChanged.connect(self._on_note_text_changed)
        bottom_layout.addWidget(self.edit_note)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([320, 160])
        main_layout.addWidget(splitter)

        # Bottom Action Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        self.btn_jump = QPushButton("Jump to Frame", self)
        self.btn_jump.setToolTip("Seek timeline to selected annotated frame")
        self.btn_jump.clicked.connect(self._on_jump_clicked)
        btn_bar.addWidget(self.btn_jump)

        self.btn_clear_frame = QPushButton("Clear Frame", self)
        self.btn_clear_frame.setIcon(get_vfx_icon("delete"))
        self.btn_clear_frame.setObjectName("danger_btn")
        self.btn_clear_frame.setToolTip("Clear annotations on the selected frame")
        self.btn_clear_frame.clicked.connect(self._on_clear_selected_frame)
        btn_bar.addWidget(self.btn_clear_frame)

        self.btn_clear_all = QPushButton("Clear All...", self)
        self.btn_clear_all.setIcon(get_vfx_icon("delete"))
        self.btn_clear_all.setObjectName("danger_btn")
        self.btn_clear_all.setToolTip("Purge all annotations across the entire clip")
        self.btn_clear_all.clicked.connect(self._on_clear_all_clicked)
        btn_bar.addWidget(self.btn_clear_all)

        btn_bar.addStretch()

        self.btn_export = QPushButton("Export...", self)
        self.btn_export.setIcon(get_vfx_icon("export"))
        self.btn_export.setToolTip("Export annotations to JSON, Report, or Burned-in Images")
        self.btn_export.clicked.connect(self._on_export_clicked)
        btn_bar.addWidget(self.btn_export)

        self.btn_import = QPushButton("Import...", self)
        self.btn_import.setIcon(get_vfx_icon("import"))
        self.btn_import.setToolTip("Import vector annotations from JSON")
        self.btn_import.clicked.connect(self._on_import_clicked)
        btn_bar.addWidget(self.btn_import)

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self._on_close_clicked)
        btn_bar.addWidget(self.btn_close)

        main_layout.addLayout(btn_bar)

    def _on_close_clicked(self) -> None:
        p = self.parent()
        if p and hasattr(p, "close_panel"):
            p.close_panel()
        elif p and hasattr(p, "accept"):
            p.accept()
        else:
            self.close()

    def _connect_signals(self) -> None:
        self.store.annotations_changed.connect(self._on_store_changed)
        self.clock.frame_changed.connect(self._on_clock_frame_changed)

    def _on_store_changed(self, frame: int) -> None:
        if not self._updating_table:
            self.refresh_table()

    def _on_clock_frame_changed(self, frame: int) -> None:
        # Highlight current frame in table if present
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == str(frame):
                self.table.selectRow(row)
                break

    def refresh_table(self) -> None:
        """Populate keyframe table with all annotated frames."""
        self._updating_table = True
        try:
            frames = self.store.get_annotated_frames()
            self.table.setRowCount(len(frames))

            total_strokes = 0
            for row, f in enumerate(frames):
                st_count = self.store.get_stroke_count(f)
                total_strokes += st_count
                shapes = self.store.get_shape_counts(f)
                shapes_str = ", ".join(f"{k.capitalize()}: {v}" for k, v in shapes.items()) if shapes else "Note only"
                note = self.store.get_frame_note(f)
                tc = frame_to_timecode(f, self.clock.fps)

                # Col 0: Frame
                item_frame = QTableWidgetItem(str(f))
                item_frame.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, item_frame)

                # Col 1: Timecode
                item_tc = QTableWidgetItem(tc)
                item_tc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, item_tc)

                # Col 2: Strokes
                item_cnt = QTableWidgetItem(str(st_count))
                item_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, item_cnt)

                # Col 3: Breakdown
                item_shapes = QTableWidgetItem(shapes_str)
                self.table.setItem(row, 3, item_shapes)

                # Col 4: Review Note
                item_note = QTableWidgetItem(note)
                self.table.setItem(row, 4, item_note)

            self.lbl_summary.setText(
                f"{len(frames)} annotated keyframe(s) | {total_strokes} total stroke(s) | FPS: {self.clock.fps:.2f}"
            )

            # Re-select row if matching clock
            current_f = self.clock.current_frame
            selected = False
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).text() == str(current_f):
                    self.table.selectRow(row)
                    selected = True
                    break
            if not selected and self.table.rowCount() > 0:
                self.table.selectRow(0)
            elif self.table.rowCount() == 0:
                self.lbl_selected_frame.setText("Selected Frame: None")
                self.edit_note.clear()
        finally:
            self._updating_table = False

    def get_selected_frame(self) -> Optional[int]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _on_table_selection_changed(self) -> None:
        frame = self.get_selected_frame()
        if frame is not None:
            self.lbl_selected_frame.setText(f"Selected Frame: {frame} (Timecode: {frame_to_timecode(frame, self.clock.fps)})")
            note = self.store.get_frame_note(frame)
            self.edit_note.blockSignals(True)
            self.edit_note.setPlainText(note)
            self.edit_note.blockSignals(False)
        else:
            self.lbl_selected_frame.setText("Selected Frame: None")
            self.edit_note.blockSignals(True)
            self.edit_note.clear()
            self.edit_note.blockSignals(False)

    def _on_table_double_clicked(self, item: QTableWidgetItem) -> None:
        self._on_jump_clicked()

    def _on_jump_clicked(self) -> None:
        frame = self.get_selected_frame()
        if frame is not None:
            self.clock.set_frame(frame)
            self.frame_jump_requested.emit(frame)

    def _on_note_text_changed(self) -> None:
        frame = self.get_selected_frame()
        if frame is not None and not self._updating_table:
            text = self.edit_note.toPlainText()
            self.store.set_frame_note(frame, text)
            # Update row in table directly without full refresh
            selected = self.table.selectedItems()
            if selected:
                row = selected[0].row()
                self.table.item(row, 4).setText(text)

    def _on_save_current_note(self) -> None:
        frame = self.get_selected_frame()
        if frame is not None:
            text = self.edit_note.toPlainText()
            self.store.set_frame_note(frame, text)
            self.refresh_table()

    def _on_clear_selected_frame(self) -> None:
        frame = self.get_selected_frame()
        if frame is None:
            return
        reply = QMessageBox.question(
            self,
            "Clear Frame Annotations",
            f"Are you sure you want to clear annotations on frame {frame}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.clear_frame(frame, clear_note=True)
            self.refresh_table()

    def _on_clear_all_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear All Annotations",
            "Are you sure you want to permanently clear all annotations and review notes across all frames?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.clear_all()
            self.annotations_cleared.emit()
            self.refresh_table()

    def _on_export_clicked(self) -> None:
        """Handle comprehensive export (PNG frames default, structured PDF report, sequences, JSON, Markdown, CSV)."""
        frames = self.store.get_annotated_frames()
        if not frames:
            QMessageBox.information(self, "No Annotations", "There are no annotations or notes to export.")
            return

        file_types = (
            "Burned-in PNG Frames (*.png);;"
            "PDF Review Sheet (*.pdf);;"
            "Annotated Image Sequence (*.png);;"
            "JSON Vector Annotations (*.json);;"
            "Markdown Review Report (*.md);;"
            "CSV Review Notes (*.csv)"
        )
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Annotations & Review Notes",
            "annotated_frame.png",
            file_types,
        )
        if not path:
            return

        try:
            p = Path(path)
            if "PDF" in selected_filter or p.suffix.lower() == ".pdf":
                if not p.suffix:
                    p = p.with_suffix(".pdf")
                entries = []
                total_steps = len(frames) + 1
                progress = QProgressDialog("Rendering annotated frames...", "Cancel", 0, total_steps, self)
                progress.setWindowTitle("Exporting PDF Review Sheet")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)
                progress.setValue(0)

                canceled = False
                for idx, f in enumerate(frames):
                    progress.setValue(idx)
                    progress.setLabelText(f"Rendering frame {f} ({idx + 1} of {len(frames)})...")
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        canceled = True
                        break

                    img = self.render_frame_callback(f) if self.render_frame_callback else None
                    note = self.store.get_frame_note(f)
                    tc = frame_to_timecode(f, self.clock.fps)
                    st_cnt = self.store.get_stroke_count(f)
                    entries.append({
                        "frame": f,
                        "timecode": tc,
                        "note": note,
                        "strokes_count": st_cnt,
                        "image": img,
                    })

                if canceled:
                    progress.close()
                    QMessageBox.information(self, "Export Cancelled", "Export operation was cancelled.")
                    return

                progress.setLabelText("Compiling PDF review document...")
                progress.setValue(len(frames))
                QApplication.processEvents()

                pdf_path = MediaExporter.export_pdf_review_sheet(
                    output_pdf_path=p,
                    entries=entries,
                    title="OpenReview - VFX Review Sheet",
                    fps=self.clock.fps,
                )
                progress.setValue(total_steps)
                progress.close()

                # Exclusively ask user if they also want to export individual annotated frames as PNGs
                reply = QMessageBox.question(
                    self,
                    "Export PNG Frames?",
                    "Do you also want to export the individual annotated frames as PNG images?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                exported_png_msg = ""
                if reply == QMessageBox.StandardButton.Yes:
                    png_dir = p.parent / f"{p.stem}_frames"
                    png_dir.mkdir(parents=True, exist_ok=True)
                    saved_count = 0
                    png_progress = QProgressDialog("Saving PNG frames...", "Cancel", 0, len(entries), self)
                    png_progress.setWindowTitle("Exporting PNG Frames")
                    png_progress.setWindowModality(Qt.WindowModality.WindowModal)
                    png_progress.setMinimumDuration(0)

                    for idx, entry in enumerate(entries):
                        png_progress.setValue(idx)
                        f = entry["frame"]
                        png_progress.setLabelText(f"Saving frame_{f:04d}.png ({idx + 1} of {len(entries)})...")
                        QApplication.processEvents()
                        if png_progress.wasCanceled():
                            break
                        img = entry["image"]
                        if img is not None:
                            png_file = png_dir / f"frame_{f:04d}.png"
                            MediaExporter.save_image_file(img, png_file)
                            saved_count += 1
                    png_progress.setValue(len(entries))
                    png_progress.close()
                    exported_png_msg = f"\n\nAlso exported {saved_count} annotated PNG frames to:\n{png_dir}"

                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported structured PDF review sheet to:\n{pdf_path}{exported_png_msg}",
                )

            elif "Sequence" in selected_filter:
                if self.render_frame_callback:
                    out_dir = p.parent / (p.stem + "_sequence")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    seq_frames = list(range(self.clock.start_frame, self.clock.end_frame + 1))
                    progress = QProgressDialog("Exporting annotated sequence...", "Cancel", 0, len(seq_frames), self)
                    progress.setWindowTitle("Exporting Image Sequence")
                    progress.setWindowModality(Qt.WindowModality.WindowModal)
                    progress.setMinimumDuration(0)

                    count = 0
                    for idx, f in enumerate(seq_frames):
                        progress.setValue(idx)
                        progress.setLabelText(f"Rendering frame {f} ({idx + 1} of {len(seq_frames)})...")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            break
                        img = self.render_frame_callback(f)
                        out_file = out_dir / f"{p.stem}.{f:04d}.png"
                        MediaExporter.save_image_file(img, out_file)
                        count += 1
                    progress.setValue(len(seq_frames))
                    progress.close()
                    QMessageBox.information(
                        self, "Export Successful", f"Exported {count} frames of annotated sequence to:\n{out_dir}"
                    )
                else:
                    QMessageBox.warning(self, "Renderer Unavailable", "Direct frame render callback not available.")

            elif "Burned-in" in selected_filter or p.suffix.lower() == ".png":
                if self.render_frame_callback:
                    if len(frames) == 1:
                        img = self.render_frame_callback(frames[0])
                        out_file = p if p.suffix.lower() == ".png" else p.with_suffix(".png")
                        MediaExporter.save_image_file(img, out_file)
                        QMessageBox.information(
                            self, "Export Successful", f"Exported annotated frame {frames[0]} to:\n{out_file}"
                        )
                    else:
                        out_dir = p.parent / (p.stem + "_frames")
                        out_dir.mkdir(parents=True, exist_ok=True)
                        progress = QProgressDialog("Exporting burned-in PNG frames...", "Cancel", 0, len(frames), self)
                        progress.setWindowTitle("Exporting PNG Frames")
                        progress.setWindowModality(Qt.WindowModality.WindowModal)
                        progress.setMinimumDuration(0)

                        count = 0
                        for idx, f in enumerate(frames):
                            progress.setValue(idx)
                            progress.setLabelText(f"Rendering frame {f} ({idx + 1} of {len(frames)})...")
                            QApplication.processEvents()
                            if progress.wasCanceled():
                                break
                            img = self.render_frame_callback(f)
                            out_file = out_dir / f"annotated.{f:04d}.png"
                            MediaExporter.save_image_file(img, out_file)
                            count += 1
                        progress.setValue(len(frames))
                        progress.close()
                        QMessageBox.information(
                            self, "Export Successful", f"Exported {count} burned-in frames to:\n{out_dir}"
                        )
                else:
                    QMessageBox.warning(self, "Renderer Unavailable", "Direct viewport render callback not available.")

            elif "JSON" in selected_filter or p.suffix.lower() == ".json":
                self.store.export_to_json(p)
                QMessageBox.information(self, "Export Successful", f"Exported vector annotations to:\n{p}")
            elif "Markdown" in selected_filter or p.suffix.lower() == ".md":
                md_content = self.store.generate_report_markdown(self.clock.fps)
                p.write_text(md_content, encoding="utf-8")
                QMessageBox.information(self, "Export Successful", f"Exported Markdown review report to:\n{p}")
            elif "CSV" in selected_filter or p.suffix.lower() == ".csv":
                csv_content = self.store.generate_report_csv(self.clock.fps)
                p.write_text(csv_content, encoding="utf-8")
                QMessageBox.information(self, "Export Successful", f"Exported CSV review notes to:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export annotations:\n{e}")

    def _on_import_clicked(self) -> None:
        """Handle importing vector annotations and notes from JSON."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Annotations",
            "",
            "JSON Vector Annotations (*.json);;All Files (*.*)",
        )
        if not path:
            return

        try:
            count = self.store.import_from_json(path, merge=True)
            self.refresh_table()
            QMessageBox.information(
                self, "Import Successful", f"Successfully imported annotations for {count} frame(s)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import annotations:\n{e}")


class AnnotationManagerDialog(QDialog):
    """Studio Annotation Manager Dialog wrapper for standalone window usage."""

    frame_jump_requested = Signal(int)
    annotations_cleared = Signal()

    def __init__(
        self,
        annotation_store: AnnotationStore,
        clock: PlaybackClock,
        render_frame_callback: Optional[Callable[[int], np.ndarray]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Annotation Manager - OpenReview")
        self.resize(760, 540)
        self.setStyleSheet("background-color: #1c1c1c;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.widget = AnnotationManagerWidget(
            annotation_store, clock, render_frame_callback, self
        )
        self.widget.frame_jump_requested.connect(self.frame_jump_requested.emit)
        self.widget.annotations_cleared.connect(self.annotations_cleared.emit)
        layout.addWidget(self.widget)

    def __getattr__(self, name):
        if name != "widget" and hasattr(self, "widget"):
            return getattr(self.widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def refresh_table(self) -> None:
        self.widget.refresh_table()


