"""
Unit tests for SessionGraph models: Sources, Folders, Sequences, Stacks, and Layouts.
"""
import pytest
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


def test_session_graph_sources_and_folders():
    graph = SessionGraph()

    # Manual add sources
    s1 = SourceItem(name="shot010_comp_v001", path="/jobs/sh010/v001.mov", start_frame=1001, end_frame=1050)
    s2 = SourceItem(name="shot010_comp_v002", path="/jobs/sh010/v002.mov", start_frame=1001, end_frame=1050)
    graph.sources[s1.id] = s1
    graph.sources[s2.id] = s2
    graph.root_source_ids.extend([s1.id, s2.id])

    assert len(graph.sources) == 2
    assert s1.duration == 50

    # Create folder
    folder = graph.create_folder("Episode 1")
    assert folder.id in graph.folders
    assert folder.id in graph.root_folder_ids

    # Delete source
    graph.delete_source(s1.id)
    assert s1.id not in graph.sources
    assert s1.id not in graph.root_source_ids


def test_session_graph_sequence_view():
    graph = SessionGraph()
    s1 = SourceItem(name="Clip A", path="/a.mov", start_frame=1001, end_frame=1020) # 20 frames
    s2 = SourceItem(name="Clip B", path="/b.mov", start_frame=1, end_frame=30)       # 30 frames
    graph.sources[s1.id] = s1
    graph.sources[s2.id] = s2

    seq = graph.create_sequence("Cut 1", [s1.id, s2.id])
    assert seq.total_duration == 50
    assert seq.start_frame == 1001
    assert seq.end_frame == 1050

    # Test timeline frame resolution
    # Frame 1005 should map to Clip A, frame 1005
    source, s_frame = seq.resolve_frame(1005, graph.sources)
    assert source == s1
    assert s_frame == 1005

    # Frame 1025 should map to Clip B, frame 5 (1001+20 = 1021 is start of Clip B frame 1)
    source, s_frame = seq.resolve_frame(1025, graph.sources)
    assert source == s2
    assert s_frame == 5

    # Reorder clips
    seq.move_clip(0, 1)
    assert seq.clips[0].source_id == s2.id


def test_session_graph_stack_view():
    graph = SessionGraph()
    s1 = SourceItem(name="Version 1", path="/v1.mov")
    s2 = SourceItem(name="Version 2", path="/v2.mov")
    graph.sources[s1.id] = s1
    graph.sources[s2.id] = s2

    stk = graph.create_stack("Comp Stack", [s1.id, s2.id])
    assert stk.index_a == 0
    assert stk.index_b == 1
    assert stk.get_layer_a(graph.sources) == s1
    assert stk.get_layer_b(graph.sources) == s2

    # Verify difference comparison modes
    stk.compare_mode = "difference"
    assert stk.compare_mode == "difference"
    stk.compare_mode = "difference_inverted"
    assert stk.compare_mode == "difference_inverted"


def test_session_graph_layout_view():
    graph = SessionGraph()
    s_ids = []
    for i in range(4):
        s = SourceItem(name=f"Camera {i+1}", path=f"/cam{i+1}.mov")
        graph.sources[s.id] = s
        s_ids.append(s.id)

    lay = graph.create_layout("Quad View", s_ids, scale_pct=50)
    assert lay.scale_pct == 50

    # Auto-grid for 4 sources should be 2x2
    rows, cols = lay.get_grid_dimensions()
    assert rows == 2
    assert cols == 2

    # Scale percentage support
    for pct in (100, 50, 25, 10):
        lay.scale_pct = pct
        assert lay.scale_pct == pct


def test_session_graph_serialization():
    graph = SessionGraph()
    s1 = SourceItem(name="Main Comp", path="/comp.mov", start_frame=1001, end_frame=1100)
    graph.sources[s1.id] = s1
    graph.root_source_ids.append(s1.id)

    seq = graph.create_sequence("Master Cut", [s1.id])
    stk = graph.create_stack("A/B Stack", [s1.id])
    lay = graph.create_layout("Review Grid", [s1.id], scale_pct=25)

    data = graph.to_dict()
    assert "sources" in data
    assert "sequences" in data
    assert "stacks" in data
    assert "layouts" in data

    # Restore in new graph
    graph2 = SessionGraph()
    graph2.load_from_dict(data)

    assert len(graph2.sources) == 1
    assert len(graph2.sequences) == 1
    assert len(graph2.stacks) == 1
    assert len(graph2.layouts) == 1
    assert graph2.layouts[lay.id].scale_pct == 25


def test_detect_media_colorspace(tmp_path):
    from openreview.models.session_graph import detect_media_colorspace

    # Test file extension rules
    exr_file = str(tmp_path / "shot.1001.exr")
    with open(exr_file, "w") as f: f.write("")
    assert detect_media_colorspace(exr_file, ".exr") == "ACEScg"

    dpx_file = str(tmp_path / "shot.1001.dpx")
    with open(dpx_file, "w") as f: f.write("")
    assert detect_media_colorspace(dpx_file, ".dpx") == "Cineon Log"

    # Default fallback for untagged still/video
    png_file = str(tmp_path / "texture.png")
    with open(png_file, "w") as f: f.write("")
    assert detect_media_colorspace(png_file, ".png") == "sRGB (Texture/Video)"
