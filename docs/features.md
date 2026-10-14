# OpenReview Complete Features & Keyboard Shortcuts Guide

**Author:** Maruthu Chakravarthi  
**Interactive HTML Version:** [docs/html/features.html](file:///e:/works/Pipeline/code/OpenReview/docs/html/features.html)

---

## 1. Complete Feature Set

### 1.1 Playback, JKL Shuttling & Timecode (`core/clock.py`, `widgets/timeline.py`)
- **Real-Time vs. Play Every Frame:** Switch between strict wall-clock sync and sequential frame-accurate playback.
- **JKL Multi-Speed Shuttling:** `J` reverses (`-1x`, `-2x`, `-4x`, `-8x`), `K` stops (`1.0x`), and `L` shuttles forward (`1x`, `2x`, `4x`, `8x`).
- **Loop Modes:** Forward Loop, Ping-Pong (Bidirectional Bounce), and Play Once.
- **SMPTE Timecode & Go-To Frame:** Toggle Frame Numbers vs. `HH:MM:SS:FF` SMPTE Timecode (`Ctrl+T`), open the frameless Go-To Frame modal (`Ctrl+G`), and toggle the Magnified Timeline Mini-Ruler (`Shift+T`).
- **Interactive Canvas Scrubbing:** Left-mouse drag horizontally on the viewport canvas to scrub frames with live 60ms audio bursts.

### 1.2 Asynchronous RAM Caching & GPU Acceleration (`core/cache.py`, `widgets/viewport.py`)
- **Four Cache Strategies:** `Off`, `Play-Ahead` (80% ahead / 20% behind), `In/Out Region` (`Shift+C`), and `Cache All` (1 GB – 64 GB RAM budget).
- **Granular Reload & Eviction:** Reload single frame (`Ctrl+R`), reload active sequence (`Ctrl+Shift+R`), clear active cache (`Ctrl+Shift+C`), or clear all source caches (`Ctrl+Delete`).
- **Three Selectable GPU Playback Engines:** `opengl_core` (OpenGL 3.3+ Core Profile), `async_pbo` (Double-Buffered Pixel Buffer Object DMA streaming), and `software_safe`.

### 1.3 Color Science, LUT/CDL & OpenColorIO v2 (`color/shader_builder.py`, `color/ocio_manager.py`, `color/lut_manager.py`)
- **Scene-Linear Exposure & Gain:** Coupled F-stop EV (`Alt++` / `Alt+-`) and linear Gain (`+` / `-`), with one-click reset (`Ctrl+Alt+E` / `E`).
- **Gamma, Contrast, Saturation & Hue:** Interactive Color Adjustments HUD (`/`) with master and per-channel R/G/B grading, 18% grey pivot contrast, hue rotation (`-180°..+180°`), and display brightness.
- **Invert Colors (`Shift+I`) & Out-of-Range Zebra:** Instant display-space RGB inversion (`Shift+I`) and Magenta (`>1.0`) / Cyan (`<0.0`) clipping indicators.
- **Hardware 3D LUT & ASC CDL:** Load `.cube` / `.3dl` 3D LUTs and `.cdl` / `.cc` / `.ccc` ASC CDL grades with independent bypass toggles.
- **Channel Isolation:** Single-key soloing for `RGB` (`C`), `Red` (`R`), `Green` (`G`), `Blue` (`B`), `Alpha` (`A`), and Rec.709 `Luminance` (`Y`).

### 1.4 A/B Split Wipes, Difference Modes, Stacks & Contact Sheet Layouts
- **Interactive Split Wipe (`W`):** Translate wipe position and rotate wipe angle (`0°–360°`) directly on canvas; flip orientation (`Shift+W`) or reset (`Alt+W`).
- **Six Composite Modes:** `Replace`, `Sequence`, `Over (Alpha Composite)`, `Add`, `Difference`, and `Difference (Inverted)` with up to `20x` Difference Boost.
- **Multi-Layer Stacks (`Z` / `Shift+Z`) & Tiled Layouts:** Cycle stack layers in place (`Z` / `Shift+Z`) or view multi-clip contact sheets (`Auto Grid`, `Side-by-Side`, `Over/Under`, `2x2`, `3x3`).

### 1.5 32-Bit Float Pixel Probe, Area Samplers & Vector Annotations
- **Pixel Color Inspector (`F5` / `Alt+C`) & Live Histogram (`H`):** 32-bit float RGBA, 8-bit RGB, HSV, Luminance, pinned point samplers, rectangular area Min/Max/Mean analyzers, and `NaN` / `Inf` / `Neg` pixel counters.
- **Vector Annotations (`X` / `D`) & Annotation Manager (`Ctrl+Shift+A`):** Pen, Line, Arrow, Rectangle, Circle, and In-Canvas Text Callouts with per-frame Undo (`Ctrl+Z`), Redo (`Ctrl+Shift+Z`), keyframe stepping (`,` / `.`), per-frame review notes, and JSON/CSV/Markdown/Burn-In media export (`Ctrl+Shift+E`).

---

## 2. Authoritative Keyboard Shortcuts Registry (All 78+ Actions)

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
| **Channels** | `channel.alpha` / `luma` | Isolate Alpha / Luminance | `A` / `Y` |
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
| **HUDs** | `hud.dailies_sync` / `toggle_file_browser` / `console` | Dailies Sync / File Browser / Console | `Ctrl+Shift+D` / `Ctrl+B` / `Ctrl+Shift+L` |
| **Annotations** | `annot.toggle_palette` / `toggle_pen` | Annotation Toolbox / Pen Tool | `X` / `D` |
| **Annotations** | `annot.undo` / `redo` / `clear_frame` | Undo / Redo / Clear Frame | `Ctrl+Z` / `Ctrl+Shift+Z` (`Ctrl+Y`) / `Delete` |
| **Annotations** | `annot.next_keyframe` / `prev_keyframe` | Next / Previous Annotated Frame | `.` / `,` |
| **Annotations** | `annot.manager` | Open Annotation Manager | `Ctrl+Shift+A` |
| **Sessions** | `session.new` / **`session.close`** | New Session / **Close & Clear Session** | `Ctrl+N` / **`Ctrl+Shift+N`** |
| **Sessions** | `session.open_media` / `open` | Open Media / Open Session (`.ovr`) | `Ctrl+O` / `Ctrl+Shift+O` |
| **Sessions** | `session.save` / `save_as` / `export` | Save / Save As / Export Media | `Ctrl+S` / `Ctrl+Shift+S` / `Ctrl+Shift+E` |
| **Cache & App** | `media.reload_frame` / `reload_sequence` | Reload Frame / Reload Sequence | `Ctrl+R` / `Ctrl+Shift+R` |
| **Cache & App** | `app.clear_cache` / `clear_all_cache` | Clear RAM Cache / Clear All Cache | `Ctrl+Shift+C` / `Ctrl+Delete` |
| **App** | `app.preferences` / `escape` / `quit` | Preferences / Cancel Tool / Quit | `Ctrl+,` / `Escape` / `Ctrl+Q` |
