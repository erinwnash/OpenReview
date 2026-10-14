"""
Unit tests for image sequence auto-detection and gap-tolerant reader.
"""
import os
import tempfile
import pytest
from PIL import Image

from openreview.core.sequence_parser import (
    detect_image_sequence,
    DiskSequenceReader,
    SequenceInfo,
)


def test_sequence_auto_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy sequence: shot.1001.png, shot.1002.png, shot.1005.png (gap: 1003, 1004)
        for frame in [1001, 1002, 1005]:
            img = Image.new("RGBA", (32, 32), color=(100, 100, 100, 255))
            fpath = os.path.join(tmpdir, f"shot_comp.{frame:04d}.png")
            img.save(fpath)

        # Detect by passing one file path
        sample_path = os.path.join(tmpdir, "shot_comp.1002.png")
        seq = detect_image_sequence(sample_path)

        assert seq is not None
        assert seq.prefix == "shot_comp"
        assert seq.separator == "."
        assert seq.padding == 4
        assert seq.extension == ".png"
        assert seq.start_frame == 1001
        assert seq.end_frame == 1005
        assert seq.available_frames == {1001, 1002, 1005}
        assert seq.missing_frames == {1003, 1004}

        # Test pattern formatting
        assert "####" in seq.hash_pattern
        assert "%04d" in seq.pattern

        # Test reader with gap tolerance
        reader = DiskSequenceReader(seq)
        f1001 = reader.read_frame(1001)
        assert f1001 is not None
        assert f1001.shape == (32, 32, 4)

        # Frame 1003 is missing in gap: should hold previous frame data
        f1003 = reader.read_frame(1003)
        assert f1003 is not None
        assert f1003.shape == (32, 32, 4)


def test_single_file_not_sequence():
    with tempfile.TemporaryDirectory() as tmpdir:
        single_path = os.path.join(tmpdir, "texture_diffuse.png")
        img = Image.new("RGBA", (16, 16))
        img.save(single_path)

        seq = detect_image_sequence(single_path)
        assert seq is None
