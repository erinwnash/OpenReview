# OpenReview Complete Features & Keyboard Shortcuts Guide

**Author:** Maruthu Chakravarthi  
**Version:** 1.0.0  
**Interactive HTML Version:** [docs/html/features.html](file:///e:/works/Pipeline/code/OpenReview/docs/html/features.html)

---

## 1. Complete Feature Set

### 1.1 Playback, JKL Shuttling & Timecode (`core/clock.py`, `widgets/timeline.py`)
- **Real-Time vs. Play Every Frame:** Switch between strict wall-clock sync and sequential frame-accurate playback.
- **JKL Multi-Speed Shuttling:** `J` reverses (`-1x`, `-2x`, `-4x`, `-8x`), `K` stops (`1.0x`), and `L` shuttles forward (`1x`, `2x`, `4x`, `8x`).
- **Loop Modes:** Forward Loop, Ping-Pong (Bidirectional Bounce), and Play Once.
- **SMPTE Timecode & Go-To Frame:** Toggle Frame Numbers vs. `HH:MM:SS:FF` SMPTE Timecode (`Ctrl+T`), open the frameless Go-To Frame modal (`Ctrl+G`), and toggle the Magnified Timeline Mini-Ruler (`Shift+T`).
- **Frame Count & In/Out Duration Indicator:** Dedicated label before Clear In/Out displaying total clip frame count or selected region frame duration in real time.
- **Interactive Canvas Scrubbing:** Left-mouse drag horizontally on the viewport canvas to scrub frames with live 60ms audio bursts.

### 1.2 Asynchronous Two-Tier RAM/Disk Caching & GPU Acceleration (`core/cache.py`, `core/async_source_loader.py`)
- **AsyncSourceLoader:** Non-blocking multi-threaded loader for heavy multi-part EXRs and video assets with cancellation tokens and real-time load progress.
- **Two-Tier Cache Architecture:**
  - **Tier 1 (RAM RingBufferCache):** Fast in-memory frame cache (1 GB – 64 GB RAM budget) with four strategies: `Off`, `Play-Ahead` (80% forward / 20% behind), `In/Out Region` (`Shift+C`), and `Cache All`.
  - **Tier 2 (Persistent DiskCache):** High-speed serialized disk cache preserving pre-decoded frames beyond physical RAM boundaries.
- **Granular Reload & Eviction:** Reload single frame (`Ctrl+R`), reload active sequence (`Ctrl+Shift+R`), clear active cache (`Ctrl+Shift+C`), or clear all source caches (`Ctrl+Delete`).
- **Three Selectable GPU Playback Engines:** `opengl_core` (OpenGL 3.3+ Core Profile), `async_pbo` (Double-Buffered Pixel Buffer Object DMA streaming), and `software_safe`.

### 1.3 Color Science, LUT/CDL & OpenColorIO v2 (`color/shader_builder.py`, `color/ocio_manager.py`)
- **Scene-Linear Exposure & Gain:** Coupled F-stop EV (`Alt++` / `Alt+-`) and linear Gain (`+` / `-`), with one-click reset (`Ctrl+Alt+E` / `E`).
- **Gamma, Contrast, Saturation & Hue:** Interactive Color Adjustments HUD (`/`) with master and per-channel R/G/B grading, 18% grey pivot contrast, hue rotation (`-180°..+180°`), and display brightness.
- **Invert Colors (`Shift+I`) & Out-of-Range Zebra:** Instant display-space RGB inversion (`Shift+I`) and Magenta (`>1.0`) / Cyan (`<0.0`) clipping indicators.
- **Hardware 3D LUT & ASC CDL:** Load `.cube` / `.3dl` 3D LUTs and `.cdl` / `.cc` / `.ccc` ASC CDL grades with independent bypass toggles.
- **Channel Isolation:** Single-key soloing for `RGB` (`C`), `Red` (`R`), `Green` (`G`), `Blue` (`B`), `Alpha` (`A`), and Rec.709 `Luminance` (`Y`).

### 1.4 A/B Split Wipes, Difference Modes, Stacks & Layouts
- **Interactive Split Wipe (`W`):** Translate wipe position and rotate wipe angle (`0°–360°`) directly on canvas; flip orientation (`Shift+W`) or reset (`Alt+W`).
- **Six Composite Modes:** `Replace`, `Sequence`, `Over (Alpha Composite)`, `Add`, `Difference`, and `Difference (Inverted)` with up to `20x` Difference Boost.
- **Multi-Layer Stacks (`Z` / `Shift+Z`) & Tiled Layouts:** Cycle stack layers in place (`Z` / `Shift+Z`) or view multi-clip contact sheets (`Auto Grid`, `Side-by-Side`, `Over/Under`, `2x2`, `3x3`).

### 1.5 Area Pixel Analyzer, Samplers & EXR Tools (`widgets/hud_layers.py`, `core/exr_contact_sheet.py`)
- **Pixel Analyzer & Area Sampler (`F5` / `Alt+C`):** Eyedropper area analyzer measuring real-time Min, Max, Average, and Median statistics with color swatch previews.
- **NaN / Inf / Negative Pixel QC:** Instant detection and counting of floating-point `NaN`, `Inf`, and negative values in sampled regions.
- **Live RGB Histogram (`H`):** Real-time luminance and RGB distribution graph.
- **EXR Multi-Layer Contact Sheet:** Automated tiling of all AOVs (Diffuse, Specular, Normal, Cryptomatte, Depth) into a multi-part contact sheet matrix.
- **EXR Metadata Inspector:** Comprehensive header viewer displaying data window, display window, compression, channels, parts, and chromaticities.

### 1.6 Vector Markup, Annotation Manager & Export Pipeline
- **Vector Annotations (`X` / `D`):** Freehand pen (`D`), line, arrow, rectangle, circle, and in-canvas text callouts (`X`) with per-frame Undo (`Ctrl+Z`) and Redo (`Ctrl+Shift+Z`).
- **Smooth Anti-Aliasing on Release:** Draws responsive draft strokes during interaction, then applies smoothing and anti-aliasing upon mouse release.
- **Transparent Slider Controls:** Clean, distraction-free brush width and opacity sliders.
- **Annotation Manager (`Ctrl+Shift+A`):** Multi-frame notes manager with non-blocking PDF and PNG export featuring real-time progress bar feedback.
- **Accurate Colorspace Export:** Annotated snapshots rendered in the user's active input colorspace with screenspace color corrections applied.
- **Comprehensive Media Export (`Ctrl+Shift+E`):** Export single frames or sequences to EXR, MOV (ProRes, DNxHD, H.264), DPX, TIFF, and PNG with selectable downrez scaling and colorspace conversion.

### 1.7 Diagnostics, File Associations & Ergonomics
- **Live Console Window (`Ctrl+Shift+L`):** Embedded logger with level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL) and auto-popup on error logs.
- **System File Associations:** Desktop and shell integration for `.exr`, `.dpx`, `.cin`, `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`, `.mov`, `.mp4`, `.ovr`.
- **Low-Resolution Optimization:** Fully responsive layout and controls adapted for 1920x1080 Full HD displays.
- **Taskbar Handling in Fullscreen:** Fullscreen (`F12`) and Presentation (`Ctrl+P`) modes conceal the OS taskbar completely for clean viewing.

