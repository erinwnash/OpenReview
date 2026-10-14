"""
DCC Integration Helpers for OpenReview SDK.
Provides ready-to-use helpers for Foundry Nuke, Autodesk Maya, and SideFX Houdini.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional
from openreview.sdk.client import OpenReviewClient, OpenReviewError


def review_in_openreview(media_path: str, in_frame: Optional[int] = None, out_frame: Optional[int] = None) -> bool:
    """
    Open media in an active OpenReview session, or launch OpenReview if not currently running.
    """
    client = OpenReviewClient()
    connected = client.ping()
    if not connected:
        # Launch OpenReview in background
        cmd = ["openreview", media_path]
        try:
            subprocess.Popen(cmd)
            return True
        except FileNotFoundError:
            # Fallback to python execution
            subprocess.Popen(["python", "-m", "openreview.app", media_path])
            return True

    client.load_media(media_path)
    if in_frame is not None and out_frame is not None:
        client.set_in_out(in_frame, out_frame)
    client.play()
    return True


# ------------------------------------------------------------------------------
# Foundry Nuke Helper
# ------------------------------------------------------------------------------
def nuke_send_selected_read() -> None:
    """
    Nuke script: Send currently selected Read node or Write node render to OpenReview.
    Add this function to ~/.nuke/menu.py:
        import nuke
        from openreview.sdk.dcc import nuke_send_selected_read
        nuke.menu('Nuke').addCommand('Pipeline/Review in OpenReview', nuke_send_selected_read, 'Ctrl+Alt+R')
    """
    try:
        import nuke  # type: ignore
    except ImportError:
        raise RuntimeError("nuke_send_selected_read must be called inside Foundry Nuke.")

    selected = nuke.selectedNodes()
    if not selected:
        nuke.message("Please select a Read or Write node to review.")
        return

    node = selected[0]
    if node.Class() in ("Read", "Write"):
        file_path = nuke.filename(node)
        first = int(node["first"].value()) if "first" in node.knobs() else int(nuke.root()["first_frame"].value())
        last = int(node["last"].value()) if "last" in node.knobs() else int(nuke.root()["last_frame"].value())
        review_in_openreview(file_path, first, last)
    else:
        nuke.message("Selected node is not a Read or Write node.")


# ------------------------------------------------------------------------------
# Autodesk Maya Helper
# ------------------------------------------------------------------------------
def maya_review_latest_playblast() -> None:
    """
    Maya script: Send playblast to OpenReview.
    Add to Maya shelf:
        from openreview.sdk.dcc import maya_review_latest_playblast
        maya_review_latest_playblast()
    """
    try:
        import maya.cmds as cmds  # type: ignore
    except ImportError:
        raise RuntimeError("maya_review_latest_playblast must be called inside Autodesk Maya.")

    start_frame = int(cmds.playbackOptions(q=True, min=True))
    end_frame = int(cmds.playbackOptions(q=True, max=True))
    # Trigger playblast
    playblast_path = cmds.playblast(
        format="qt",
        compression="H.264",
        forceOverwrite=True,
        showOrnaments=True,
        viewer=False,
    )
    if playblast_path and os.path.exists(playblast_path):
        review_in_openreview(playblast_path, start_frame, end_frame)


def get_nuke_menu_script(port: int = 45124) -> str:
    """Generate Python boilerplate code for Nuke menu.py integration."""
    return f"""# OpenReview Nuke Integration
import nuke
from openreview.sdk import OpenReviewClient

def _openreview_selected():
    client = OpenReviewClient(port={port})
    nodes = nuke.selectedNodes()
    if not nodes:
        nuke.message("Select a Read or Write node first.")
        return
    node = nodes[0]
    if node.Class() in ("Read", "Write"):
        path = nuke.filename(node)
        first = int(node["first"].value()) if "first" in node.knobs() else int(nuke.root()["first_frame"].value())
        last = int(node["last"].value()) if "last" in node.knobs() else int(nuke.root()["last_frame"].value())
        client.load_media(path)
        client.set_in_out(first, last)
        client.play()

nuke.menu('Nuke').addCommand('Review/Send to OpenReview', _openreview_selected, 'Ctrl+Alt+R')
"""


def get_maya_shelf_script(port: int = 45124) -> str:
    """Generate Python boilerplate code for Maya shelf button."""
    return f"""# OpenReview Maya Shelf Integration
import maya.cmds as cmds
from openreview.sdk import OpenReviewClient

client = OpenReviewClient(port={port})
start = int(cmds.playbackOptions(q=True, min=True))
end = int(cmds.playbackOptions(q=True, max=True))
pb = cmds.playblast(format="qt", compression="H.264", forceOverwrite=True, viewer=False)
if pb:
    client.load_media(pb)
    client.set_in_out(start, end)
    client.play()
"""

