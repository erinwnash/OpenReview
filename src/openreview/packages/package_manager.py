"""
Package and Plugin Management Engine for OpenReview.
Handles discovery, manifest validation, dynamic module loading, zip installation,
and thread-safe hook dispatching.
"""
from __future__ import annotations

import os
import sys
import shutil
import zipfile
import logging
import importlib.util
from pathlib import Path
from typing import Optional, List, Dict, Any, Type
from PySide6.QtCore import QObject, Signal

from openreview.packages.manifest import PackageManifest
from openreview.packages.plugin_base import OpenReviewPlugin, PluginContext

logger = logging.getLogger(__name__)


class PackageManager(QObject):
    """
    Central manager for extension packages and plugins.
    Discovers packages, loads them dynamically, and dispatches application events.
    """

    packages_changed = Signal()
    hook_dispatched = Signal(str)

    _instance: Optional[PackageManager] = None

    def __init__(
        self,
        main_window: Optional[Any] = None,
        parent: Optional[QObject] = None,
        user_packages_dir: Optional[Path] = None,
        user_dir: Optional[Path] = None,
        builtin_packages_dir: Optional[Path] = None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self._manifests: Dict[str, PackageManifest] = {}
        self._loaded_plugins: Dict[str, OpenReviewPlugin] = {}
        self._disabled_packages: set[str] = set()
        self._enabled_packages: set[str] = set()

        u_dir = user_dir if user_dir is not None else user_packages_dir
        self._user_packages_dir = Path(u_dir) if u_dir else (Path.home() / ".openreview" / "packages")
        self._user_packages_dir.mkdir(parents=True, exist_ok=True)

        self._builtin_packages_dir = Path(builtin_packages_dir) if builtin_packages_dir else (Path(__file__).parent / "builtin")
        self._builtin_packages_dir.mkdir(parents=True, exist_ok=True)

        self._state_file = self._user_packages_dir.parent / "package_state.json"
        self._load_state()

    def _load_state(self) -> None:
        try:
            if hasattr(self, "_state_file") and self._state_file.is_file():
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._disabled_packages.update(data.get("disabled", []))
                    self._enabled_packages.update(data.get("enabled", []))
        except Exception as e:
            logger.warning("Failed to load package state: %s", e)

    def _save_state(self) -> None:
        try:
            if hasattr(self, "_state_file"):
                self._state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._state_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "disabled": sorted(list(self._disabled_packages)),
                        "enabled": sorted(list(self._enabled_packages)),
                    }, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save package state: %s", e)

    @classmethod
    def instance(cls, main_window: Optional[Any] = None) -> PackageManager:
        if cls._instance is None:
            cls._instance = PackageManager(main_window=main_window)
        elif main_window is not None:
            cls._instance.main_window = main_window
        return cls._instance

    @property
    def user_packages_dir(self) -> Path:
        return self._user_packages_dir

    def get_loaded_plugin(self, name_or_id: str) -> Optional[OpenReviewPlugin]:
        """Retrieve an active plugin instance by name or ID."""
        if name_or_id in self._loaded_plugins:
            return self._loaded_plugins[name_or_id]
        for manifest_name, plugin in self._loaded_plugins.items():
            manifest = self._manifests.get(manifest_name)
            if manifest and (manifest.id == name_or_id or manifest.name == name_or_id):
                return plugin
        return None

    def is_plugin_enabled(self, name_or_id: str) -> bool:
        """Check whether a package/plugin is enabled."""
        manifest = self._manifests.get(name_or_id)
        if not manifest:
            for m in self._manifests.values():
                if m.id == name_or_id or m.name == name_or_id:
                    manifest = m
                    break
        return manifest.enabled if manifest else False

    def set_plugin_enabled(self, name_or_id: str, enabled: bool) -> bool:
        """Alias for set_package_enabled supporting both id and name."""
        target_name = name_or_id
        if name_or_id not in self._manifests:
            for m in self._manifests.values():
                if m.id == name_or_id:
                    target_name = m.name
                    break
        return self.set_package_enabled(target_name, enabled)

    def install_package_from_zip(self, zip_path: Path) -> PackageManifest:
        """Alias for install_from_zip."""
        return self.install_from_zip(zip_path)


    def get_search_paths(self) -> List[Path]:
        """Return all active package search directories in priority order."""
        paths = [self._builtin_packages_dir, self._user_packages_dir]

        env_path = os.environ.get("OPENREVIEW_PACKAGE_PATH", "")
        if env_path:
            sep = ";" if sys.platform == "win32" else ":"
            for p in env_path.split(sep):
                p_path = Path(p.strip())
                if p_path.is_dir() and p_path not in paths:
                    paths.append(p_path)

        return paths

    def discover_packages(self) -> List[PackageManifest]:
        """Scan all package directories for valid package manifests."""
        self._manifests.clear()

        for search_dir in self.get_search_paths():
            if not search_dir.is_dir():
                continue

            is_builtin = (search_dir == self._builtin_packages_dir)
            for item in search_dir.iterdir():
                if not item.is_dir():
                    continue

                manifest_file = None
                for fname in ("manifest.json", "package.json"):
                    cand = item / fname
                    if cand.is_file():
                        manifest_file = cand
                        break

                if manifest_file:
                    try:
                        manifest = PackageManifest.from_file(manifest_file, is_builtin=is_builtin)
                        # Check override state
                        if manifest.name in self._disabled_packages or manifest.id in self._disabled_packages:
                            manifest.enabled = False
                        elif manifest.name in self._enabled_packages or manifest.id in self._enabled_packages:
                            manifest.enabled = True
                        self._manifests[manifest.name] = manifest
                    except Exception as e:
                        logger.warning("Failed to parse manifest at %s: %s", manifest_file, e)

        return list(self._manifests.values())

    def load_all_plugins(self) -> None:
        """Discover and instantiate all enabled plugins."""
        self.discover_packages()

        for name, manifest in list(self._manifests.items()):
            if manifest.enabled and name not in self._loaded_plugins:
                self._load_plugin(manifest)

        self.packages_changed.emit()

    def unload_all_plugins(self) -> None:
        """Call shutdown on all active plugins and clear loaded state."""
        visited = set()
        for name, plugin in list(self._loaded_plugins.items()):
            if id(plugin) in visited:
                continue
            visited.add(id(plugin))
            try:
                if hasattr(plugin, "shutdown") and callable(plugin.shutdown):
                    plugin.shutdown()
                if hasattr(plugin, "on_shutdown") and callable(plugin.on_shutdown):
                    plugin.on_shutdown()
            except Exception as e:
                logger.error("Error shutting down plugin '%s': %s", name, e)
        self._loaded_plugins.clear()
        self.packages_changed.emit()

    def reload_all(self) -> None:
        """Reload all active plugins cleanly."""
        self.unload_all_plugins()
        self.load_all_plugins()

    def set_package_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable an extension package."""
        if not self._manifests:
            self.discover_packages()
        manifest = self._manifests.get(name)
        if not manifest:
            for m in self._manifests.values():
                if m.id == name or m.name == name:
                    manifest = m
                    break
        if not manifest:
            return False

        manifest.enabled = enabled
        if enabled:
            self._disabled_packages.discard(name)
            self._disabled_packages.discard(manifest.id)
            self._enabled_packages.add(name)
            self._enabled_packages.add(manifest.id)
            if name not in self._loaded_plugins:
                self._load_plugin(manifest)
        else:
            self._enabled_packages.discard(name)
            self._enabled_packages.discard(manifest.id)
            self._disabled_packages.add(name)
            self._disabled_packages.add(manifest.id)
            if name in self._loaded_plugins:
                plugin = self._loaded_plugins.pop(name)
                # also pop alias if present
                if manifest.id in self._loaded_plugins:
                    self._loaded_plugins.pop(manifest.id, None)
                try:
                    if hasattr(plugin, "shutdown") and callable(plugin.shutdown):
                        plugin.shutdown()
                    if hasattr(plugin, "on_shutdown") and callable(plugin.on_shutdown):
                        plugin.on_shutdown()
                except Exception as e:
                    logger.error("Error shutting down plugin '%s': %s", name, e)

        self._save_state()
        self.packages_changed.emit()
        return True

    def install_from_zip(self, zip_path: Path) -> PackageManifest:
        """Extract a .zip package into user packages directory and validate manifest."""
        if not zip_path.is_file():
            raise FileNotFoundError(f"Package zip file not found: {zip_path}")

        temp_extract = self._user_packages_dir / f"_tmp_{zip_path.stem}"
        if temp_extract.exists():
            shutil.rmtree(temp_extract)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_extract)

        # Detect top-level manifest or nested single folder
        manifest_file = None
        target_dir = temp_extract
        for cand_dir in [temp_extract] + [p for p in temp_extract.iterdir() if p.is_dir()]:
            for fname in ("manifest.json", "package.json"):
                f = cand_dir / fname
                if f.is_file():
                    manifest_file = f
                    target_dir = cand_dir
                    break
            if manifest_file:
                break

        if not manifest_file:
            shutil.rmtree(temp_extract, ignore_errors=True)
            raise ValueError("Invalid package: no manifest.json or package.json found in archive.")

        manifest = PackageManifest.from_file(manifest_file, is_builtin=False)
        dest_dir = self._user_packages_dir / manifest.name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        shutil.move(str(target_dir), str(dest_dir))
        shutil.rmtree(temp_extract, ignore_errors=True)

        # Reload newly installed package
        final_manifest = PackageManifest.from_file(dest_dir / manifest_file.name, is_builtin=False)
        self._manifests[final_manifest.name] = final_manifest
        if final_manifest.enabled:
            self._load_plugin(final_manifest)

        self.packages_changed.emit()
        return final_manifest

    def install_from_dir(self, dir_path: Path) -> PackageManifest:
        """Copy a package directory into user packages directory."""
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {dir_path}")

        manifest_file = None
        for fname in ("manifest.json", "package.json"):
            f = dir_path / fname
            if f.is_file():
                manifest_file = f
                break

        if not manifest_file:
            raise ValueError(f"No manifest.json or package.json found in {dir_path}")

        manifest = PackageManifest.from_file(manifest_file, is_builtin=False)
        dest_dir = self._user_packages_dir / manifest.name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        shutil.copytree(dir_path, dest_dir)
        final_manifest = PackageManifest.from_file(dest_dir / manifest_file.name, is_builtin=False)
        self._manifests[final_manifest.name] = final_manifest
        if final_manifest.enabled:
            self._load_plugin(final_manifest)

        self.packages_changed.emit()
        return final_manifest

    def uninstall_package(self, name: str) -> bool:
        """Remove a user package from disk."""
        manifest = self._manifests.get(name)
        if not manifest:
            return False

        if manifest.is_builtin:
            raise PermissionError(f"Cannot uninstall built-in package '{name}'")

        if name in self._loaded_plugins:
            plugin = self._loaded_plugins.pop(name)
            try:
                plugin.shutdown()
            except Exception as e:
                logger.error("Error shutting down plugin '%s': %s", name, e)

        pkg_dir = Path(manifest.package_path)
        if pkg_dir.is_dir() and pkg_dir.is_relative_to(self._user_packages_dir):
            shutil.rmtree(pkg_dir)

        del self._manifests[name]
        self._disabled_packages.discard(name)
        if manifest.id:
            self._disabled_packages.discard(manifest.id)
        self._enabled_packages.discard(name)
        if manifest.id:
            self._enabled_packages.discard(manifest.id)
        self._save_state()
        self.packages_changed.emit()
        return True

    def dispatch_hook(self, hook_name: str, *args, **kwargs) -> None:
        """Safely invoke an event callback on all active plugins."""
        visited = set()
        for name, plugin in list(self._loaded_plugins.items()):
            if id(plugin) in visited:
                continue
            visited.add(id(plugin))
            method = getattr(plugin, hook_name, None)
            if callable(method):
                try:
                    method(*args, **kwargs)
                except Exception as e:
                    logger.exception("Error in plugin '%s' handling hook '%s': %s", name, hook_name, e)

        self.hook_dispatched.emit(hook_name)

    # --------------------------------------------------------------------------
    # Internal Plugin Loader
    # --------------------------------------------------------------------------
    def _load_plugin(self, manifest: PackageManifest) -> Optional[OpenReviewPlugin]:
        entry_str = manifest.entrypoint or "plugin.py"
        cls_name = None
        if ":" in entry_str:
            file_part, cls_name = entry_str.split(":", 1)
        else:
            file_part = entry_str

        pkg_dir = Path(manifest.package_path)
        entry_path = pkg_dir / file_part
        if not entry_path.is_file() and (pkg_dir / f"{file_part}.py").is_file():
            entry_path = pkg_dir / f"{file_part}.py"

        if not entry_path.is_file():
            logger.warning("Plugin entrypoint not found: %s", entry_path)
            return None

        module_name = f"openreview_plugin_{manifest.name.replace('-', '_')}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(entry_path))
            if not spec or not spec.loader:
                return None

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            # Find OpenReviewPlugin subclass
            plugin_cls: Optional[Type[OpenReviewPlugin]] = None
            if cls_name and hasattr(mod, cls_name):
                c = getattr(mod, cls_name)
                if isinstance(c, type) and issubclass(c, OpenReviewPlugin):
                    plugin_cls = c

            if plugin_cls is None:
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if isinstance(obj, type) and issubclass(obj, OpenReviewPlugin) and obj is not OpenReviewPlugin:
                        plugin_cls = obj
                        break

            if not plugin_cls:
                logger.warning("No OpenReviewPlugin subclass found in %s", entry_path)
                return None

            ctx = PluginContext(manifest, main_window=self.main_window)
            try:
                instance = plugin_cls(ctx)
            except TypeError:
                instance = plugin_cls()
                instance.context = ctx

            if hasattr(instance, "initialize") and callable(instance.initialize):
                try:
                    instance.initialize()
                except Exception as e:
                    logger.warning("Error calling initialize on '%s': %s", manifest.name, e)

            if hasattr(instance, "on_init") and callable(instance.on_init):
                try:
                    instance.on_init(ctx)
                except Exception as e:
                    logger.warning("Error calling on_init on '%s': %s", manifest.name, e)

            self._loaded_plugins[manifest.name] = instance
            if manifest.id and manifest.id != manifest.name:
                self._loaded_plugins[manifest.id] = instance

            logger.info("Successfully loaded plugin '%s' v%s", manifest.name, manifest.version)
            return instance
        except Exception as e:
            logger.exception("Failed to load plugin '%s': %s", manifest.name, e)
            return None
