"""
Tests for OpenReview Option 3: Annotation Manager & Markup Export.
Covers AnnotationStore enhancements, JSON/CSV/Markdown reports,
AnnotationManagerDialog UI and interactions, and MainWindow integration.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from openreview.models.annotations import (
    AnnotationStore,
    Stroke,
    ShapeType,
    frame_to_timecode,
)
from openreview.core.clock import PlaybackClock
from openreview.ui.annotation_manager_dialog import AnnotationManagerDialog
from openreview.ui.main_window import MainWindow


def test_annotation_store_notes_and_shapes():
    """Verify notes, stroke breakdown, and counting in AnnotationStore."""
    store = AnnotationStore()
    assert not store.has_annotations(1001)
    assert store.get_annotated_frames() == []

    # 1. Add pen stroke and arrow stroke
    store.add_stroke(1001, Stroke(shape_type=ShapeType.PEN, points=[(0.1, 0.1), (0.2, 0.2)]))
    store.add_stroke(1001, Stroke(shape_type=ShapeType.ARROW, points=[(0.2, 0.2), (0.4, 0.4)]))
    assert store.has_annotations(1001)
    assert store.get_stroke_count(1001) == 2
    counts = store.get_shape_counts(1001)
    assert counts.get("pen") == 1
    assert counts.get("arrow") == 1

    # 2. Add text note on frame 1001
    store.set_frame_note(1001, "Fix edge chatter on helmet")
    assert store.get_frame_note(1001) == "Fix edge chatter on helmet"
    assert store.get_annotated_frames() == [1001]

    # 3. Add note-only frame on 1050
    store.set_frame_note(1050, "Director approved timing")
    assert store.has_annotations(1050)
    assert store.get_annotated_frames() == [1001, 1050]
    assert store.get_stroke_count(1050) == 0

    # 4. Clear frame
    store.clear_frame(1001, clear_note=False)
    assert store.get_stroke_count(1001) == 0
    assert store.get_frame_note(1001) == "Fix edge chatter on helmet"

    store.clear_frame(1001, clear_note=True)
    assert not store.has_annotations(1001)
    assert store.get_annotated_frames() == [1050]


def test_annotation_store_json_export_import(tmp_path):
    """Test exporting to and importing from JSON vector markup files."""
    store = AnnotationStore()
    store.add_stroke(1010, Stroke(shape_type=ShapeType.RECTANGLE, points=[(0.1, 0.1), (0.5, 0.5)]))
    store.set_frame_note(1010, "Highlight cleanup area")

    store.add_stroke(1020, Stroke(shape_type=ShapeType.CIRCLE, points=[(0.3, 0.3), (0.7, 0.7)]))
    store.set_frame_note(1020, "VFX explosion center")

    json_path = tmp_path / "markup.json"
    store.export_to_json(json_path)
    assert json_path.exists()

    # Load and verify JSON contents
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "1010" in data
    assert "1020" in data
    assert data["__notes__"]["1010"] == "Highlight cleanup area"

    # Restore in new store
    new_store = AnnotationStore()
    new_store.import_from_json(json_path)
    assert new_store.get_annotated_frames() == [1010, 1020]
    assert new_store.get_stroke_count(1010) == 1
    assert new_store.get_frame_note(1010) == "Highlight cleanup area"
    assert new_store.get_frame_note(1020) == "VFX explosion center"


def test_annotation_store_markdown_and_csv_reports():
    """Verify Markdown and CSV dailies report generation."""
    store = AnnotationStore()
    store.add_stroke(1001, Stroke(shape_type=ShapeType.PEN, points=[(0.0, 0.0), (0.1, 0.1)]))
    store.set_frame_note(1001, "Fix boom mic in top left")

    md_report = store.generate_report_markdown(fps=24.0)
    assert "# OpenReview - Annotation & Review Notes Report" in md_report
    assert "Fix boom mic in top left" in md_report
    assert "1001" in md_report

    csv_report = store.generate_report_csv(fps=24.0)
    assert "Frame,Timecode,Stroke Count,Shape Breakdown,Review Note" in csv_report
    assert "1001" in csv_report
    assert "Fix boom mic in top left" in csv_report


def test_annotation_manager_dialog_ui(qtbot, monkeypatch):
    """Test AnnotationManagerDialog table population, selection, and frame jumping."""
    store = AnnotationStore()
    store.add_stroke(1015, Stroke(shape_type=ShapeType.ARROW, points=[(0.2, 0.2), (0.4, 0.4)]))
    store.set_frame_note(1015, "Check continuity")

    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=24.0)
    clock.set_current_frame(1001)

    dlg = AnnotationManagerDialog(store, clock)
    qtbot.addWidget(dlg)
    dlg.show()

    # Verify table has 1 row
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 0).text() == "1015"
    assert "Check continuity" in dlg.table.item(0, 4).text()

    # Select row and verify note edit updates
    dlg.table.selectRow(0)
    assert dlg.edit_note.toPlainText() == "Check continuity"

    # Test typing new note
    dlg.edit_note.setPlainText("Updated continuity note")
    dlg.btn_save_note.click()
    assert store.get_frame_note(1015) == "Updated continuity note"

    # Test Jump to Frame
    dlg.btn_jump.click()
    assert clock.current_frame == 1015

    # Test Clear Frame (mock QMessageBox to answer Yes)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    dlg.btn_clear_frame.click()
    assert not store.has_annotations(1015)
    assert dlg.table.rowCount() == 0

    dlg.close()


def test_annotation_manager_export_workflow(qtbot, monkeypatch, tmp_path):
    """Test dialog export button triggering file writes."""
    store = AnnotationStore()
    store.add_stroke(1005, Stroke(shape_type=ShapeType.PEN, points=[(0.1, 0.1), (0.2, 0.2)]))
    store.set_frame_note(1005, "Review render passes")

    clock = PlaybackClock(start_frame=1001, end_frame=1100, fps=24.0)
    dummy_render = lambda f: np.zeros((100, 100, 3), dtype=np.uint8)

    dlg = AnnotationManagerDialog(store, clock, render_frame_callback=dummy_render)
    qtbot.addWidget(dlg)

    # 1. Export JSON
    target_json = tmp_path / "notes.json"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_json), "JSON Vector Annotations (*.json)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    dlg._on_export_clicked()
    assert target_json.exists()

    # 2. Export Markdown Report
    target_md = tmp_path / "notes.md"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_md), "Markdown Review Report (*.md)"),
    )
    dlg._on_export_clicked()
    assert target_md.exists()
    assert "Review render passes" in target_md.read_text(encoding="utf-8")

    # 3. Export PDF with PNG frames prompt accepted
    target_pdf = tmp_path / "review_sheet.pdf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_pdf), "PDF Review Sheet (*.pdf)"),
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    dlg._on_export_clicked()
    assert target_pdf.exists()
    png_dir = tmp_path / "review_sheet_frames"
    assert png_dir.exists()
    assert (png_dir / "frame_1005.png").exists()

    dlg.close()


def test_main_window_annotation_integration(qtbot, monkeypatch):
    """Test MainWindow annotation menu, tools toggle, and mark annotated frames."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()

    # 1. Toggle annotation palette (off by default, toggled with X)
    assert not win.markup_palette.isVisible()
    win._on_toggle_annotation_tools()
    assert win.markup_palette.isVisible()
    win._on_toggle_annotation_tools()
    assert not win.markup_palette.isVisible()

    # 2. Add annotation to current frame
    win.clock.set_current_frame(1010)
    win.annotation_store.add_stroke(
        1010, Stroke(shape_type=ShapeType.PEN, points=[(0.1, 0.1), (0.2, 0.2)])
    )
    win.clock.set_current_frame(1025)
    win.annotation_store.add_stroke(
        1025, Stroke(shape_type=ShapeType.LINE, points=[(0.3, 0.3), (0.5, 0.5)])
    )

    # 3. Mark Annotated Frames
    win._on_mark_annotated_frames()
    assert 1010 in win.clock.bookmarks
    assert 1025 in win.clock.bookmarks

    # 4. Next / Prev Keyframe navigation
    win.clock.set_current_frame(1005)
    win._on_next_keyframe()
    assert win.clock.current_frame == 1010
    win._on_next_keyframe()
    assert win.clock.current_frame == 1025
    win._on_prev_keyframe()
    assert win.clock.current_frame == 1010

    # 5. Clear all annotations with prompt
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    win._on_clear_all_annotations()
    assert len(win.annotation_store.get_annotated_frames()) == 0

    win.close()
