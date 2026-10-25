# Changelog

All notable changes to **OpenReview** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-10-25

### Added
- **Draggable Scroll Area**: Added `DraggableScrollArea` widget allowing smooth middle-mouse and touch-drag canvas panning across multi-source panels and inspectors.
- **Floating HUD Opacity & Dynamic Resizing**: Interactive opacity control slider and 8-directional edge/corner resize handles for all 12 floating workstation HUDs.
- **System Utilities Module**: Added `system_utils.py` with cross-platform physical RAM detection, GPU driver inspection, and OS file manager reveal helpers.
- **Deep Source Media Metadata**: Full extraction of EXR channel topologies, video container streams, audio sampling rates, pixel aspect ratios, and color space tags.
- **Viewer Drag Overlay**: Visual drag-and-drop overlay indicator on the OpenGL viewport providing instant feedback during clip ingestion.
- **PDF Export Preferences & Layout**: Configurable page orientation, margin presets, DPI scaling, and multi-frame contact sheet report layouts.
- **Dynamic Stack Source Details**: Live metadata and resolution readouts dynamically linked to the active layer within composite stacks.

### Fixed
- **Cache Eviction**: Resolved ring buffer cache lockups during rapid JKL bidirectional scrubbing over high-bitrate video clips.
- **Timeline Transport Bounds**: Corrected frame clamp math when moving between sequences with disparate frame numbering (e.g. 1001-1150 vs 1-240).
- **Comp QC Softclip Knee**: Fixed highlight compression curve math in the `xtra-qc-Utils` diagnostic shader.
- **Annotation Frame-Matching**: Fixed stroke undo/redo history retention when scrubbing across non-annotated intermediate frames.
- **Sequence Parser**: Improved single-frame VFX plate detection and non-sequential frame range parsing.

---

## [1.1.0] - 2026-10-18

### Added
- **Built-in Comp QC Package (`xtra-qc-Utils`)**: Complete compositing quality control toolset with non-destructive diagnostic color adjustments, softclip knee highlight compression, and specialized inspection filters (Grain Check, High-Pass, Black Levels, NaN/Inf hunting, HSL soloing).
- **About & License Dialog**: Full interactive credits dialog with system specifications and searchable third-party open-source license browser (`licenses.py`).
- **Modernized Dock Title Bars**: Custom dark-themed dock headers with dedicated minimize, undock/float, and close controls.
- **Dynamic Two-Tier Caching**: High-speed RAM ring buffer coupled with persistent multi-gigabyte `DiskCache` prefetching.
- **Studio Feature Manual**: Exhaustive 12-domain technical documentation guide (`docs/features.md`).

---

## [1.0.1] - 2026-10-15

### Added
- **Multi-Part OpenEXR Contact Sheet**: Grid inspection and soloing of all sub-parts, multi-layer AOVs, and display windows.
- **Deep EXR Metadata Inspector**: Detailed header inspection, channel mappings, compression algorithms, and chromaticities.
- **Async Source Loader Engine**: Multi-threaded non-blocking loader with cancellation tokens for ultra-high-bitrate clips.
- **Persistent In/Out Auto-Snap & Range Memory**: Per-view In/Out mark retention and auto-fitting across session switches.
- **High-DPI Vector Icons & Branding**: Complete multi-resolution Windows ICO (16px to 256px), horizontal header logo, and scalable SVG suite.

---

## [1.0.0] - 2026-10-14

### Added
- **Initial Production Release**: Studio-grade VFX sequence playback, HDR color inspection, compositing comparison, and dailies review desktop workstation.
- **Hardware-Accelerated Viewport**: OpenGL 3.3+ Core Profile with double-buffered asynchronous PBO DMA texture streaming and native `RGBA16F`/`RGBA32F` float textures.
- **9-Stage GLSL Color Pipeline**: Seamless OpenColorIO v2 integration (ACES 1.3 / 2.0, Cineon, LogC, Rec.709, sRGB), Exposure, Gain, Gamma, ASC CDL, 3D LUTs, Invert, and Out-of-Range zebra warnings.
- **A/B Split Wipes & Difference QC**: Multi-angle split wipe controller with difference boost and plate-to-comp alignment tools.
- **Resolution-Independent Vector Markups**: Freehand pen, shapes, callouts, and frame annotations with export to CSV/JSON/burn-in video.
- **Sub-Frame Audio Engine & Dailies Sync**: Scrubbing audio bursts, drift resync, and multi-user TCP remote playback sync.
- **Distribution Packages**: 64-bit Windows Installer (.msi), Windows Portable (.zip), Linux Debian (.deb), and Linux RedHat (.rpm).
