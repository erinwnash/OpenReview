import os
import numpy as np
import pytest
from pathlib import Path
from PIL import Image

from openreview.core.clock import PlaybackClock
from openreview.core.exporter import MediaExporter
from openreview.ui.export_dialog import ExportDialog


def test_export_image_file(tmp_path):
    img_data = np.zeros((100, 100, 3), dtype=np.uint8)
    img_data[:, :, 0] = 255  # Solid Red

    out_file = tmp_path / "frame.png"
    MediaExporter.save_image_file(img_data, out_file)

    assert out_file.exists()
    loaded = Image.open(out_file)
    assert loaded.size == (100, 100)
    assert loaded.getpixel((50, 50)) == (255, 0, 0)


def test_export_sequence(tmp_path):
    def frame_gen(f: int) -> np.ndarray:
        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        arr[:, :, 1] = min(255, f * 20)  # Green varies
        return arr

    out_dir = tmp_path / "seq"
    frames = [1, 2, 3]
    out_files = MediaExporter.export_sequence(
        frame_provider=frame_gen,
        frames=frames,
        output_dir=out_dir,
        filename_prefix="test_shot",
        file_ext="png",
        pad=4,
    )

    assert len(out_files) == 3
    for f in out_files:
        assert Path(f).exists()
    assert (out_dir / "test_shot.0001.png").exists()
    assert (out_dir / "test_shot.0002.png").exists()
    assert (out_dir / "test_shot.0003.png").exists()


def test_export_video(tmp_path):
    def frame_gen(f: int) -> np.ndarray:
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[:, :, 2] = 200  # Blue
        return arr

    out_video = tmp_path / "test_movie.mp4"
    frames = [1, 2, 3, 4, 5]
    res_path = MediaExporter.export_video(
        frame_provider=frame_gen,
        frames=frames,
        output_path=out_video,
        fps=24.0,
    )

    assert Path(res_path).exists()
    assert os.path.getsize(res_path) > 0


def test_export_dialog_frame_ranges(qapp):
    clock = PlaybackClock(start_frame=1001, end_frame=1100)
    clock.set_in_out(1020, 1050)
    clock.set_frame(1035)

    marked = [1010, 1040]
    annotated = [1025, 1075]

    dlg = ExportDialog(clock, marked_frames=marked, annotated_frames=annotated)

    # Default is in_out
    assert dlg.get_selected_frames() == list(range(1020, 1051))

    # Full range
    dlg.combo_range.setCurrentIndex(1)  # full
    assert dlg.get_selected_frames() == list(range(1001, 1101))

    # Current frame
    dlg.combo_range.setCurrentIndex(2)  # current
    assert dlg.get_selected_frames() == [1035]

    # Marked frames
    dlg.combo_range.setCurrentIndex(3)  # marked
    assert dlg.get_selected_frames() == [1010, 1040]

    # Annotated frames
    dlg.combo_range.setCurrentIndex(4)  # annotated
    assert dlg.get_selected_frames() == [1025, 1075]

    # Custom range
    dlg.combo_range.setCurrentIndex(5)  # custom
    dlg.spin_custom_start.setValue(1015)
    dlg.spin_custom_end.setValue(1018)
    assert dlg.get_selected_frames() == [1015, 1016, 1017, 1018]
