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


def test_progressive_source_loader_lifecycle():
    from openreview.models.session_graph import create_proxy_source_item
    app = QCoreApplication.instance() or QCoreApplication([])

    # Test direct proxy generation
    proxy = create_proxy_source_item("/path/to/my_shot.exr", parent_folder_id="bin1")
    assert proxy.is_proxy is True
    assert proxy.proxy_resolved is False
    assert proxy.duration == 24
    assert proxy.name == "my_shot.exr"

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(2):
            p = os.path.join(tmpdir, f"clip_{i}.png")
            _create_dummy_image(p)
            paths.append(p)

        loader = AsyncSourceLoader()
        before_count = []
        proxies_created = []
        resolved_items = []
        after_batch = []

        loader.before_progressive_loading.connect(lambda cnt: before_count.append(cnt))
        loader.source_proxy_created.connect(lambda p_item, cur, tot: proxies_created.append(p_item))
        loader.source_resolved.connect(lambda pid, real_item: resolved_items.append((pid, real_item)))
        loader.after_progressive_loading.connect(lambda b: after_batch.extend(b))

        loader.load_paths_async(paths, use_progressive_proxies=True)

        # Proxies should be emitted immediately before worker processing
        assert len(before_count) == 1
        assert before_count[0] == 2
        assert len(proxies_created) == 2
        assert all(p.is_proxy for p in proxies_created)

        # Process Qt events until workers resolve
        timeout_loops = 100
        while len(resolved_items) < 2 and timeout_loops > 0:
            app.processEvents()
            QCoreApplication.processEvents()
            timeout_loops -= 1
            import time
            time.sleep(0.02)

        assert len(resolved_items) == 2
        assert len(after_batch) == 2
        # Real items should not be proxies
        assert all(not r[1].is_proxy for r in resolved_items)
