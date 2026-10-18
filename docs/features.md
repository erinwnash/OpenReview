# OpenReview Complete Studio Feature Manual: In-Depth One-on-One Reference Guide

**Author:** Maruthu Chakravarthi  
**Version:** 1.0.1  
**Architecture:** Python 3.10+, PySide6 (Qt 6), Modern OpenGL 3.3+ Core Profile, OpenColorIO v2  
**Interactive Documentation Portal:** [docs/html/features.html](file:///e:/works/Pipeline/code/OpenReview/docs/html/features.html) | [docs/html/index.html](file:///e:/works/Pipeline/code/OpenReview/docs/html/index.html)

---

## Executive Overview

**OpenReview** is an open-source, studio-grade visual effects (VFX) sequence playback, high-dynamic-range (HDR) color inspection, multi-source compositing comparison, and collaborative dailies review desktop workstation. Designed with a high-contrast 3DEqualizer, Foundry Nuke, and Autodesk RV aesthetic, OpenReview combines high-performance multi-threaded C++/Python media readers, an OpenGL 3.3+ Core Profile GLSL fragment shader pipeline, two-tier RAM/disk caching, OpenColorIO (OCIO) v2 color science, multi-part EXR demuxing, stereoscopic 3D review, vector annotations, and compositing technical QC diagnostics.

This manual provides an **exhaustive, one-on-one deep-dive explanation for every studio feature** across twelve core domains. Each feature is documented with its studio purpose, exact UI controls and keyboard shortcuts, step-by-step operator guide, technical engine mechanics, and linked visual screenshots.

---

## 1. Domain-Driven One-on-One Feature Breakdown

### Domain 1: High-Performance Sequence & Video Playback Engine

---

#### Feature: Multi-Format Image Sequence Ingestion
- **Purpose & Studio Context:** High-end visual effects and animation pipelines rely on uncompressed or lossless image sequences rather than compressed video files. OpenReview natively ingests and indexes VFX image sequences without requiring transcode steps.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+O</span>  
  - Menu: *File &gt; Open Media...* or drag-and-drop any sequence frame onto the viewport canvas or Sources Dock.
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+O</span> or drag a frame (e.g. `sh010_comp_v002.1001.exr`) into the application.
  2. OpenReview automatically analyzes the file name, detects the frame number pattern (e.g. `####` or `%04d`), and scans the directory to resolve the full contiguous frame sequence range (e.g. `1001–1100`).
  3. The sequence is mounted into the Sources Dock, and the timeline transport updates its start, end, and current frame indicators automatically.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/core/sequence_parser.py` and `openreview/readers/`. The parser uses regex tokenization to isolate shot prefixes, padding width, and frame numbers, verifying file boundaries asynchronously to prevent filesystem I/O blocking.
- **Linked Figure:** `docs/html/assets/screenshots/sources_session_dock.png`

---

#### Feature: Containerized Video Playback
- **Purpose & Studio Context:** Editorial departments and review sessions frequently package daily cuts and offline references into Apple ProRes or Avid DNxHD QuickTime containers. OpenReview provides fluid video stream decoding alongside raw image sequences.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+O</span>  
  - Menu: *File &gt; Open Media...*
- **Step-by-Step Operator Guide:**
  1. Select a containerized video file (`.mov`, `.mp4`) via the file dialog or drop it onto the viewport.
  2. OpenReview probes audio/video streams, native resolution, framerate, and duration.
  3. Scrub smoothly using the timeline bar or transport controls.
- **Technical Engine Mechanics:**  
  Powered by `openreview/readers/video_reader.py` utilizing hardware-accelerated FFmpeg/OpenCV decoders. Video packets are decoded into linear frames and buffered directly into the unified cache ring.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: Wall-Clock Real-Time Playback vs. Play Every Frame Mode
- **Purpose & Studio Context:** Reviewing dialogue and audio sync requires strictly maintaining real-world playback speed (Real-Time), whereas checking complex VFX simulations and dynamics requires viewing every individual calculated frame without skipping (Play Every Frame).
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: Toggle button in Timeline Transport dock / Preferences dialog (<span class="key-badge">Ctrl+,</span>).
- **Step-by-Step Operator Guide:**
  1. Click the **Real-Time / Play Every Frame** toggle button on the right side of the transport dock.
  2. In *Real-Time* mode, if storage disk bandwidth temporarily lags, the clock drops redundant display draws to preserve true 24.0 FPS playback timing and audio lock.
  3. In *Play Every Frame* mode, the clock guarantees that every single frame is presented sequentially, automatically throttling playback speed if decoding requires additional time.
- **Technical Engine Mechanics:**  
  Managed by `openreview/core/clock.py` using Python's high-resolution `time.monotonic()` clock. Target presentation timestamps are evaluated on each tick of a high-precision `QTimer` (sub-millisecond resolution).
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: Non-Blocking Asynchronous Source Loading
- **Purpose & Studio Context:** Studio projects often reside on centralized network storage (NAS/SAN). Loading large 4K multi-part OpenEXR sequences must never freeze or lock up the artist's interactive interface.
- **UI Access & Keyboard Shortcuts:**  
  - Fully automatic upon media ingestion. Progress is displayed via a non-intrusive status toast and progress bar.
- **Step-by-Step Operator Guide:**
  1. Drop or open an extensive sequence directory.
  2. The UI remains 100% responsive: panning, zooming, and menu access function immediately while metadata and initial frames pre-buffer in the background.
  3. Cancellation tokens allow the user to immediately switch clips without waiting for background disk operations to finish.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/core/async_source_loader.py` using a thread pool worker architecture with thread-safe Qt signals and task cancellation tokens.
- **Linked Figure:** `docs/html/assets/screenshots/status_bar.png`

---

#### Feature: Bidirectional Playback & Ping-Pong Looping
- **Purpose & Studio Context:** Animators, modelers, and VFX artists constantly evaluate cyclic character walk cycles, smoke plumes, or cloth simulations.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Loop Mode button on Timeline Transport dock (cycles *Loop*, *Ping-Pong*, *Play Once*).
- **Step-by-Step Operator Guide:**
  1. Click the Loop Mode icon on the timeline transport bar to switch between modes.
  2. In *Ping-Pong* mode, when the playhead reaches the Out point, it seamlessly reverses playback direction until reaching the In point, bouncing continuously.
  3. In *Play Once* mode, the playhead halts upon reaching the terminal frame.
- **Technical Engine Mechanics:**  
  Handled in `openreview/core/clock.py` by dynamically flipping the transport direction sign (`direction = -direction`) at range boundaries.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: Target Framerate & Fractional FPS Calibration
- **Purpose & Studio Context:** Visual effects projects operate across international broadcast and cinema standards: 23.976 (NTSC cinema), 24.0 (theatrical), 25.0 (PAL), 29.97 (broadcast), 30.0, 48.0 (HFR), 59.94, and 60.0 FPS.
- **UI Access & Keyboard Shortcuts:**  
  - Access: FPS dropdown selector on the timeline transport bar, or *Preferences &gt; Playback*.
- **Step-by-Step Operator Guide:**
  1. Click the FPS indicator on the timeline bar.
  2. Select from the standardized industry presets or enter an arbitrary custom decimal framerate.
  3. The clock adjusts its monotonic target delta ($1.0 / \text{FPS}$) instantly without stopping active playback.
- **Technical Engine Mechanics:**  
  `openreview/core/clock.py` computes target interval milliseconds with 64-bit float precision, accounting for fractional frame durations.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

### Domain 2: Monotonic Timeline, JKL Shuttling & SMPTE Timecode

---

#### Feature: Multi-Speed JKL Transport Shuttling
- **Purpose & Studio Context:** Professional editors and supervisors navigate cuts and sequences using three-finger JKL navigation without looking at the mouse.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">J</span>: Shuttle Reverse (`-1x`, `-2x`, `-4x`, `-8x`)  
  - <span class="key-badge">K</span>: Stop Playback  
  - <span class="key-badge">L</span>: Shuttle Forward (`+1x`, `+2x`, `+4x`, `+8x`)
- **Step-by-Step Operator Guide:**
  1. While reviewing, tap <span class="key-badge">L</span> once to play forward at standard `1x` speed.
  2. Tap <span class="key-badge">L</span> again to accelerate to `2x`, `4x`, and up to `8x` high-speed fast forward.
  3. Tap <span class="key-badge">K</span> to stop on an exact frame.
  4. Tap <span class="key-badge">J</span> to shuttle backwards through `-1x`, `-2x`, `-4x`, and `-8x`.
- **Technical Engine Mechanics:**  
  Implemented in `MainWindow._on_shuttle_rev()`, `_on_shuttle_stop()`, and `_on_shuttle_fwd()` in `openreview/ui/main_window.py`. The clock multiplies base framerate by speed factor and rescales audio playback rate synchronously.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: SMPTE Timecode (HH:MM:SS:FF) & Frame Count Display
- **Purpose & Studio Context:** Production editorial communicates using SMPTE timecodes (`HH:MM:SS:FF`), while VFX artists and compositors work with absolute frame numbers (`1001-1100`).
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+T</span>  
  - Click on the timecode label on the timeline dock.
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+T</span> while viewing any media.
  2. The timeline timecode readout toggles immediately between SMPTE timecode (e.g. `01:00:04:12`) and absolute sequence frame numbers (e.g. `1024`).
- **Technical Engine Mechanics:**  
  `openreview/widgets/timeline.py` calculates SMPTE strings based on sequence start frame, active FPS, and current frame count, with full drop-frame and non-drop-frame compatibility.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: Frameless Go-To Frame Floating Modal
- **Purpose & Studio Context:** Quickly jumping to specific shot keyframes, director notes, or client review frames without taking hands off the keyboard.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+G</span>  
  - Menu: *Playback &gt; Go to Frame...*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+G</span> to open the minimalist popup dialog.
  2. Type the target frame number (e.g. `1054`).
  3. Press <span class="key-badge">Enter</span> to instantly seek the viewport and timeline. Press <span class="key-badge">Escape</span> to dismiss without seeking.
- **Technical Engine Mechanics:**  
  Built as a borderless, auto-focused modal in `openreview/ui/goto_frame_dialog.py`, clamping inputs to the active sequence's valid frame bounds.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_goto_frame.png`

---

#### Feature: Bookmark Flags & Segment Navigation
- **Purpose & Studio Context:** Flagging key moments, continuity hitches, or art notes on specific frames during dailies for quick recall later.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">M</span>: Toggle bookmark on current frame  
  - <span class="key-badge">Alt+Left</span> / <span class="key-badge">Alt+Right</span>: Jump to previous / next bookmark  
  - <span class="key-badge">PageUp</span> / <span class="key-badge">PageDown</span>: Jump across bookmark segments
- **Step-by-Step Operator Guide:**
  1. While scrubbing, press <span class="key-badge">M</span> on any frame of interest. A vibrant cyan bookmark flag appears on the timeline scrubber.
  2. Tap <span class="key-badge">Alt+Right</span> or <span class="key-badge">Alt+Left</span> to jump directly between flagged frames.
  3. Use <span class="key-badge">PageDown</span> / <span class="key-badge">PageUp</span> to restrict playback looping to consecutive bookmark intervals.
- **Technical Engine Mechanics:**  
  Maintained inside `PlaybackClock.bookmarks` in `openreview/core/clock.py` and rendered as custom anti-aliased visual ticks in `openreview/widgets/timeline.py`.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

### Domain 3: Two-Tier Memory Caching (RAM Ring Buffer & Persistent Disk Cache)

---

#### Feature: Tier-1 RAM RingBufferCache & 80/20 Lookahead
- **Purpose & Studio Context:** High-resolution 4K and 8K EXR sequence playback requires caching uncompressed floating-point pixel frames directly in system RAM for zero-latency 60 FPS playback.
- **UI Access & Keyboard Shortcuts:**  
  - Configurable in *Preferences &gt; Caching* (<span class="key-badge">Ctrl+,</span>).
- **Step-by-Step Operator Guide:**
  1. Open *Preferences &gt; Caching* and allocate a RAM cache budget (from 1.0 GB up to 64.0 GB).
  2. As you scrub or play, the timeline displays a green cached frame indicator showing frames loaded into memory.
  3. The asymmetric 80/20 lookahead algorithm pre-decodes 80% of budget forward in the direction of playback and 20% behind the playhead.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/core/cache.py` via `RingBufferCache`. Memory allocation is tracked in real-time, safely evicting the oldest unreferenced frames outside the active playhead window when the budget ceiling is approached.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_preferences_caching.png`

---

#### Feature: In/Out Region RAM Caching
- **Purpose & Studio Context:** Supervisors reviewing a specific 30-frame cut revision want that exact segment locked into RAM so it loops seamlessly without storage disk reads.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Shift+C</span>  
  - Menu: *Playback &gt; Cache In/Out Region*
- **Step-by-Step Operator Guide:**
  1. Mark In (<span class="key-badge">[</span>) and Out (<span class="key-badge">]</span>) points around the review segment.
  2. Press <span class="key-badge">Shift+C</span>. The cache engine immediately prioritizes background decoding for that exact frame bracket.
  3. The timeline fills with solid green across the range, locking the frames into RAM.
- **Technical Engine Mechanics:**  
  `MainWindow.toggle_cache()` coordinates with `RingBufferCache` to set high-priority prefetch tasks targeting the frame subset $[In, Out]$.
- **Linked Figure:** `docs/html/assets/screenshots/timeline_transport_dock.png`

---

#### Feature: Tier-2 Persistent High-Speed Disk Caching
- **Purpose & Studio Context:** Preserving pre-decoded 32-bit float frames on fast NVMe storage across application restarts, saving hours of decompression time on large projects.
- **UI Access & Keyboard Shortcuts:**  
  - Configurable in *Preferences &gt; Caching* (<span class="key-badge">Ctrl+,</span>).
- **Step-by-Step Operator Guide:**
  1. In Preferences, enable *Persistent Disk Cache* and designate a storage path (default: `~/.openreview/cache`) with a disk limit (e.g. 32.0 GB).
  2. Frames decoded during review are written to compressed binary cache blocks on disk.
  3. Relaunching OpenReview and opening the same sequence loads frames near-instantaneously from NVMe disk cache rather than decompressing raw EXRs.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/core/disk_cache.py` using fast serialization with LZ4/Zstandard compression, keyed by file mtime, hash, and sequence indices.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_preferences_caching.png`

---

#### Feature: Granular Cache Invalidation & Reload
- **Purpose & Studio Context:** When compositors re-render single frames or an entire shot from Nuke, the reviewer needs to invalidate and refresh cached frames without restarting the application.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Ctrl+R</span>: Reload Active Frame  
  - <span class="key-badge">Ctrl+Shift+R</span>: Reload Active Sequence  
  - <span class="key-badge">Ctrl+Shift+C</span>: Clear Active Source RAM Cache  
  - <span class="key-badge">Ctrl+Delete</span>: Flush Entire Workspace RAM/Disk Cache
- **Step-by-Step Operator Guide:**
  1. To inspect a newly overwritten frame from Nuke, press <span class="key-badge">Ctrl+R</span>. The frame is purged from RAM and disk cache and re-read from source.
  2. To refresh the entire sequence after a full background render, press <span class="key-badge">Ctrl+Shift+R</span>.
  3. To free system RAM, press <span class="key-badge">Ctrl+Shift+C</span>.
- **Technical Engine Mechanics:**  
  Calls `cache.invalidate_frame(source_id, frame)` and `cache.clear_source(source_id)` to purge entries from memory and trigger immediate viewport redraws.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_process_info.png`

---

### Domain 4: Hardware OpenGL 3.3 Core Viewport Canvas & Presentation Display

---

#### Feature: Modern OpenGL 3.3 Core Profile Pipeline
- **Purpose & Studio Context:** Fixed-function legacy OpenGL pipelines lack the precision needed for 32-bit floating-point HDR images. OpenReview utilizes modern Core Profile shaders for high-throughput, color-accurate presentation.
- **UI Access & Keyboard Shortcuts:**  
  - Automatically active. View context info in *Help &gt; Process Information* (<span class="key-badge">Ctrl+I</span>).
- **Step-by-Step Operator Guide:**
  1. Open any floating-point EXR or DPX sequence.
  2. Frame presentation is rendered via compiled GLSL fragment shaders directly on the GPU.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/ui/viewport.py` and `openreview/color/shader_builder.py`. Uses `QOpenGLWidget` with core profile context, allocating native `GL_RGBA16F` or `GL_RGBA32F` texture storage.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_preferences_gpu_acceleration.png`

---

#### Feature: Asynchronous PBO (Pixel Buffer Object) DMA Texture Streaming
- **Purpose & Studio Context:** Uploading 4K 16-bit uncompressed frames to GPU VRAM synchronously causes micro-stutters. Double-buffered PBOs upload texture data in the background via Direct Memory Access (DMA).
- **UI Access & Keyboard Shortcuts:**  
  - Configurable in *Preferences &gt; GPU Acceleration* (<span class="key-badge">Ctrl+,</span>).
- **Step-by-Step Operator Guide:**
  1. Ensure *Use Asynchronous PBO Streaming* is enabled in Preferences.
  2. Playback of high-resolution sequences streams smoothly without CPU transfer stalls.
- **Technical Engine Mechanics:**  
  `Viewport._upload_texture()` binds alternating `glGenBuffers` PBOs. While the GPU renders from PBO A, CPU memory copies frame bytes asynchronously to PBO B via DMA.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_preferences_gpu_acceleration.png`

---

#### Feature: Pan, Multi-Tier Zoom & Geometric Framing
- **Purpose & Studio Context:** Inspecting fine matte lines, comp grain, or pixel flaws requires smooth canvas navigation and immediate access to 100% 1:1 pixel size and framing presets.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">F</span>: Fit to Window  
  - <span class="key-badge">Alt+F</span>: Fit Width  
  - <span class="key-badge">1</span> / <span class="key-badge">Ctrl+1</span>: 100% (1:1 Actual Pixel Size)  
  - <span class="key-badge">Ctrl+2</span> / <span class="key-badge">Ctrl+4</span> / <span class="key-badge">Ctrl+8</span>: 200% / 400% / 800% Zoom  
  - Middle Mouse Button (MMB) Drag: Pan Canvas  
  - Mouse Scroll Wheel: Dynamic Continuous Zoom
- **Step-by-Step Operator Guide:**
  1. Middle-click and drag across the canvas to pan smoothly.
  2. Spin the mouse wheel to zoom centered around the cursor position.
  3. Press <span class="key-badge">F</span> at any time to re-center and fit the entire frame in the window.
  4. Press <span class="key-badge">1</span> to view pixels at their true native resolution.
- **Technical Engine Mechanics:**  
  Handled in `Viewport.mouseMoveEvent()` and `wheelEvent()` by updating canvas transformation matrices passed directly to vertex shaders.
- **Linked Figure:** `docs/html/assets/screenshots/top_control_bar.png`

---

#### Feature: Horizontal Flop & Vertical Flip Transforms
- **Purpose & Studio Context:** VFX supervisors often flip an image horizontally to break visual familiarity and spot compositional errors, lighting mismatches, and matte seams.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Shift+X</span>: Flop Horizontal (Mirror X)  
  - <span class="key-badge">Shift+Y</span>: Flip Vertical (Mirror Y)
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Shift+X</span> to instantly invert the horizontal axis of the displayed media.
  2. Press again to restore normal orientation.
- **Technical Engine Mechanics:**  
  Transforms texture UV coordinates directly in the vertex shader without re-copying or modifying underlying frame buffer memory.
- **Linked Figure:** `docs/html/assets/screenshots/top_control_bar.png`

---

#### Feature: Bilinear Smooth vs. Nearest-Neighbor Filtering
- **Purpose & Studio Context:** When zoomed in to 400% or 800%, bilinear smoothing blurs pixel borders, making it impossible to evaluate edge aliasing or single-pixel fireflies.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">N</span>  
  - Menu: *View &gt; Toggle Filtering (Bilinear / Nearest)*
- **Step-by-Step Operator Guide:**
  1. Zoom in close to a high-contrast edge (<span class="key-badge">Ctrl+4</span>).
  2. Press <span class="key-badge">N</span> to switch the OpenGL texture sampler from `GL_LINEAR` to `GL_NEAREST`.
  3. Individual pixel squares become crisp and blocky, allowing exact sub-pixel evaluation.
- **Technical Engine Mechanics:**  
  Toggles `glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)` dynamically on active texture units.
- **Linked Figure:** `docs/html/assets/screenshots/top_control_bar.png`

---

#### Feature: Fullscreen Mode with Taskbar Concealment & Presentation Mode
- **Purpose & Studio Context:** Executive screening rooms and supervisory reviews require clean, distraction-free display without window borders, docks, or operating system taskbars.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">F12</span>: Toggle Borderless Fullscreen (conceals OS taskbar)  
  - <span class="key-badge">Ctrl+P</span>: Toggle Clean Presentation Mode (hides all UI chrome)
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">F12</span> on a calibrated reference monitor for edge-to-edge playback.
  2. Press <span class="key-badge">Ctrl+P</span> to hide all docks, menus, and scrubber chrome.
  3. Press <span class="key-badge">Escape</span> to exit presentation mode.
- **Technical Engine Mechanics:**  
  Uses `Qt.WindowFullScreen` flags combined with Windows Win32 API taskbar concealment overrides in `MainWindow._toggle_fullscreen()`.
- **Linked Figure:** `docs/html/assets/screenshots/workspace_overview.png`

---

#### Feature: Theatrical Aspect Ratio Mattes & Safe Guides
- **Purpose & Studio Context:** Ensuring compositions comply with theatrical delivery framing (e.g. 2.35:1 or 1.85:1) and action/title broadcast safety margins.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Ctrl+M</span>: Cycle Aspect Mattes (1.33, 1.78, 1.85, 2.35, 2.39, Off)  
  - <span class="key-badge">Shift+M</span>: Cycle Matte Opacity (25%, 50%, 75%, 100%)  
  - <span class="key-badge">Shift+G</span>: Toggle Action/Title Safe Area Guides and Center Cross
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+M</span> to overlay letterbox/pillarbox bars calibrated to the project's delivery aspect ratio.
  2. Press <span class="key-badge">Shift+M</span> to adjust the masking transparency.
  3. Press <span class="key-badge">Shift+G</span> to draw Action Safe (90%), Title Safe (80%), and Center Crosshair guides.
- **Technical Engine Mechanics:**  
  Calculated and drawn as parametric vector geometries over the viewport canvas in `Viewport.paintGL()`.
- **Linked Figure:** `docs/html/assets/screenshots/viewport_safe_guides_matte.png`

---

### Domain 5: Multi-Stage GLSL Color Pipeline, OCIO v2 & 3D LUT Engine

---

#### Feature: GPU OpenColorIO v2 (OCIO) Pipeline
- **Purpose & Studio Context:** Industry-standard color fidelity conforming scene-linear ACEScg, camera raw log spaces (ARRI LogC, RED Log3G10), and display devices (sRGB, Rec.709, DCI-P3).
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+O</span> (Toggle OCIO)  
  - HUD: OpenColorIO Configuration HUD
- **Step-by-Step Operator Guide:**
  1. Open the OCIO Configuration HUD.
  2. Select your studio's `config.ocio` file or auto-resolve via the `$OCIO` environment variable.
  3. Pick the active Input Space (e.g. `ACEScg`), Display (e.g. `sRGB`), and View Transform (e.g. `ACES 1.0 SDR-video`).
  4. Shader updates compile instantly on the GPU with zero frame latency.
- **Technical Engine Mechanics:**  
  `openreview/color/ocio_manager.py` queries PyOpenColorIO to generate native GLSL fragment shader code and 3D LUT textures bound directly to the viewport shader program.
- **Linked Figure:** `docs/html/assets/screenshots/hud_ocio_config.png`

---

#### Feature: Scene-Linear Exposure (EV) & Linear Gain
- **Purpose & Studio Context:** Checking underexposed shadow detail or overexposed highlight roll-off in 32-bit floating-point HDR images using photographic F-stop stops.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Alt++</span> / <span class="key-badge">Alt+-</span>: Exposure Up / Down (±0.25 EV steps)  
  - <span class="key-badge">+</span> / <span class="key-badge">-</span>: Linear Gain Up / Down (±0.10 steps)  
  - <span class="key-badge">E</span> / <span class="key-badge">Ctrl+Alt+E</span>: Reset Exposure to 0.0 EV  
  - <span class="key-badge">Ctrl+Alt+R</span>: Reset All Color Adjustments
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Alt++</span> to stop up exposure by +0.25 EV increments into highlights.
  2. Press <span class="key-badge">Alt+-</span> to stop down exposure into deep shadows.
  3. Tap <span class="key-badge">E</span> to return exposure to default 0.0 EV.
- **Technical Engine Mechanics:**  
  Evaluated in GLSL fragment shader: `color.rgb = color.rgb * uGain * exp2(uExposureEV);`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_color_adjustments.png`

---

#### Feature: Instant Display Invert Colors
- **Purpose & Studio Context:** Inverting displayed colors allows rotoscope artists and compositors to inspect edge quality, fringing, and matte halos against high-contrast complementary backdrops.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Shift+I</span>  
  - Checkbox in Color Adjustments HUD (<span class="key-badge">/</span>).
- **Step-by-Step Operator Guide:**
  1. While zoomed in on an actor's hair or roto edge, press <span class="key-badge">Shift+I</span>.
  2. The display immediately inverts (`vec3(1.0) - rgb`). Dark matte lines on light backgrounds become instantly visible.
  3. Press <span class="key-badge">Shift+I</span> again to return to normal display.
- **Technical Engine Mechanics:**  
  Calculated at the end of the GLSL fragment shader pipeline: `if (uInvert) { rgb = vec3(1.0) - rgb; }`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_color_adjustments.png`

---

#### Feature: Master & Per-Channel Gamma, Contrast & Saturation
- **Purpose & Studio Context:** Performing non-destructive color balancing, midtone adjustments, and despill verification during review.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Shift++</span> / <span class="key-badge">Shift+-</span>: Master Gamma Up / Down (±0.05)  
  - <span class="key-badge">Ctrl+Shift++</span> / <span class="key-badge">Ctrl+Shift+-</span>: Saturation Up / Down (±0.05)  
  - <span class="key-badge">/</span>: Open Color Adjustments HUD
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">/</span> to open the Color Adjustments HUD.
  2. Adjust Master Gamma or expand the Per-Channel R/G/B section to trim individual color channels.
  3. Adjust Contrast using the 18% scene-linear mid-grey pivot slider to preserve midtone exposure while expanding dynamic range.
- **Technical Engine Mechanics:**  
  Contrast is computed around mid-grey: `rgb = pow(rgb / 0.18, vec3(contrast)) * 0.18`. Saturation uses Rec.709 luminance weighting: `luma = dot(rgb, vec3(0.2126, 0.7152, 0.0722))`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_color_adjustments.png`

---

#### Feature: Out-of-Range High-Contrast Zebra Under/Over Indicators
- **Purpose & Studio Context:** Warning colorists and compositors of illegal clipping whites (> 1.0) or crushed negative blacks (< 0.0) that violate broadcast or delivery specs.
- **UI Access & Keyboard Shortcuts:**  
  - Checkbox in Color Adjustments HUD (<span class="key-badge">/</span>).
- **Step-by-Step Operator Guide:**
  1. Open the Color Adjustments HUD (<span class="key-badge">/</span>) and check *Show Out-of-Range Zebra*.
  2. Blown-out highlight pixels (> 1.0) flash in bright saturated Magenta.
  3. Sub-black clipped pixels (< 0.0) flash in bright saturated Cyan.
- **Technical Engine Mechanics:**  
  Executed in the GLSL fragment shader:
  ```glsl
  if (uShowOutOfRange) {
      if (any(greaterThan(rgb, vec3(1.0)))) rgb = vec3(1.0, 0.0, 1.0); // Magenta
      else if (any(lessThan(rgb, vec3(0.0)))) rgb = vec3(0.0, 1.0, 1.0); // Cyan
  }
  ```
- **Linked Figure:** `docs/html/assets/screenshots/viewport_out_of_range.png`

---

#### Feature: Hardware 3D LUT & ASC CDL Grading Engine
- **Purpose & Studio Context:** Applying on-set CDL grades (`.cdl`, `.cc`, `.ccc`) and show creative 3D LUTs (`.cube`, `.3dl`) non-destructively to raw log or linear plates.
- **UI Access & Keyboard Shortcuts:**  
  - Drop a `.cube`, `.3dl`, or `.cdl` file directly onto the viewport canvas or load via the Color menu.
- **Step-by-Step Operator Guide:**
  1. Drag a 3D LUT (`.cube`) or CDL file onto the canvas.
  2. OpenReview parses the grade and enables the corresponding GLSL shader stage.
  3. Toggle LUT or CDL bypass via the Color menu to check the un-graded source plate.
- **Technical Engine Mechanics:**  
  3D LUTs are uploaded to `GL_TEXTURE_3D` texture units with trilinear interpolation. ASC CDL applies standard Slope, Offset, Power, and Saturation equations in the fragment shader.
- **Linked Figure:** `docs/html/assets/screenshots/hud_color_adjustments.png`

---

### Domain 6: Visual Effects Technical QC & Inbuilt xtra-QC Diagnostic Suite

---

#### Feature: Built-in xtra-QC Utils Compositing Suite Dock
- **Purpose & Studio Context:** Comprehensive compositing quality control inspired by high-end visual effects workflows, bringing plate comparisons, softclip knee, grain checks, and edge defringing directly into the review workspace.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Q</span>  
  - Menu: *Window &gt; xtra QC Utils Dock*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Q</span> to reveal the xtra QC Utils dock panel on the right sidebar.
  2. The panel features middle-mouse button Blender-style panning and collapsible accordion sections for Source Plate, Color Correction, HSL/Grain/Highpass, Black Levels, and RGBA Mattes.
  3. Adjust any slider or mode; viewport shaders update instantly.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/packages/builtin/comp_qc/hud_comp_qc.py` and `qc_state.py`. Connects directly to `Viewport.comp_qc_state` and binds dynamic uniforms in `shader_builder.py`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_comp_qc.png`

---

#### Feature: Softclip Knee Highlight Compression
- **Purpose & Studio Context:** Inspecting detail hidden inside burned-out specular highlights, practical lights, and sky plates without affecting midtone exposure.
- **UI Access & Keyboard Shortcuts:**  
  - Access: *Softclip Knee* slider in the xtra QC Utils panel (<span class="key-badge">Q</span>).
- **Step-by-Step Operator Guide:**
  1. In the xtra QC panel, expand *Color correction*.
  2. Drag the *Softclip Knee* slider down from `1.0` towards `0.0`.
  3. High-dynamic-range highlight values roll off smoothly into display range, revealing hidden texture in overexposed areas.
- **Technical Engine Mechanics:**  
  Evaluated in GLSL:
  ```glsl
  if (knee < 1.0) {
      color.rgb = mix(color.rgb, color.rgb / (color.rgb + vec3(1.0 - knee)), 1.0 - knee);
  }
  ```
- **Linked Figure:** `docs/html/assets/screenshots/hud_comp_qc.png`

---

#### Feature: Split-Frequency Comp Grain Inspector
- **Purpose & Studio Context:** Auditing whether synthetic CG grain matches original camera sensor grain structure across fine, medium, and coarse frequencies.
- **UI Access & Keyboard Shortcuts:**  
  - Access: *Grain Check Mode* buttons in xtra QC Utils (<span class="key-badge">Q</span>).
- **Step-by-Step Operator Guide:**
  1. In the xtra QC panel, expand *HSL Colorspace / Grain Inspection / Highpass*.
  2. Click *Grain Check Mode*.
  3. OpenReview isolates sensor noise frequencies and boosts luminance contrast, making grain mismatches and crawling noise clearly visible.
- **Technical Engine Mechanics:**  
  Computes high-frequency band-pass luminance offsets and expands contrast: `color.rgb = 0.5 + (color.rgb - blur(color.rgb)) * gain;`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_comp_qc.png`

---

#### Feature: High-Pass Spatial Edge Filter
- **Purpose & Studio Context:** Detecting motion blur inconsistencies, keying edge halos, and sharpening artifacts along composite boundaries.
- **UI Access & Keyboard Shortcuts:**  
  - Access: *Highpass Filter* toggle and radius slider in xtra QC Utils (<span class="key-badge">Q</span>).
- **Step-by-Step Operator Guide:**
  1. Toggle the *Highpass Filter* on in the xtra QC panel.
  2. Low-frequency illumination is removed, leaving only fine spatial edges and transitions rendered on a neutral 50% grey plane.
  3. Edge defringing errors and matte seams immediately jump out.
- **Technical Engine Mechanics:**  
  Applies a real-time 9-tap 2D Laplacian convolution kernel across neighboring pixel samples in the GLSL fragment shader.
- **Linked Figure:** `docs/html/assets/screenshots/hud_comp_qc.png`

---

#### Feature: Shadow Black Level Elevation QC
- **Purpose & Studio Context:** Uncovering contaminated black levels, matte line bleeding, and negative sensor values hidden in dark shadow regions.
- **UI Access & Keyboard Shortcuts:**  
  - Access: *Black Levels* section in xtra QC Utils (<span class="key-badge">Q</span>).
- **Step-by-Step Operator Guide:**
  1. Expand the *Black Levels* section in the xtra QC panel.
  2. Increase the black pedestal lift.
  3. Deep shadows are lifted into midtone visibility, revealing whether composited elements sit properly on the original camera plate's black floor.
- **Technical Engine Mechanics:**  
  Applies linear shadow pedestal offsets and toe expansions: `color.rgb = max(vec3(0.0), color.rgb + vec3(lift));`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_comp_qc.png`

---

#### Feature: Floating-Point Negative & NaN/Inf Pixel Highlighter
- **Purpose & Studio Context:** CG renders occasionally generate illegal IEEE-754 `NaN` (Not a Number), `+Inf`, or negative values that cause render crashes or black speckles downstream.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Toggle checkboxes in xtra QC Utils panel (<span class="key-badge">Q</span>) or Viewport diagnostics menu.
- **Step-by-Step Operator Guide:**
  1. Enable *Highlight NaN Pixels* and *Highlight Negative Pixels*.
  2. Invalid `NaN` pixels flash in bright neon green; negative values flash in bright red.
- **Technical Engine Mechanics:**  
  Executed via GLSL built-in predicates `isnan(color)` and `isinf(color)`, overriding display color when true.
- **Linked Figure:** `docs/html/assets/screenshots/viewport_out_of_range.png`

---

#### Feature: Single-Key Channel Isolation (RGB, R, G, B, Alpha, Luma)
- **Purpose & Studio Context:** Evaluating individual color channels for noise, compression artifacts, and greenscreen spill.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">C</span>: Full RGB Color  
  - <span class="key-badge">R</span>: Solo Red Channel as Monochrome  
  - <span class="key-badge">G</span>: Solo Green Channel as Monochrome  
  - <span class="key-badge">B</span>: Solo Blue Channel as Monochrome  
  - <span class="key-badge">A</span>: Solo Alpha Channel as Monochrome  
  - <span class="key-badge">Y</span>: Solo Rec.709 Luminance Channel
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">B</span> to inspect the Blue channel, where digital camera sensor noise is most prominent.
  2. Press <span class="key-badge">A</span> to inspect the Alpha matte channel for transparency holes or edge fringing.
  3. Press <span class="key-badge">C</span> to restore full color viewing.
- **Technical Engine Mechanics:**  
  GLSL fragment shader isolates channels: `if (uChannel == 1) rgb = vec3(rgb.r); else if (uChannel == 4) rgb = vec3(color.a);`.
- **Linked Figure:** `docs/html/assets/screenshots/top_control_bar.png`

---

#### Feature: Interactive 64-Bit Floating-Point Pixel Status Bar
- **Purpose & Studio Context:** Continuously reading raw pixel values under the mouse cursor without having to open a separate modal tool.
- **UI Access & Keyboard Shortcuts:**  
  - Hover mouse anywhere on the viewport canvas. Telemetry appears live in the bottom status bar.
- **Step-by-Step Operator Guide:**
  1. Move the mouse pointer over any pixel on the canvas.
  2. The status bar immediately updates with:
     - Exact integer canvas coordinates `(X, Y)`
     - 32/64-bit float linear RGBA values (e.g. `R:0.4852 G:0.3214 B:0.1876 A:1.0000`)
     - 8-bit sRGB equivalents (e.g. `RGB: 124, 82, 48`)
     - HSV color values
     - Rec.709 Luminance `Y`
- **Technical Engine Mechanics:**  
  `Viewport._on_mouse_moved()` samples the underlying raw numpy frame buffer array at cursor sub-pixel coordinates, emitting rich signals to `MainWindow.statusBar()`.
- **Linked Figure:** `docs/html/assets/screenshots/status_bar.png`

---

#### Feature: Area Pixel Analyzer & Region Color Sampler
- **Purpose & Studio Context:** Measuring color statistics across a specific area (e.g. an actor's forehead or a greenscreen backdrop) to check exposure consistency.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">F5</span> / <span class="key-badge">Alt+C</span>  
  - HUD: Color Inspector HUD
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">F5</span> to open the Color Inspector HUD.
  2. Click and drag a rectangular sampling box on the viewport canvas.
  3. The HUD instantly calculates and displays Minimum, Maximum, Mean Average, and Median values per channel, along with a live color swatch.
- **Technical Engine Mechanics:**  
  Extracts the 2D bounding box slice from the active frame array and executes vector numpy statistics (`np.min`, `np.max`, `np.mean`, `np.median`).
- **Linked Figure:** `docs/html/assets/screenshots/hud_color_inspector.png`

---

### Domain 7: Multi-Source Comparison, Interactive A/B Wipes & Difference QC

---

#### Feature: Dual-Source Interactive Split Wipe
- **Purpose & Studio Context:** Comparing a comp render against an original plate, or comparing two grading passes, with an intuitive on-screen split divider.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">W</span>: Toggle Split Wipe Mode  
  - <span class="key-badge">Shift+W</span>: Flip Wipe Orientation  
  - <span class="key-badge">Alt+W</span>: Reset Wipe to Center (50%)
- **Step-by-Step Operator Guide:**
  1. Assign Source A (e.g. Comp) and Source B (e.g. Plate) in the Sources Dock or Wipe HUD.
  2. Press <span class="key-badge">W</span> to activate the split wipe line.
  3. Drag the line across the canvas to wipe between the two versions. Press <span class="key-badge">Shift+W</span> to flip sides.
- **Technical Engine Mechanics:**  
  Implemented in `Viewport.paintGL()` and `openreview/models/comparison.py`. The fragment shader evaluates pixel positions against the linear plane equation: `dot(uv - wipePos, normal) > 0.0`.
- **Linked Figure:** `docs/html/assets/screenshots/viewport_ab_wipe_mode.png`

---

#### Feature: Continuous 360-Degree Wipe Angle Rotation
- **Purpose & Studio Context:** Diagonal elements (e.g. tilted horizons, telephone wires, angled light sabers) cannot be inspected cleanly with a vertical wipe line.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Angle dial and slider in the Wipe Controller HUD, or interactive drag near the wipe handle.
- **Step-by-Step Operator Guide:**
  1. Open the Wipe Controller HUD.
  2. Rotate the angle wheel to any arbitrary angle between `0.0°` and `360.0°`.
  3. The split divider rotates smoothly in real time across the screen.
- **Technical Engine Mechanics:**  
  Computes 2D rotation matrix normals: `normal = vec2(cos(rad), sin(rad))` passed as a uniform to the fragment shader.
- **Linked Figure:** `docs/html/assets/screenshots/hud_wipe_controller.png`

---

#### Feature: Difference Composite Mode with 20x Amplification
- **Purpose & Studio Context:** Verifying that areas of an image that were not supposed to be touched have zero pixel differences between plate and comp.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Blend Mode dropdown in the Wipe Controller HUD (select *Difference*).
- **Step-by-Step Operator Guide:**
  1. In the Wipe Controller HUD, change the comparison mode to *Difference*.
  2. Identical pixels render as pure black ($0.0$).
  3. Increase the *Diff Boost* multiplier slider (from `1.0x` up to `20.0x`) to amplify sub-perceptual differences, compression artifacts, or subtle edge fringing.
- **Technical Engine Mechanics:**  
  GLSL evaluation: `diff = abs(colorA.rgb - colorB.rgb) * uDiffBoost;`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_wipe_controller.png`

---

#### Feature: Inverted Difference Mode for Matte Edge Audits
- **Purpose & Studio Context:** Human eyes detect dark lines against white backdrops much more sensitively than faint bright lines against pure black.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Select *Difference (Inverted)* in the Wipe Controller HUD.
- **Step-by-Step Operator Guide:**
  1. Switch to *Difference (Inverted)* mode.
  2. Matching pixels render as pure solid white ($1.0$).
  3. Any pixel discrepancy appears as a crisp dark marking, instantly highlighting unintended camera plate shifts or matte leaks.
- **Technical Engine Mechanics:**  
  GLSL evaluation: `diff = vec3(1.0) - clamp(abs(colorA.rgb - colorB.rgb) * uDiffBoost, 0.0, 1.0);`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_wipe_controller.png`

---

#### Feature: Alpha Over & Additive Blend Modes
- **Purpose & Studio Context:** Live compositing of foreground RGBA elements over background plates directly inside the viewer, or checking optical light wrap integration via additive blending.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Blend Mode dropdown in Wipe Controller / Stacking HUD.
- **Step-by-Step Operator Guide:**
  1. Assign a foreground element with an alpha channel to Slot A and a background plate to Slot B.
  2. Select *Over* to evaluate the live composite with premultiplication handling.
  3. Select *Add* to evaluate additive glow, flare, or illumination passes.
- **Technical Engine Mechanics:**  
  Standard Porter-Duff Over composite implemented in GLSL: `result = colorA.rgb + colorB.rgb * (1.0 - colorA.a);`.
- **Linked Figure:** `docs/html/assets/screenshots/hud_media_stacking.png`

---

### Domain 8: Multi-Layer Stacks, Layouts & Contact Sheet Generation

---

#### Feature: Hierarchical Session Graph & Sources Dock
- **Purpose & Studio Context:** Managing dozens of loaded shot takes, background plates, CGI passes, audio tracks, and annotations within a unified project hierarchy.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">`</span> (Backtick) toggles Sources Dock.  
  - Panel: Left Sources & Session Dock.
- **Step-by-Step Operator Guide:**
  1. Open the Sources Dock (<span class="key-badge">`</span>).
  2. View loaded media organized by shot folders, version groups, and stacks.
  3. Drag and drop items to reorder priority, create comparison pairs, or assemble multi-clip playlists.
- **Technical Engine Mechanics:**  
  Built on a directed acyclic graph (DAG) model in `openreview/models/session_graph.py` and rendered via `openreview/ui/sources_panel.py`.
- **Linked Figure:** `docs/html/assets/screenshots/sources_session_dock.png`

---

#### Feature: Multi-Layer Stack Assembly & In-Place Layer Cycling
- **Purpose & Studio Context:** Grouping multiple lighting passes or comp iterations into a single stacked entity, allowing artists to flip between versions in place.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Z</span>: Cycle Stack Layer Forward (Next Layer)  
  - <span class="key-badge">Shift+Z</span>: Cycle Stack Layer Backward (Previous Layer)  
  - HUD: Media Stacking HUD
- **Step-by-Step Operator Guide:**
  1. Select several clips in the Sources dock and choose *Create Stack*.
  2. While paused or playing, tap <span class="key-badge">Z</span> to step through each layer in the stack without reloading media or changing playhead position.
  3. Open the Stacking HUD to configure per-layer blend modes and opacity faders.
- **Technical Engine Mechanics:**  
  `SessionGraph.cycle_stack_layer()` alters active layer pointers in the stack node, updating texture uploads with zero frame latency.
- **Linked Figure:** `docs/html/assets/screenshots/hud_media_stacking.png`

---

#### Feature: Dynamic Auto-Grid & Fixed Multi-Tile Contact Sheet Layouts
- **Purpose & Studio Context:** Evaluating shot-to-shot continuity across an entire sequence, or viewing multiple lighting passes side-by-side simultaneously.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Layout selector dropdown on the top bar or Stacking HUD.
- **Step-by-Step Operator Guide:**
  1. Select all clips in a sequence and create a *Layout View*.
  2. Choose between `Auto Grid`, `Side-by-Side (1x2)`, `Over/Under (2x1)`, `2x2 Quad Split`, or `3x3 Nine-Up` matrices.
  3. All tiles scrub and play in synchronized lockstep.
- **Technical Engine Mechanics:**  
  `LayoutCompositor` calculates grid cells based on active viewport aspect ratio, binding multi-texture units and rendering each tile to its calculated normalized screen coordinates.
- **Linked Figure:** `docs/html/assets/screenshots/hud_media_stacking.png`

---

### Domain 9: Multi-Part OpenEXR AOVs & Stereoscopic 3D Workflows

---

#### Feature: Multi-Part & Multi-Channel OpenEXR Demuxing
- **Purpose & Studio Context:** CGI lighting renders output multi-channel OpenEXR files containing dozens of Arbitrary Output Variables (AOVs) like diffuse, specular, depth, normals, and Cryptomattes.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+L</span>  
  - HUD: OpenEXR Layers HUD
- **Step-by-Step Operator Guide:**
  1. Open a multi-part OpenEXR file.
  2. Press <span class="key-badge">Ctrl+L</span> to open the EXR Layers HUD.
  3. Click any pass (e.g. `diffuse_direct`, `specular_indirect`, `depth.Z`) to isolate and view that specific channel in the viewport.
- **Technical Engine Mechanics:**  
  `openreview/readers/exr_reader.py` demuxes OpenEXR channel hierarchies via OpenEXR bindings, mapping selected channels into active texture buffers.
- **Linked Figure:** `docs/html/assets/screenshots/hud_exr_layers.png`

---

#### Feature: Automated EXR Multi-AOV Contact Sheet Generator
- **Purpose & Studio Context:** Lighting leads need an instant contact sheet showing all embedded passes of a CG frame to audit pass balance at a glance.
- **UI Access & Keyboard Shortcuts:**  
  - Menu: *Media &gt; Generate EXR AOV Contact Sheet*
- **Step-by-Step Operator Guide:**
  1. Load an EXR frame containing multiple AOVs.
  2. Select *Generate EXR AOV Contact Sheet*.
  3. OpenReview extracts all embedded passes and builds an interactive multi-tile contact sheet displaying beauty, diffuse, specular, normal, and depth passes simultaneously.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/core/exr_contact_sheet.py`, extracting channel buffers and assembling them into a composite contact sheet layout.
- **Linked Figure:** `docs/html/assets/screenshots/hud_exr_layers.png`

---

#### Feature: Stereoscopic 3D Display Modes & Parallax Convergence
- **Purpose & Studio Context:** Reviewing theatrical 3D stereoscopic productions to calibrate eye disparity and verify depth planes without visual discomfort.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Alt+S</span>  
  - HUD: Stereoscopic 3D HUD
- **Step-by-Step Operator Guide:**
  1. Load stereoscopic media (separate `_L`/`_R` files or packed streams).
  2. Open the Stereo 3D HUD (<span class="key-badge">Ctrl+Alt+S</span>).
  3. Select your display mode: *Red-Cyan Anaglyph* (for standard 3D glasses), *Interlaced* (for polarized 3D monitors), or *Side-by-Side*.
  4. Adjust the *Parallax Convergence* slider in real time to shift zero-depth planes.
- **Technical Engine Mechanics:**  
  `openreview/widgets/hud_stereo.py` binds Left and Right textures to `uTextureA` and `uTextureB`, blending channels in GLSL based on the selected stereo presentation matrix.
- **Linked Figure:** `docs/html/assets/screenshots/hud_stereo_3d.png`

---

### Domain 10: Vector Markup, Frame Annotations & Collaborative Review Notes

---

#### Feature: Non-Destructive Vector Drawing Toolbox
- **Purpose & Studio Context:** Supervisors and art directors draw feedback directly onto frames to communicate roto fixes, paint patches, and lighting notes.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">X</span>: Toggle Floating Vector Markup Palette  
  - <span class="key-badge">D</span>: Activate Freehand Pen Drawing Tool  
  - <span class="key-badge">Delete</span>: Clear Annotations on Current Frame
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">X</span> to reveal the floating markup palette.
  2. Select from Freehand Pen (<span class="key-badge">D</span>), Straight Line, Directed Arrow, Bounding Rectangle, or Circle.
  3. Pick a swatch color and brush width, then draw directly over the canvas.
  4. Vector strokes are tied to the exact frame where drawn.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/models/annotations.py`. Strokes are stored as normalized vector coordinate paths $[0.0, 1.0]$, ensuring sharpness regardless of viewport zoom level.
- **Linked Figure:** `docs/html/assets/screenshots/floating_annotation_palette.png`

---

#### Feature: In-Canvas Text Callouts
- **Purpose & Studio Context:** Typing concise art direction notes directly onto the review canvas anchored to specific spatial elements.
- **UI Access & Keyboard Shortcuts:**  
  - Access: Text Tool icon on the Markup Palette (<span class="key-badge">X</span>).
- **Step-by-Step Operator Guide:**
  1. Select the Text Tool from the palette.
  2. Click on the canvas where the note should appear.
  3. Type your feedback (e.g. "Check comp edge grain integration").
  4. Click outside to commit the vector text callout.
- **Technical Engine Mechanics:**  
  Stored as `ShapeType.TEXT` in `AnnotationStore` with font size, family, and screen-space anchor points rendered via `QPainter` overlay passes.
- **Linked Figure:** `docs/html/assets/screenshots/viewport_annotations_huds.png`

---

#### Feature: Two-Pass Vector Anti-Aliasing & Temporal Onion Skinning
- **Purpose & Studio Context:** Providing ultra-responsive interactive drawing during mouse movement while producing smooth, publication-grade anti-aliased curves upon release.
- **UI Access & Keyboard Shortcuts:**  
  - <span class="key-badge">Shift+O</span>: Toggle Temporal Onion Skinning
- **Step-by-Step Operator Guide:**
  1. Draw a curve with the pen tool. During interaction, a rapid draft path renders smoothly.
  2. Upon releasing the mouse button, OpenReview smooths points and renders anti-aliased geometry.
  3. Press <span class="key-badge">Shift+O</span> to display ghosted transparent outlines of drawings on neighboring frames to check animation arcs.
- **Technical Engine Mechanics:**  
  Applies Catmull-Rom spline interpolation to stroke points on mouse release. Onion skinning samples annotations from $F-1$ and $F+1$ with 35% alpha.
- **Linked Figure:** `docs/html/assets/screenshots/viewport_annotations_huds.png`

---

#### Feature: Multi-Frame Annotation Manager HUD & PDF Dailies Export
- **Purpose & Studio Context:** Reviewing all notes across a sequence and publishing executive PDF review decks for production departments.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+A</span>  
  - HUD: Annotation Manager HUD
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+A</span> to open the Annotation Manager.
  2. Browse the table of all annotated frames, stroke counts, and note summaries.
  3. Click any row to jump the timeline directly to that note.
  4. Click *Export PDF Report* to compile all annotated frames into a formatted multi-page PDF review document.
- **Technical Engine Mechanics:**  
  `openreview/export/pdf_exporter.py` compiles annotated frame snapshots in native viewer colorspace into high-resolution PDF pages with timecode stamps and note text.
- **Linked Figure:** `docs/html/assets/screenshots/hud_annotation_manager.png`

---

### Domain 11: Sub-Frame Audio Synchronization & Remote Dailies Sync

---

#### Feature: High-Fidelity Audio Engine & Sub-Frame Lip-Sync Calibration
- **Purpose & Studio Context:** Playing sync sound alongside visual sequences and slipping audio tracks to correct 2-pop sync leader offsets.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+U</span>  
  - HUD: Audio Settings HUD
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+U</span> to open Audio Settings.
  2. View live waveform envelopes, peak dB meters, and volume faders.
  3. Use the *Slip Offset* controls to nudge audio forward or backward in millisecond or frame increments to lock lip-sync.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/audio/audio_engine.py` using `QtMultimedia`. Compares hardware audio buffers against monotonic clock timestamps, executing sub-frame resync if drift exceeds 45ms.
- **Linked Figure:** `docs/html/assets/screenshots/hud_audio_settings.png`

---

#### Feature: Sub-Frame Audio Scrubbing Bursts
- **Purpose & Studio Context:** Allowing animators and editors to hear dialogue phonemes and transient audio hits while manually dragging the playhead.
- **UI Access & Keyboard Shortcuts:**  
  - Enabled automatically during timeline or canvas drag-scrubbing.
- **Step-by-Step Operator Guide:**
  1. Drag the timeline playhead or drag horizontally across the canvas.
  2. As you scrub back and forth across frames, brief 60ms audio slices play cleanly without audio distortion or buffer popping.
- **Technical Engine Mechanics:**  
  `AudioEngine.scrub_at_frame()` calculates the target millisecond offset, plays a 60ms slice, and arms a single-shot timer that pauses the buffer cleanly.
- **Linked Figure:** `docs/html/assets/screenshots/hud_audio_settings.png`

---

#### Feature: Multi-User Remote Dailies Sync
- **Purpose & Studio Context:** Enabling distributed teams across studios to conduct synchronized dailies reviews over local network or VPN without video-conferencing compression artifacts.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+D</span>  
  - HUD: Remote Dailies Sync HUD
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+D</span> to open the Dailies Sync HUD.
  2. Host a review room or enter the IP address of an existing room.
  3. Once connected, transport playback, JKL shuttling, frame seeking, and vector drawing strokes synchronize across all participants in lockstep.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/network/sync_client.py` and `sync_engine.py` over low-latency WebSockets. Each participant reviews uncompressed local EXRs while transport and annotation states broadcast in real time.
- **Linked Figure:** `docs/html/assets/screenshots/hud_dailies_sync.png`

---

### Domain 12: Python Scripting SDK, DCC Pipelines, Package Manager & Media Export

---

#### Feature: Python 3.10+ Scripting SDK & IPC Protocol
- **Purpose & Studio Context:** Automating review workflows, loading shots from production databases (ShotGrid, Ftrack, Kitsu), and scripting pipeline interactions.
- **UI Access & Keyboard Shortcuts:**  
  - Python import: `from openreview.sdk import OpenReviewClient`
- **Step-by-Step Operator Guide:**
  1. In your studio script or DCC Python terminal:
     ```python
     from openreview.sdk import OpenReviewClient
     client = OpenReviewClient(host="127.0.0.1", port=45124)
     client.open_media("/shots/sq01/sh010/renders/v002/sh010.####.exr")
     client.set_exposure(0.5)
     client.play()
     ```
  2. OpenReview receives the command and executes it immediately.
- **Technical Engine Mechanics:**  
  `openreview/network/ipc_server.py` listens on TCP port `45124`, dispatching JSON-RPC 2.0 requests to the application orchestrator on the main thread.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_console_window.png`

---

#### Feature: Extensible Package & Plugin Manager
- **Purpose & Studio Context:** Allowing studios to author and distribute custom Python plugins, custom dock widgets, and pipeline hooks without modifying OpenReview core code.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+P</span>  
  - Menu: *Tools &gt; Package Manager*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+P</span> to view installed plugins.
  2. Discover, enable, disable, or install plugins from `.zip` packages.
  3. Built-in packages like `xtra-qc-Utils` can be managed directly from this dialog.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/packages/package_manager.py`. Scans directories for `manifest.json` files and loads `OpenReviewPlugin` subclasses dynamically.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_package_manager.png`

---

#### Feature: Multi-Format Transcode & Media Export Engine
- **Purpose & Studio Context:** Transcoding review sequences, marked In/Out ranges, or single annotated snapshots to industry formats for client delivery or editorial turnover.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+E</span>  
  - Menu: *File &gt; Export Media...*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+E</span> to open the Export dialog.
  2. Choose export range (*Current Frame*, *In/Out Range*, *All Frames*, or *Annotated Frames Only*).
  3. Select output format: Apple ProRes (Proxy, LT, 422, 4444), DNxHD, H.264 MP4, 16/32-bit OpenEXR, DPX, TIFF, or PNG.
  4. Select downrez resolution scaling (100%, 50%, 25%, Custom) and colorspace options, then click *Export*.
- **Technical Engine Mechanics:**  
  Multi-threaded export in `openreview/ui/export_dialog.py` and `openreview/core/exporter.py` reading raw frames and piping through FFmpeg or OpenEXR encoders.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_export_media.png`

---

#### Feature: Diagnostic Console Window with Auto-Popup on Error
- **Purpose & Studio Context:** Tracking system warnings, OCIO shader compilation messages, reader bandwidth, and Python tracebacks during studio operation.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">Ctrl+Shift+L</span>  
  - Menu: *Help &gt; Diagnostic Console*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">Ctrl+Shift+L</span> to open the Console Window.
  2. Filter logs by severity (*DEBUG*, *INFO*, *WARNING*, *ERROR*, *CRITICAL*) or subsystem source (`app`, `gpu`, `cache`, `ocio`, `reader`).
  3. If an unhandled exception or file decoding failure occurs, the window automatically pops up with the relevant log entry highlighted.
- **Technical Engine Mechanics:**  
  `openreview/ui/console_window.py` hooks standard logging handlers and Python `sys.excepthook`, recording structured timestamped records.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_console_window.png`

---

#### Feature: Studio About & Interactive License Inspector
- **Purpose & Studio Context:** Viewing application versioning, system telemetry, and inspecting all third-party open-source dependency licenses and copyright notices for studio compliance.
- **UI Access & Keyboard Shortcuts:**  
  - Shortcut: <span class="key-badge">F1</span>  
  - Menu: *Help &gt; About OpenReview*
- **Step-by-Step Operator Guide:**
  1. Press <span class="key-badge">F1</span> to open the About dialog.
  2. The *Overview* tab displays version `1.0.1`, author attribution (**Maruthu Chakravarthi**), and core system telemetry.
  3. The *Licenses* tab provides an interactive master-detail browser listing all dependencies (PySide6, NumPy, Pillow, OpenCV, PyOpenColorIO, etc.) with real-time text search and copy-to-clipboard utilities.
- **Technical Engine Mechanics:**  
  Implemented in `openreview/ui/about_dialog.py` querying structured metadata from `openreview/resources/licenses.py`.
- **Linked Figure:** `docs/html/assets/screenshots/dialog_about.png`

---

## 2. Complete Keyboard Shortcuts Matrix (All 85+ Actions)

| Domain | Action ID | Action Description | Default Shortcut & Key Aliases |
| :--- | :--- | :--- | :--- |
| **Playback** | `playback.toggle` | Toggle Play / Pause | <span class="key-badge">Space</span> |
| **Playback** | `playback.shuttle_rev` | Shuttle Reverse (-1x, -2x, -4x, -8x) | <span class="key-badge">J</span> |
| **Playback** | `playback.shuttle_stop` | Shuttle Stop (Halt Playhead) | <span class="key-badge">K</span> |
| **Playback** | `playback.shuttle_fwd` | Shuttle Forward (1x, 2x, 4x, 8x) | <span class="key-badge">L</span> / <span class="key-badge">Shift+L</span> |
| **Playback** | `playback.step_fwd` / `step_back` | Step 1 Frame Forward / Backward | <span class="key-badge">Right</span> / <span class="key-badge">Left</span> |
| **Playback** | `playback.step_fwd_10` / `step_back_10` | Step 10 Frames Forward / Backward | <span class="key-badge">Shift+Right</span> / <span class="key-badge">Shift+Left</span> |
| **Playback** | `playback.first_frame` / `last_frame` | Jump to First Frame / Last Frame | <span class="key-badge">Home</span> / <span class="key-badge">End</span> |
| **Playback** | `app.toggle_cache` | Start In/Out Region RAM Caching | <span class="key-badge">Shift+C</span> |
| **Timeline** | `timeline.toggle_timecode` | Toggle SMPTE Timecode vs. Frame Count | <span class="key-badge">Ctrl+T</span> |
| **Timeline** | `timeline.goto_frame` | Open Frameless Go-To Frame Modal | <span class="key-badge">Ctrl+G</span> |
| **Timeline** | `timeline.magnifier_toggle` | Toggle Timeline Magnifier Mini-Ruler | <span class="key-badge">Shift+T</span> |
| **Timeline** | `timeline.zoom_in` / `zoom_out` | Zoom Timeline Scrubber In / Out | <span class="key-badge">Ctrl+=</span> / <span class="key-badge">Ctrl+-</span> |
| **Marking** | `mark.in` / `mark.out` | Set In Point / Set Out Point | <span class="key-badge">[</span> / <span class="key-badge">]</span> |
| **Marking** | `mark.clear_in_out` | Clear Both In and Out Points | <span class="key-badge">\</span> |
| **Marking** | `mark.clear_in` / `clear_out` | Clear In Point / Clear Out Point | <span class="key-badge">Alt+I</span> / <span class="key-badge">Alt+O</span> |
| **Marking** | `mark.bookmark_toggle` | Toggle Frame Bookmark Flag | <span class="key-badge">M</span> |
| **Marking** | `mark.bookmark_next` / `prev` | Jump to Next / Previous Bookmark | <span class="key-badge">Alt+Right</span> / <span class="key-badge">Alt+Left</span> |
| **Marking** | `mark.bookmark_segment_next` / `prev` | Jump Next / Previous Bookmark Segment | <span class="key-badge">PageDown</span> / <span class="key-badge">PageUp</span> |
| **Channels** | `channel.rgb` | Restore Full RGB Channels | <span class="key-badge">C</span> |
| **Channels** | `channel.red` | Solo Red Channel as Monochrome | <span class="key-badge">R</span> |
| **Channels** | `channel.green` | Solo Green Channel as Monochrome | <span class="key-badge">G</span> |
| **Channels** | `channel.blue` | Solo Blue Channel as Monochrome | <span class="key-badge">B</span> |
| **Channels** | `channel.alpha` | Solo Alpha Channel as Monochrome | <span class="key-badge">A</span> |
| **Channels** | `channel.luma` | Solo Rec.709 Luminance Channel | <span class="key-badge">Y</span> |
| **Color** | `color.invert_toggle` | **Toggle Full Display Invert Colors** | **<span class="key-badge">Shift+I</span>** |
| **Color** | `color.gain_up` / `gain_down` | Adjust Linear Gain (+0.10 / -0.10) | <span class="key-badge">+</span> / <span class="key-badge">-</span> |
| **Color** | `color.exp_up` / `exp_down` | Adjust F-Stop Exposure (+0.25 / -0.25 EV) | <span class="key-badge">Alt++</span> / <span class="key-badge">Alt+-</span> |
| **Color** | `color.gamma_up` / `gamma_down` | Adjust Gamma (+0.05 / -0.05) | <span class="key-badge">Shift++</span> / <span class="key-badge">Shift+-</span> |
| **Color** | `color.sat_up` / `sat_down` | Adjust Saturation (+0.05 / -0.05) | <span class="key-badge">Ctrl+Shift++</span> / <span class="key-badge">Ctrl+Shift+-</span> |
| **Color** | `color.exp_reset` | Reset Exposure to 0.0 EV | <span class="key-badge">Ctrl+Alt+E</span> / <span class="key-badge">E</span> |
| **Color** | `color.gamma_reset` | Reset Gamma to 1.0 | <span class="key-badge">Ctrl+Alt+G</span> |
| **Color** | `color.reset_all` | Reset All Color Grading Adjustments | <span class="key-badge">Ctrl+Alt+R</span> / <span class="key-badge">Shift+Home</span> |
| **Color** | `color.adjustments` | Open Interactive Color Adjustments HUD | <span class="key-badge">/</span> |
| **Color** | `color.ocio_toggle` | Toggle OpenColorIO Display Transform | <span class="key-badge">Ctrl+Shift+O</span> |
| **View** | `view.fit` | Fit Canvas to Viewport | <span class="key-badge">F</span> |
| **View** | `view.fit_width` | Fit Canvas to Viewport Width | <span class="key-badge">Alt+F</span> |
| **View** | `view.actual_size` | Zoom to 100% 1:1 Pixel Mapping | <span class="key-badge">1</span> |
| **View** | `view.zoom_100` / `200` / `400` / `800` | Preset Zoom Scales (100% – 800%) | <span class="key-badge">Ctrl+1</span> / <span class="key-badge">Ctrl+2</span> / <span class="key-badge">Ctrl+4</span> / <span class="key-badge">Ctrl+8</span> |
| **View** | `view.flop_x` / `flip_y` | Flop Horizontal / Flip Vertical Mirror | <span class="key-badge">Shift+X</span> / <span class="key-badge">Shift+Y</span> |
| **View** | `view.filter_toggle` | Toggle Bilinear / Nearest Filtering | <span class="key-badge">N</span> |
| **View** | `view.fullscreen` | Toggle Fullscreen (Taskbar Hidden) | <span class="key-badge">F12</span> |
| **View** | `view.presentation` | Toggle Clean Presentation Mode | <span class="key-badge">Ctrl+P</span> |
| **View** | `view.matte_cycle` | Cycle Aspect Masking Mattes | <span class="key-badge">Ctrl+M</span> |
| **View** | `view.matte_opacity_cycle`| Cycle Aspect Matte Opacity (25%-100%) | <span class="key-badge">Shift+M</span> |
| **View** | `view.safe_guides` | Toggle Title/Action Safe & Center Cross | <span class="key-badge">Shift+G</span> |
| **View** | `view.onion_skin` | Toggle Temporal Onion Skinning | <span class="key-badge">Shift+O</span> |
| **View** | `view.pixel_inspector` | Toggle Area Pixel Inspector | <span class="key-badge">F5</span> / <span class="key-badge">Alt+C</span> |
| **Wipe & QC** | `hud.wipe` | Toggle A/B Split Wipe Mode | <span class="key-badge">W</span> |
| **Wipe & QC** | `hud.wipe_flip_orientation` | Flip Wipe Orientation (Left/Right) | <span class="key-badge">Shift+W</span> |
| **Wipe & QC** | `hud.wipe_reset` | Reset Wipe Position to 50% Center | <span class="key-badge">Alt+W</span> |
| **Wipe & QC** | `app.toggle_comp_qc` | **Toggle xtra QC Utils Suite Dock & HUD** | **<span class="key-badge">Q</span>** |
| **Stacks** | `stack.cycle_fwd` / `cycle_bwd` | Cycle Stack Layer Up / Down In-Place | <span class="key-badge">Z</span> / <span class="key-badge">Shift+Z</span> |
| **Layers** | `hud.exr_layers` | Open OpenEXR AOV Layer Selection HUD | <span class="key-badge">Ctrl+L</span> |
| **Stereo 3D** | `hud.stereo_3d` | Open Stereoscopic 3D Control HUD | <span class="key-badge">Ctrl+Alt+S</span> |
| **Playlist** | `playlist.toggle` | Toggle Sources & Session Manager Dock | <span class="key-badge">`</span> (Backtick) |
| **Versions** | `version.up` / `version.down` | Pipeline Version Increment / Decrement | <span class="key-badge">Alt+Up</span> / <span class="key-badge">Alt+Down</span> |
| **HUDs** | `hud.histogram` | Toggle Real-Time RGB Histogram HUD | <span class="key-badge">H</span> |
| **HUDs** | `hud.source_details` | Toggle Source Media Details HUD | <span class="key-badge">I</span> |
| **HUDs** | `hud.info_strip` | Toggle Canvas Info Overlay Strip | <span class="key-badge">Ctrl+I</span> |
| **HUDs** | `hud.audio_settings` | Toggle Audio Settings & Mixer HUD | <span class="key-badge">Ctrl+Shift+U</span> |
| **HUDs** | `hud.dailies_sync` | Toggle Remote Dailies Sync Room HUD | <span class="key-badge">Ctrl+Shift+D</span> |
| **HUDs** | `view.toggle_file_browser` | Toggle Embedded File Browser Dock | <span class="key-badge">Ctrl+B</span> |
| **HUDs** | `app.console_window` | Open Diagnostic Console Logger | <span class="key-badge">Ctrl+Shift+L</span> |
| **Annotations**| `annot.toggle_palette` | Toggle Floating Vector Markup Palette | <span class="key-badge">X</span> |
| **Annotations**| `annot.toggle_pen` | Activate Freehand Pen Drawing Tool | <span class="key-badge">D</span> |
| **Annotations**| `annot.undo` / `redo` | Undo / Redo Vector Stroke on Frame | <span class="key-badge">Ctrl+Z</span> / <span class="key-badge">Ctrl+Shift+Z</span> |
| **Annotations**| `annot.clear_frame` | Clear All Annotations on Current Frame | <span class="key-badge">Delete</span> |
| **Annotations**| `annot.next_keyframe` / `prev` | Jump to Next / Previous Annotated Frame | <span class="key-badge">.</span> / <span class="key-badge">,</span> |
| **Annotations**| `annot.manager` | Open Multi-Frame Annotation Manager | <span class="key-badge">Ctrl+Shift+A</span> |
| **Sessions** | `session.new` | Create New Clean Session | <span class="key-badge">Ctrl+N</span> |
| **Sessions** | `session.close` | **Close Current Session & Clear Memory** | **<span class="key-badge">Ctrl+Shift+N</span>** |
| **Sessions** | `session.open_media` | Open Media File or Image Sequence | <span class="key-badge">Ctrl+O</span> |
| **Sessions** | `session.open` | Open Saved Review Session File (`.ovr`)| <span class="key-badge">Ctrl+Shift+O</span> |
| **Sessions** | `session.save` / `save_as` | Save Session / Save Session As | <span class="key-badge">Ctrl+S</span> / <span class="key-badge">Ctrl+Shift+S</span> |
| **Export** | `session.export` | Open Media Transcode & Sequence Export | <span class="key-badge">Ctrl+Shift+E</span> |
| **Packages** | `app.package_manager` | Open Package & Plugin Manager | <span class="key-badge">Ctrl+Shift+P</span> |
| **Cache** | `media.reload_frame` | Invalidate & Reload Active Frame | <span class="key-badge">Ctrl+R</span> |
| **Cache** | `media.reload_sequence` | Invalidate & Reload Active Sequence | <span class="key-badge">Ctrl+Shift+R</span> |
| **Cache** | `app.clear_cache` | Purge Active Source RAM Cache | <span class="key-badge">Ctrl+Shift+C</span> |
| **Cache** | `app.clear_all_cache` | **Flush Entire Workspace RAM/Disk Cache** | **<span class="key-badge">Ctrl+Delete</span>** |
| **App** | `app.preferences` | Open Workstation Preferences Dialog | <span class="key-badge">Ctrl+,</span> |
| **App** | `app.about` | Open Studio About & License Inspector | <span class="key-badge">F1</span> |
| **App** | `app.escape` | Cancel Active Tool / Dismiss Floating HUD| <span class="key-badge">Escape</span> |
| **App** | `app.quit` | Terminate Application Cleanly | <span class="key-badge">Ctrl+Q</span> |

---

## 3. High-Resolution Screenshot Gallery

All 36 official UI screenshots captured directly from running OpenReview workstation instances:

- **Primary Studio Workspace Overview:** `docs/html/assets/screenshots/workspace_overview.png`
- **Workspace with Embedded File Browser:** `docs/html/assets/screenshots/workspace_with_file_browser.png`
- **Top Control Bar Toolbar:** `docs/html/assets/screenshots/top_control_bar.png`
- **Timeline Transport Dock:** `docs/html/assets/screenshots/timeline_transport_dock.png`
- **Status Bar Telemetry:** `docs/html/assets/screenshots/status_bar.png`
- **Sources & Session Graph Dock:** `docs/html/assets/screenshots/sources_session_dock.png`
- **Pipeline File Browser Dock:** `docs/html/assets/screenshots/file_browser_dock.png`
- **Floating Vector Markup Palette:** `docs/html/assets/screenshots/floating_annotation_palette.png`
- **xtra QC Utils Compositing Suite (Comp QC):** `docs/html/assets/screenshots/hud_comp_qc.png`
- **Color Adjustments HUD:** `docs/html/assets/screenshots/hud_color_adjustments.png`
- **OpenColorIO v2 Config HUD:** `docs/html/assets/screenshots/hud_ocio_config.png`
- **A/B Split Wipe Controller HUD:** `docs/html/assets/screenshots/hud_wipe_controller.png`
- **Real-Time RGB Histogram HUD:** `docs/html/assets/screenshots/hud_histogram.png`
- **Color Inspector & Region Sampler HUD:** `docs/html/assets/screenshots/hud_color_inspector.png`
- **Media Stacking & Layouts HUD:** `docs/html/assets/screenshots/hud_media_stacking.png`
- **OpenEXR Multi-Layer Passes HUD:** `docs/html/assets/screenshots/hud_exr_layers.png`
- **Stereoscopic 3D HUD:** `docs/html/assets/screenshots/hud_stereo_3d.png`
- **Annotation & Review Notes Manager HUD:** `docs/html/assets/screenshots/hud_annotation_manager.png`
- **Source Media Technical Details HUD:** `docs/html/assets/screenshots/hud_source_details.png`
- **Audio Settings & Mixer HUD:** `docs/html/assets/screenshots/hud_audio_settings.png`
- **Remote Dailies Sync Room HUD:** `docs/html/assets/screenshots/hud_dailies_sync.png`
- **Studio About & License Inspector Dialog:** `docs/html/assets/screenshots/dialog_about.png`
- **Diagnostic Console Window:** `docs/html/assets/screenshots/dialog_console_window.png`
- **Media Transcode & Sequence Export Dialog:** `docs/html/assets/screenshots/dialog_export_media.png`
- **Package & Plugin Manager Dialog:** `docs/html/assets/screenshots/dialog_package_manager.png`
- **Process Info & Performance Telemetry:** `docs/html/assets/screenshots/dialog_process_info.png`
- **Frameless Go-To Frame Modal:** `docs/html/assets/screenshots/dialog_goto_frame.png`
- **Preferences: General & Playback:** `docs/html/assets/screenshots/dialog_preferences_general_and_playback.png`
- **Preferences: GPU Acceleration:** `docs/html/assets/screenshots/dialog_preferences_gpu_acceleration.png`
- **Preferences: Two-Tier Caching:** `docs/html/assets/screenshots/dialog_preferences_caching.png`
- **Preferences: Keyboard Shortcuts:** `docs/html/assets/screenshots/dialog_preferences_keyboard_shortcuts.png`
- **Viewport: A/B Split Wipe Mode:** `docs/html/assets/screenshots/viewport_ab_wipe_mode.png`
- **Viewport: Vector Markup & Color HUDs:** `docs/html/assets/screenshots/viewport_annotations_huds.png`
- **Viewport: Out-of-Range High-Contrast Zebra:** `docs/html/assets/screenshots/viewport_out_of_range.png`
- **Viewport: Safe Area Guides & Theatrical Mattes:** `docs/html/assets/screenshots/viewport_safe_guides_matte.png`
