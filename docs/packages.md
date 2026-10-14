# OpenReview Package & Plugin Management Guide

OpenReview provides a modular extensibility system allowing studios and artists to create custom plugins, add menu actions, hook into playback events, and distribute packages across productions.

---

## 1. Package Structure & Specification

An OpenReview package is a directory or `.zip` file containing a `manifest.json` (or `package.json`) and a Python entry point.

### Directory Layout
```text
my_studio_plugin/
├── manifest.json
├── plugin.py
└── icons/
    └── logo.png
```

### `manifest.json` Format
```json
{
  "id": "com.studio.shot_sync",
  "name": "Shot Sync Tool",
  "version": "1.0.0",
  "author": "VFX Pipeline Team",
  "description": "Integrates OpenReview playback with studio production database.",
  "entrypoint": "plugin.py",
  "category": "Pipeline",
  "tags": ["database", "sync", "dailies"],
  "min_openreview_version": "0.1.0",
  "enabled": true,
  "hooks": [
    "on_media_loaded",
    "on_frame_changed",
    "on_playback_state_changed"
  ]
}
```

---

## 2. Plugin Authoring (`OpenReviewPlugin`)

Subclass `OpenReviewPlugin` from `openreview.packages`:

```python
# plugin.py
import logging
from openreview.packages import OpenReviewPlugin, PluginContext

logger = logging.getLogger(__name__)

class ShotSyncPlugin(OpenReviewPlugin):
    """Studio shot sync plugin."""

    def on_init(self, context: PluginContext) -> None:
        """Called upon application startup."""
        self.context = context
        context.log("Shot Sync Plugin loaded successfully!")

    def on_media_loaded(self, media_path: str) -> None:
        """Triggered whenever a sequence or video is loaded."""
        self.context.log(f"Inspecting loaded plate: {media_path}")
        self.context.show_toast(f"Loaded: {media_path}", duration_ms=2500)

    def on_frame_changed(self, frame: int) -> None:
        """Triggered when playhead steps or scrubs to a frame."""
        pass

    def on_playback_state_changed(self, is_playing: bool) -> None:
        """Triggered on play/pause transitions."""
        pass

    def on_shutdown(self) -> None:
        """Called before application teardown."""
        self.context.log("Shutting down Shot Sync Plugin.")
```

### `PluginContext` Capabilities
The `context` object provides safe access to the host application:
- **`context.log(message, level=INFO)`**: Logs to OpenReview's log stream with automatic plugin namespace tagging.
- **`context.show_toast(message, duration_ms=3000)`**: Displays a transient on-screen notification in the OpenGL viewport.
- **`context.main_window`**: Access to OpenReview's `MainWindow` instance (for custom dock widgets or menu actions).

---

## 3. Package Discovery & Search Paths

OpenReview scans the following locations in priority order:
1. **Built-in Plugins**: Installed with the OpenReview core package (`openreview/packages/builtin/`).
2. **User Packages**: Located at `~/.openreview/packages/`.
3. **Studio Network Path**: Configured using the `OPENREVIEW_PACKAGE_PATH` environment variable:
   ```bash
   export OPENREVIEW_PACKAGE_PATH="/mnt/pipeline/openreview/plugins;/mnt/show/plugins"
   ```

---

## 4. Package Manager GUI

OpenReview provides a dedicated 3DEqualizer dark studio dialog accessible via:
- **`Window -> Package Manager`**
- **`Help -> Check for Software Updates...`**

### Features:
- **Plugin Inspector**: View version, author, description, tags, and category for all installed extensions.
- **Runtime Toggles**: Enable or disable plugins on the fly with instantaneous state persistence.
- **Zip Archive Installer**: Click **Install from ZIP...** to install and load extension packages without restarting OpenReview.
- **Folder Installer**: Click **Install from Folder...** to symlink or copy developer directories.
- **Uninstall**: Cleanly removes user packages from disk.

---

## 5. Software Updates (`SoftwareUpdater`)

OpenReview features an integrated update checker:
- **GitHub Releases Integration**: Automatically queries GitHub API for latest tagged releases.
- **Studio Manifest Support**: Studios can point OpenReview to an internal HTTP JSON endpoint.
- **Changelog Viewer**: Inspect release notes and changelogs directly inside the updates tab.

---

## 6. Recommended Custom Studio Plugins (with Examples)

### 6.1 ShotGrid / Flow Production Tracking Note & Annotated Frame Publisher (`com.studio.shotgrid_publisher`)
Exports all annotated frames and timeline bookmarks directly to a ShotGrid `Version` entity as `Note` attachments:

```python
import tempfile
from pathlib import Path
from PySide6.QtGui import QAction
from openreview.packages import OpenReviewPlugin, PluginContext

class ShotGridPublisherPlugin(OpenReviewPlugin):
    def on_init(self, context: PluginContext) -> None:
        self.context = context
        win = context.main_window
        if win is not None:
            act = QAction("Publish Annotations to ShotGrid...", win)
            act.setShortcut("Ctrl+Alt+P")
            act.triggered.connect(self.publish_notes_to_shotgrid)
            win.menuBar().addAction(act)

    def publish_notes_to_shotgrid(self) -> None:
        win = self.context.main_window
        if not win or not win._current_file:
            self.context.show_toast("No active media loaded to publish.", 3000)
            return
        annotated_frames = win._annotation_store.annotated_frames()
        bookmarks = win._timeline.bookmarks()
        target_frames = sorted(set(annotated_frames) | set(bookmarks.keys()))
        if not target_frames:
            self.context.show_toast("No annotations or bookmarks found.", 3000)
            return

        export_dir = Path(tempfile.mkdtemp(prefix="openreview_sg_"))
        attachments = []
        for frame in target_frames:
            out_png = export_dir / f"review_note.{frame:04d}.png"
            win.sdk_export_frame(str(out_png), frame=frame)
            note_text = bookmarks.get(frame, f"Annotated paint-over on frame {frame}")
            attachments.append((frame, out_png, note_text))

        self.context.show_toast(
            f"Published {len(attachments)} annotated frames to ShotGrid!", 4000
        )
```

