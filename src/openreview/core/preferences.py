"""
Persistent Preferences Management for OpenReview.
Stores user preferences in ~/.openreview/preferences.json with QSettings fallback.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject, Signal, QSettings


from dataclasses import dataclass, asdict, field

@dataclass
class UserPreferences:
    """Dataclass holding all configurable user settings."""
    default_fps: float = 24.0
    play_on_startup: bool = False
    start_fullscreen: bool = False
    canvas_scrub_enabled: bool = True
    auto_retime_mismatched_fps: bool = True
    play_all_frames: bool = True

    # Caching
    default_cache_mode: str = "off"  # "off", "play_ahead", "region", "all"
    auto_ram_budget: bool = True
    lookahead_cache_gb: float = 4.0
    region_cache_gb: float = 4.0
    lookahead_behind_pct: float = 20.0
    enable_disk_cache: bool = True
    disk_cache_dir: str = ""  # empty = default OS temp directory
    max_disk_cache_gb: float = 20.0

    # Playback Performance & Low-spec / GPU Workstation Optimization
    playback_texture_mode: str = "auto"  # "auto", "rgba8" (fast/laptop), "rgba16f", "rgba32f"
    prefetch_buffer_size: int = 64
    prefetch_worker_threads: int = 6
    fast_playback_laptop_mode: bool = False

    # GPU Performance & Playback Engines
    playback_engine: str = "opengl_core"  # "opengl_core", "async_pbo", "software_safe"
    selected_gpu_device: str = "auto"     # "auto" or specific GPU name
    hardware_video_decoding: bool = True
    enable_opencl_acceleration: bool = True
    enable_pbo_streaming: bool = True
    vsync_enabled: bool = False
    gpu_vram_limit_mb: float = 2048.0

    # Keyboard Shortcut Customizations: action_id -> key_sequence_str
    shortcuts: dict[str, str] = field(default_factory=dict)

    # Workflow & UI Enhancements
    recent_files: list[str] = field(default_factory=list)
    file_browser_bookmarks: list[dict[str, str]] = field(default_factory=list)
    timecode_mode: bool = False
    continuous_playback: bool = False
    safe_guides_enabled: bool = False
    safe_guides_matte_constrained: bool = True

    # Studio OpenColorIO Configuration
    ocio_config_path: str = ""
    ocio_display: str = ""
    ocio_view: str = ""
    ocio_input_space: str = ""
    ocio_lut_paths: list[str] = field(default_factory=list)

    # Multi-User Remote Dailies Sync
    sync_room_name: str = "VFX Review Main"
    sync_username: str = "Artist"
    sync_playlist_enabled: bool = True

    # Console & Diagnostics
    console_auto_open_on_error: bool = True


class PreferencesManager(QObject):
    """
    Singleton-style Preferences Manager emitting signals upon modification.
    """
    preferences_changed = Signal(object)  # Emits UserPreferences

    _instance: Optional[PreferencesManager] = None

    def __init__(self, config_dir: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._use_qsettings = (config_dir is None)
        self.config_dir = config_dir or (Path.home() / ".openreview")
        self.config_file = self.config_dir / "preferences.json"
        self._prefs = UserPreferences()
        self.load()

    @classmethod
    def instance(cls) -> PreferencesManager:
        if cls._instance is None:
            cls._instance = PreferencesManager()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    @property
    def prefs(self) -> UserPreferences:
        return self._prefs

    @property
    def preferences(self) -> UserPreferences:
        return self._prefs

    def save_preferences(self) -> None:
        self.save()

    def load(self) -> UserPreferences:
        """Load preferences from JSON file, falling back to QSettings if available."""
        if self.config_file.is_file():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._prefs = UserPreferences(
                    default_fps=float(data.get("default_fps", 24.0)),
                    play_on_startup=bool(data.get("play_on_startup", False)),
                    start_fullscreen=bool(data.get("start_fullscreen", False)),
                    canvas_scrub_enabled=bool(data.get("canvas_scrub_enabled", True)),
                    auto_retime_mismatched_fps=bool(data.get("auto_retime_mismatched_fps", True)),
                    play_all_frames=bool(data.get("play_all_frames", True)),
                    default_cache_mode=str(data.get("default_cache_mode", "off")),
                    auto_ram_budget=bool(data.get("auto_ram_budget", True)),
                    lookahead_cache_gb=float(data.get("lookahead_cache_gb", 4.0)),
                    region_cache_gb=float(data.get("region_cache_gb", 4.0)),
                    lookahead_behind_pct=float(data.get("lookahead_behind_pct", 20.0)),
                    playback_texture_mode=str(data.get("playback_texture_mode", "auto")),
                    prefetch_buffer_size=int(data.get("prefetch_buffer_size", 48)),
                    prefetch_worker_threads=int(data.get("prefetch_worker_threads", max(2, min(os.cpu_count() or 4, 8)))),
                    fast_playback_laptop_mode=bool(data.get("fast_playback_laptop_mode", False)),
                    playback_engine=str(data.get("playback_engine", "opengl_core")),
                    selected_gpu_device=str(data.get("selected_gpu_device", "auto")),
                    hardware_video_decoding=bool(data.get("hardware_video_decoding", True)),
                    enable_opencl_acceleration=bool(data.get("enable_opencl_acceleration", True)),
                    enable_pbo_streaming=bool(data.get("enable_pbo_streaming", True)),
                    vsync_enabled=bool(data.get("vsync_enabled", False)),
                    gpu_vram_limit_mb=float(data.get("gpu_vram_limit_mb", 2048.0)),
                    shortcuts=dict(data.get("shortcuts", {})),
                    recent_files=list(data.get("recent_files", [])),
                    file_browser_bookmarks=list(data.get("file_browser_bookmarks", [])),
                    timecode_mode=bool(data.get("timecode_mode", False)),
                    continuous_playback=bool(data.get("continuous_playback", False)),
                    safe_guides_enabled=bool(data.get("safe_guides_enabled", False)),
                    safe_guides_matte_constrained=bool(data.get("safe_guides_matte_constrained", True)),
                    ocio_config_path=str(data.get("ocio_config_path", "")),
                    ocio_display=str(data.get("ocio_display", "")),
                    ocio_view=str(data.get("ocio_view", "")),
                    ocio_input_space=str(data.get("ocio_input_space", "")),
                    ocio_lut_paths=list(data.get("ocio_lut_paths", [])),
                    sync_room_name=str(data.get("sync_room_name", "VFX Review Main")),
                    sync_username=str(data.get("sync_username", "Artist")),
                    sync_playlist_enabled=bool(data.get("sync_playlist_enabled", True)),
                    console_auto_open_on_error=bool(data.get("console_auto_open_on_error", True)),
                )
                return self._prefs
            except Exception as e:
                print(f"[PreferencesManager] Failed to read JSON config: {e}. Falling back.")

        # Fallback to QSettings only for default user config
        if self._use_qsettings:
            try:
                settings = QSettings("OpenReview", "OpenReview")
                self._prefs.default_fps = float(settings.value("default_fps", 24.0))
                self._prefs.play_on_startup = settings.value("play_on_startup", False, type=bool)
                self._prefs.start_fullscreen = settings.value("start_fullscreen", False, type=bool)
                self._prefs.canvas_scrub_enabled = settings.value("canvas_scrub_enabled", True, type=bool)
                self._prefs.auto_retime_mismatched_fps = settings.value("auto_retime_mismatched_fps", True, type=bool)
                self._prefs.default_cache_mode = str(settings.value("default_cache_mode", "off"))
                self._prefs.auto_ram_budget = settings.value("auto_ram_budget", True, type=bool)
                self._prefs.lookahead_cache_gb = float(settings.value("lookahead_cache_gb", 4.0))
                self._prefs.region_cache_gb = float(settings.value("region_cache_gb", 4.0))
                self._prefs.lookahead_behind_pct = float(settings.value("lookahead_behind_pct", 20.0))
                self._prefs.playback_texture_mode = str(settings.value("playback_texture_mode", "auto"))
                self._prefs.prefetch_buffer_size = int(settings.value("prefetch_buffer_size", 48))
                self._prefs.fast_playback_laptop_mode = settings.value("fast_playback_laptop_mode", False, type=bool)
                self._prefs.console_auto_open_on_error = settings.value("console_auto_open_on_error", True, type=bool)
            except Exception:
                pass
        return self._prefs

    def save(self, prefs: Optional[UserPreferences] = None) -> None:
        """Persist preferences to ~/.openreview/preferences.json and QSettings."""
        if prefs is not None:
            self._prefs = prefs

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self._prefs), f, indent=4)
        except Exception as e:
            print(f"[PreferencesManager] Could not write JSON: {e}")

        # Sync QSettings only for default user config
        if self._use_qsettings:
            try:
                settings = QSettings("OpenReview", "OpenReview")
                for k, v in asdict(self._prefs).items():
                    settings.setValue(k, v)
                settings.sync()
            except Exception as e:
                print(f"[PreferencesManager] Could not write QSettings: {e}")

        self.preferences_changed.emit(self._prefs)

    def add_recent_file(self, path: str, max_items: int = 12) -> None:
        """Add a path to recent files list (deduplicated, MRU order)."""
        if not path:
            return
        norm_path = os.path.normpath(path)
        current = [os.path.normpath(p) for p in self._prefs.recent_files]
        if norm_path in current:
            current.remove(norm_path)
        current.insert(0, norm_path)
        self._prefs.recent_files = current[:max_items]
        self.save()

    def clear_recent_files(self) -> None:
        """Clear all recent file paths."""
        self._prefs.recent_files.clear()
        self.save()

    def get_recent_files(self) -> list[str]:
        """Return list of recent files that exist on disk."""
        return [p for p in self._prefs.recent_files if os.path.exists(p)]

    def is_low_spec_gpu(self) -> bool:
        """Check if active GPU has constrained memory or bandwidth (<=2GB VRAM or entry-level GPU)."""
        vram = getattr(self._prefs, "gpu_vram_limit_mb", 2048.0)
        gpu = str(getattr(self._prefs, "selected_gpu_device", "")).lower()
        if "gt 710" in gpu or "gt 730" in gpu or "intel" in gpu or "uhd" in gpu or vram <= 2048.0:
            return True
        return False

    def get_effective_texture_mode(self) -> str:
        """Resolve texture mode: 'rgba16f' provides zero-copy GPU upload for HDR/float media."""
        mode = getattr(self._prefs, "playback_texture_mode", "auto")
        if mode in ("rgba8", "rgba16f", "rgba32f"):
            return mode
        return "rgba16f"