---

## 2. Authoritative Keyboard Shortcuts Registry (All 80+ Actions)

| Category | Action ID | Action Name | Default Shortcut & Aliases |
| :--- | :--- | :--- | :--- |
| **Playback** | `playback.toggle` | Toggle Playback | `Space` |
| **Playback** | `playback.shuttle_rev` | Shuttle Reverse (-1x to -8x) | `J` |
| **Playback** | `playback.shuttle_stop` | Shuttle Stop | `K` |
| **Playback** | `playback.shuttle_fwd` | Shuttle Forward (1x to 8x) | `L` / `Shift+L` |
| **Playback** | `playback.step_fwd` / `step_back` | Step 1 Frame Forward / Back | `Right` / `Left` |
| **Playback** | `playback.step_fwd_10` / `step_back_10` | Step 10 Frames Forward / Back | `Shift+Right` / `Shift+Left` |
| **Playback** | `playback.first_frame` / `last_frame` | Go to First / Last Frame | `Home` / `End` |
| **Playback** | `app.toggle_cache` | Start In/Out Region Cache | `Shift+C` |
| **Channels** | `channel.rgb` | Full RGB Color | `C` |
| **Channels** | `channel.red` / `green` / `blue` | Isolate Red / Green / Blue | `R` / `G` / `B` |
| **Channels** | `channel.alpha` / `luma` | Isolate Alpha / Rec.709 Luminance | `A` / `Y` |
| **View** | `view.fit` / `fit_width` / `actual_size` | Fit Window / Fit Width / 100% 1:1 | `F` / `Alt+F` / `1` |
| **View** | `view.zoom_100` / `200` / `400` / `800` | Zoom Presets (100%–800%) | `Ctrl+1` / `Ctrl+2` / `Ctrl+4` / `Ctrl+8` |
| **View** | `view.flop_x` / `flip_y` | Flop Horizontal / Flip Vertical | `Shift+X` / `Shift+Y` |
| **View** | `view.filter_toggle` | Toggle Bilinear / Nearest Filter | `N` |
| **View** | `view.fullscreen` / `presentation` | Fullscreen / Presentation Mode | `F12` / `Ctrl+P` |
| **View** | `view.matte_cycle` / `matte_opacity_cycle` | Cycle Matte Ratio / Matte Opacity | `Ctrl+M` / `Shift+M` |
| **View** | `view.safe_guides` / `onion_skin` | Safe Area Guides / Onion Skin | `Shift+G` / `Shift+O` |
| **Color** | `color.invert_toggle` | **Toggle Invert Colors** | **`Shift+I`** |
| **Color** | `color.gain_up` / `gain_down` | Gain Increase / Decrease (±0.10) | `+` (`=`) / `-` (`_`) |
| **Color** | `color.exp_up` / `exp_down` | Exposure Increase / Decrease (±0.25 EV) | `Alt++` / `Alt+-` |
| **Color** | `color.gamma_up` / `gamma_down` | Gamma Increase / Decrease (±0.05) | `Shift++` / `Shift+-` |
| **Color** | `color.sat_up` / `sat_down` | Saturation Increase / Decrease (±0.05) | `Ctrl+Shift++` / `Ctrl+Shift+-` |
| **Color** | `color.exp_reset` / `gamma_reset` | Reset Exposure / Reset Gamma | `Ctrl+Alt+E` (`Ctrl+E`, `E`) / `Ctrl+Alt+G` |
| **Color** | `color.reset_all` | Reset All Color Adjustments | `Ctrl+Alt+R` / `Shift+Home` |
| **Color** | `color.adjustments` | Interactive Color Adjustments HUD | `/` |
| **Timeline** | `timeline.zoom_in` / `zoom_out` | Timeline Zoom In / Out | `Ctrl+=` / `Ctrl+-` |
| **Timeline** | `timeline.magnifier_toggle` | Toggle Magnified Timeline | `Shift+T` |
| **Timeline** | `timeline.toggle_timecode` | Toggle SMPTE Timecode | `Ctrl+T` |
| **Timeline** | `timeline.goto_frame` | Go to Frame Modal | `Ctrl+G` |
| **Marking** | `mark.in` / `mark.out` | Set In Mark / Set Out Mark | `[` / `]` |
| **Marking** | `mark.clear_in_out` / `clear_in` / `clear_out` | Clear In & Out / Clear In / Clear Out | `\` / `Alt+I` / `Alt+O` |
| **Marking** | `mark.bookmark_toggle` | Toggle Frame Bookmark | `M` |
| **Marking** | `mark.bookmark_next` / `prev` | Next / Previous Bookmark | `Alt+Right` / `Alt+Left` |
| **Marking** | `mark.bookmark_segment_next` / `prev` | Next / Previous Bookmark Segment | `PageDown` / `PageUp` |
| **Stacks** | `stack.cycle_fwd` / `cycle_bwd` | Cycle Stack Layer Forward / Back | `Z` / `Shift+Z` |
| **Playlist** | `playlist.toggle` | Toggle Sources & Session Manager | `` ` `` |
| **Versions** | `version.up` / `version.down` | Pipeline Version Up / Down | `Alt+Up` / `Alt+Down` |
| **HUDs** | `hud.histogram` / `color_inspector` | Histogram HUD / Color Inspector HUD | `H` / `F5` (`Alt+C`) |
| **HUDs** | `hud.wipe` / `wipe_flip_orientation` / `wipe_reset` | Wipe Toggle / Flip / Reset | `W` / `Shift+W` / `Alt+W` |
| **HUDs** | `hud.source_details` / `info_strip` | Source Media Details / Info Strip | `I` / `Ctrl+I` |
| **HUDs** | `hud.dailies_sync` / `toggle_file_browser` / `console` | Dailies Sync / File Browser / Console | `Ctrl+Shift+D` / `Ctrl+B` / **`Ctrl+Shift+L`** |
| **Annotations** | `annot.toggle_palette` / `toggle_pen` | Annotation Toolbox / Pen Tool | `X` / `D` |
| **Annotations** | `annot.undo` / `redo` / `clear_frame` | Undo / Redo / Clear Frame | `Ctrl+Z` / `Ctrl+Shift+Z` (`Ctrl+Y`) / `Delete` |
| **Annotations** | `annot.next_keyframe` / `prev_keyframe` | Next / Previous Annotated Frame | `.` / `,` |
| **Annotations** | `annot.manager` | Open Annotation Manager | `Ctrl+Shift+A` |
| **Sessions** | `session.new` / **`session.close`** | New Session / **Close & Clear Session** | `Ctrl+N` / **`Ctrl+Shift+N`** |
| **Sessions** | `session.open_media` / `open` | Open Media / Open Session (`.ovr`) | `Ctrl+O` / `Ctrl+Shift+O` |
| **Sessions** | `session.save` / `save_as` / `export` | Save / Save As / Export Media | `Ctrl+S` / `Ctrl+Shift+S` / `Ctrl+Shift+E` |
| **Cache & App** | `media.reload_frame` / `reload_sequence` | Reload Frame / Reload Sequence | `Ctrl+R` / `Ctrl+Shift+R` |
| **Cache & App** | `app.clear_cache` / `clear_all_cache` | Clear RAM Cache / **Clear All Sources Cache** | `Ctrl+Shift+C` / **`Ctrl+Delete`** |
| **App** | `app.preferences` / `escape` / `quit` | Preferences / Cancel Tool / Quit | `Ctrl+,` / `Escape` / `Ctrl+Q` |
