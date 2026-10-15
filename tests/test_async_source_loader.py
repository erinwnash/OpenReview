"""
Unit tests for AsyncSourceLoader and batch source addition in SessionGraph.
"""
import os
import tempfile
import numpy as np
from PIL import Image
from PySide6.QtCore import QCoreApplication

from openreview.core.async_source_loader import AsyncSourceLoader
from openreview.models.session_graph import SessionGraph, SourceItem, build_source_item_from_path


def _create_dummy_image(path: str):
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 255))
    img.save(path)


def test_build_source_item_from_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "test_shot.1001.png")
        _create_dummy_image(img_path)

        item = build_source_item_from_path(img_path)
        assert item is not None
        assert item.name == "test_shot.1001.png"
        assert item.media_type in ("still", "sequence")


def test_session_graph_add_sources_batch():
    graph = SessionGraph()
    signals_received = []
    graph.graph_changed.connect(lambda: signals_received.append(True))

    item1 = SourceItem(name="shot1", path="/fake/shot1.png")
    item2 = SourceItem(name="shot2", path="/fake/shot2.png")
    item3 = SourceItem(name="shot3", path="/fake/shot3.png")

    added = graph.add_sources_batch([item1, item2, item3])
    assert len(added) == 3
    # Crucial: only ONE graph_changed signal emission for all 3 items!
    assert len(signals_received) == 1
    assert item1.id in graph.sources
    assert item2.id in graph.sources
    assert item3.id in graph.sources


def test_async_source_loader_process():
    app = QCoreApplication.instance() or QCoreApplication([])

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(3):
            p = os.path.join(tmpdir, f"file_{i}.png")
            _create_dummy_image(p)
            paths.append(p)

        loader = AsyncSourceLoader()
        discovered = []
        completed = []

        loader.source_discovered.connect(lambda item, cur, tot: discovered.append(item))
        loader.batch_completed.connect(lambda batch: completed.extend(batch))

        loader.load_paths_async(paths)

        # Process Qt events until completed
        timeout_loops = 100
        while len(completed) < 3 and timeout_loops > 0:
            app.processEvents()
            QCoreApplication.processEvents()
            timeout_loops -= 1
            import time
            time.sleep(0.02)

        assert len(completed) == 3
        assert len(discovered) == 3