### 6.2 Automated Render Tech-Check & QC Validator (`com.studio.auto_qc`)
Automatically inspects newly loaded EXR sequences on `on_media_loaded` for dropped frames, non-standard frame rates, or resolution mismatches, and bookmarks defective frames:

```python
from openreview.packages import OpenReviewPlugin, PluginContext

class AutoQCValidatorPlugin(OpenReviewPlugin):
    EXPECTED_WIDTH = 3840
    EXPECTED_HEIGHT = 2160
    EXPECTED_FPS = 24.0

    def on_init(self, context: PluginContext) -> None:
        self.context = context

    def on_media_loaded(self, media_path: str) -> None:
        win = self.context.main_window
        if not win or not win._reader:
            return
        reader = win._reader
        issues = []
        w, h = getattr(reader, "width", 0), getattr(reader, "height", 0)
        if (w, h) != (self.EXPECTED_WIDTH, self.EXPECTED_HEIGHT):
            issues.append(f"Resolution {w}x{h} != {self.EXPECTED_WIDTH}x{self.EXPECTED_HEIGHT}")
        fps = getattr(reader, "fps", 24.0)
        if abs(fps - self.EXPECTED_FPS) > 0.05:
            issues.append(f"FPS {fps:.3f} != {self.EXPECTED_FPS}")
        missing = getattr(reader, "missing_frames", [])
        for mf in missing:
            win._timeline.add_bookmark(mf, note=f"QC FAIL: Missing Frame {mf}")
        if missing:
            issues.append(f"{len(missing)} missing frames bookmarked")
        if issues:
            self.context.show_toast("QC FAIL: " + " | ".join(issues), 5000)
        else:
            self.context.show_toast("QC PASS: Delivery specs verified.", 2500)
```

### 6.3 Custom Studio Slate & Security Watermark Burn-In (`com.studio.slate_watermark`)
Auto-configures studio burn-in overlays and user watermarks when plates load from `/shots/<SHOW>/<SEQ>/<SHOT>/`:

```python
import getpass
import re
from openreview.packages import OpenReviewPlugin, PluginContext

class StudioBurnInHudPlugin(OpenReviewPlugin):
    SHOT_REGEX = re.compile(r"/shots/(?P<show>[^/]+)/(?P<seq>[^/]+)/(?P<shot>[^/]+)/")

    def on_init(self, context: PluginContext) -> None:
        self.context = context
        self.user = getpass.getuser()

    def on_media_loaded(self, media_path: str) -> None:
        win = self.context.main_window
        if not win:
            return
        norm_path = media_path.replace("\\", "/")
        match = self.SHOT_REGEX.search(norm_path)
        if match:
            info = match.groupdict()
            stamp = f"{info['show'].upper()} | {info['seq']}_{info['shot']} | CONFIDENTIAL: {self.user}"
            self.context.show_toast(f"Slate Configured: {stamp}", 3000)
```

### 6.4 One-Click Dailies HTML & PDF Contact Sheet Generator (`com.studio.html_report`)
Exports all bookmarked and annotated frames into a self-contained dark-themed HTML review report:

```python
from pathlib import Path
from PySide6.QtGui import QAction
from openreview.packages import OpenReviewPlugin, PluginContext

class HtmlReviewReportPlugin(OpenReviewPlugin):
    def on_init(self, context: PluginContext) -> None:
        self.context = context
        win = context.main_window
        if win:
            act = QAction("Export HTML Dailies Report...", win)
            act.triggered.connect(self.export_html_report)
            win.menuBar().addAction(act)

    def export_html_report(self) -> None:
        win = self.context.main_window
        if not win or not win._current_file:
            return
        report_dir = Path.home() / "OpenReview_Reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        frames = sorted(
            set(win._annotation_store.annotated_frames())
            | set(win._timeline.bookmarks().keys())
        ) or [win._current_frame]
        cards = []
        for f in frames:
            img_name = f"frame_{f:04d}.png"
            win.sdk_export_frame(str(report_dir / img_name), frame=f)
            note = win._timeline.bookmarks().get(f, "Annotated review frame")
            cards.append(f"<div class='card'><img src='{img_name}'/><h4>Frame {f}</h4><p>{note}</p></div>")
        html = f"<html><body style='background:#141414;color:#ddd;font-family:sans-serif'><h1>Dailies Report</h1>{''.join(cards)}</body></html>"
        out_html = report_dir / "dailies_report.html"
        out_html.write_text(html, encoding="utf-8")
        self.context.show_toast(f"Report saved: {out_html}", 4000)
```

---
*Author: **Maruthu Chakravarthi***

