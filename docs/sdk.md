# OpenReview Python SDK Reference

**Author:** Maruthu Chakravarthi  
**Version:** 1.0.1  
**HTML Portal:** [docs/html/sdk.html](file:///e:/works/Pipeline/code/OpenReview/docs/html/sdk.html)


The OpenReview Python SDK (`openreview.sdk`) enables seamless programmatic control of OpenReview from pipeline tools, terminal scripts, and Digital Content Creation (DCC) software such as **Foundry Nuke**, **Autodesk Maya**, and **SideFX Houdini**.

---

## 1. Quick Start

Install or add OpenReview to your Python environment:
```bash
export PYTHONPATH="/path/to/OpenReview/src:$PYTHONPATH"
```

### Basic Connection
```python
from openreview.sdk import OpenReviewClient

# Connect to local OpenReview instance (default port: 45124)
client = OpenReviewClient(host="127.0.0.1", port=45124)

# Test connectivity
if client.ping():
    print("Connected to OpenReview!")
else:
    print("OpenReview is not running.")
```

---

## 2. API Reference: `OpenReviewClient`

### Lifecycle & Status
- **`ping() -> bool`**  
  Returns `True` if OpenReview is running and responding.
- **`get_status() -> dict`**  
  Queries current viewer state. Returns:
  ```json
  {
    "media_path": "/shots/sq01/sh010/renders/v002/sh010.####.exr",
    "media_type": "sequence",
    "current_frame": 1024,
    "start_frame": 1001,
    "end_frame": 1100,
    "in_frame": 1001,
    "out_frame": 1050,
    "fps": 24.0,
    "is_playing": true,
    "exposure_ev": 0.0,
    "gain": 1.0,
    "gamma": 1.0,
    "saturation": 1.0,
    "bookmarks": [1010, 1045]
  }
  ```

### Media Loading
- **`load_media(path: str) -> bool`**  
  Loads a video file (`.mov`, `.mp4`), an image sequence (`sh010.####.exr`), or an OpenReview session file (`.ors`).

### Transport & Navigation
- **`play() -> bool`**: Initiates forward playback.
- **`pause() -> bool`**: Pauses playback.
- **`toggle_play() -> bool`**: Toggles between play and pause.
- **`seek(frame: int) -> int`**: Jumps playhead to specific frame number.
- **`set_fps(fps: float) -> float`**: Sets frame rate (e.g. `24.0`, `23.976`, `30.0`, `60.0`).
- **`set_in_out(in_frame: int, out_frame: int) -> dict`**: Clamps timeline playback range.

### Color Adjustments
- **`set_gain(gain: float) -> float`**: Sets linear multiplier.
- **`set_gamma(gamma: float) -> float`**: Sets gamma exponent.
- **`set_saturation(saturation: float) -> float`**: Sets color saturation multiplier.
- **`set_exposure(ev: float) -> float`**: Sets exposure offset in EV stops (e.g. `+1.0`, `-0.5`).
- **`set_color(gain=None, gamma=None, saturation=None, exposure=None) -> dict`**: Atomically updates multiple color grading parameters at once.

### Bookmarks & Exports
- **`add_bookmark(frame: Optional[int] = None, note: str = "") -> list[int]`**: Places a timeline bookmark.
- **`clear_bookmarks() -> list[int]`**: Clears all bookmarks.
- **`export_frame(destination: str, frame: Optional[int] = None) -> bool`**: Captures a viewport frame snapshot and writes it to disk.

---

## 3. DCC Integration Guides

### 3.1 Foundry Nuke Integration
Add this snippet to `~/.nuke/menu.py` to add a keyboard shortcut (`Ctrl+Alt+R`) that immediately reviews the selected Read or Write node in OpenReview:

```python
import nuke
from openreview.sdk import OpenReviewClient
from openreview.sdk.dcc import review_in_openreview

def review_selected_node():
    selected = nuke.selectedNodes()
    if not selected:
        nuke.message("Please select a Read or Write node to review.")
        return

    node = selected[0]
    if node.Class() in ("Read", "Write"):
        path = nuke.filename(node)
        first = int(node["first"].value()) if "first" in node.knobs() else int(nuke.root()["first_frame"].value())
        last = int(node["last"].value()) if "last" in node.knobs() else int(nuke.root()["last_frame"].value())
        
        # Opens in active OpenReview or launches a new process
        review_in_openreview(path, in_frame=first, out_frame=last)
    else:
        nuke.message("Selected node is not a Read or Write node.")

nuke.menu('Nuke').addCommand('Pipeline/Review in OpenReview', review_selected_node, 'Ctrl+Alt+R')
```

### 3.2 Autodesk Maya Shelf Button
Add this script to a custom Maya shelf button to send playblasts straight into OpenReview:

```python
import maya.cmds as cmds
from openreview.sdk.dcc import review_in_openreview

start_frame = int(cmds.playbackOptions(q=True, min=True))
end_frame = int(cmds.playbackOptions(q=True, max=True))

playblast_path = cmds.playblast(
    format="qt",
    compression="H.264",
    forceOverwrite=True,
    showOrnaments=True,
    viewer=False
)

if playblast_path:
    review_in_openreview(playblast_path, start_frame, end_frame)
```

### 3.3 SideFX Houdini ROP / TOPs Post-Render Callback
Attach this script to a Karma / Mantra ROP Post-Render Script or PDG/TOPs Python Processor node:

```python
import hou
from openreview.sdk import OpenReviewClient
from openreview.sdk.dcc import launch_or_connect

def post_render_openreview():
    node = hou.pwd()
    output_expr = node.parm("vm_picture").unexpandedString()
    start_f = int(node.parm("f1").eval())
    end_f = int(node.parm("f2").eval())
    fps = hou.fps()

    client = launch_or_connect()
    client.load_media(output_expr)
    client.set_fps(fps)
    client.set_in_out(start_f, end_f)
    client.seek(start_f)
    client.play()

post_render_openreview()
```

### 3.4 Blender (`render_complete` Handler)
Register a persistent `bpy.app.handlers.render_complete` callback in Blender:

```python
import bpy
from openreview.sdk.dcc import review_in_openreview

def _on_blender_render_complete(scene, _depsgraph=None):
    filepath = bpy.path.abspath(scene.render.filepath)
    start_f = scene.frame_start
    end_f = scene.frame_end
    review_in_openreview(filepath, in_frame=start_f, out_frame=end_f)

if _on_blender_render_complete not in bpy.app.handlers.render_complete:
    bpy.app.handlers.render_complete.append(_on_blender_render_complete)
```

### 3.5 Terminal / Pipeline Scripting
```python
#!/usr/bin/env python3
import sys
from openreview.sdk import OpenReviewClient

def main():
    if len(sys.argv) < 2:
        print("Usage: review_shot.py <sequence_or_mov>")
        sys.exit(1)

    path = sys.argv[1]
    client = OpenReviewClient()
    if not client.ping():
        print("Error: OpenReview is not running.")
        sys.exit(1)

    client.load_media(path)
    client.seek(1001)
    client.play()
    print(f"Sent {path} to OpenReview.")

if __name__ == "__main__":
    main()
```

---
*Author: **Maruthu Chakravarthi***

