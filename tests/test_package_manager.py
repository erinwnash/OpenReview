import io
import json
import zipfile
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from openreview.packages.manifest import PackageManifest
from openreview.packages.plugin_base import OpenReviewPlugin, PluginContext
from openreview.packages.package_manager import PackageManager


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_package_manifest_parsing():
    manifest_data = {
        "id": "com.studio.shot_sync",
        "name": "Shot Sync",
        "version": "1.2.0",
        "author": "Pipeline Team",
        "description": "Syncs shots with ShotGrid",
        "entry_point": "plugin:ShotSyncPlugin",
        "category": "Pipeline",
        "tags": ["shotgrid", "sync"],
        "min_openreview_version": "0.1.0",
        "hooks": ["on_media_loaded"],
    }
    pkg = PackageManifest.from_dict(manifest_data)
    assert pkg.id == "com.studio.shot_sync"
    assert pkg.name == "Shot Sync"
    assert pkg.version == "1.2.0"
    assert pkg.author == "Pipeline Team"
    assert pkg.category == "Pipeline"
    assert "shotgrid" in pkg.tags
    assert pkg.hooks == ["on_media_loaded"]

    json_str = pkg.to_json()
    reconstructed = PackageManifest.from_json(json_str)
    assert reconstructed.id == pkg.id
    assert reconstructed.version == pkg.version


def test_package_discovery_and_lifecycle(tmp_path, qapp):
    user_packages_dir = tmp_path / "user_packages"
    user_packages_dir.mkdir()

    # Create dummy plugin folder
    plugin_dir = user_packages_dir / "test_plugin"
    plugin_dir.mkdir()

    manifest_json = plugin_dir / "manifest.json"
    manifest_json.write_text(json.dumps({
        "id": "org.test.dummy",
        "name": "Dummy Plugin",
        "version": "1.0.0",
        "entry_point": "dummy_mod:DummyPlugin",
        "hooks": ["on_frame_changed", "on_media_loaded"],
    }))

    dummy_py = plugin_dir / "dummy_mod.py"
    dummy_py.write_text("""
from openreview.packages.plugin_base import OpenReviewPlugin

class DummyPlugin(OpenReviewPlugin):
    def __init__(self):
        super().__init__()
        self.frame_history = []
        self.media_history = []
        self.initialized = False
        self.shutdown_called = False

    def on_init(self, context):
        self.context = context
        self.initialized = True

    def on_frame_changed(self, frame):
        self.frame_history.append(frame)

    def on_media_loaded(self, media_path):
        self.media_history.append(media_path)

    def on_shutdown(self):
        self.shutdown_called = True
""")

    mgr = PackageManager(user_dir=user_packages_dir)
    discovered = mgr.discover_packages()
    assert any(p.name == "Dummy Plugin" or p.id == "org.test.dummy" for p in discovered)

    # Load all enabled plugins
    mgr.load_all_plugins()
    plugin_inst = mgr.get_loaded_plugin("Dummy Plugin") or mgr.get_loaded_plugin("org.test.dummy")
    assert plugin_inst is not None
    assert plugin_inst.initialized is True

    # Dispatch hooks
    mgr.dispatch_hook("on_frame_changed", 101)
    mgr.dispatch_hook("on_frame_changed", 102)
    mgr.dispatch_hook("on_media_loaded", "/shots/sq01/sh010.exr")

    assert plugin_inst.frame_history == [101, 102]
    assert plugin_inst.media_history == ["/shots/sq01/sh010.exr"]

    # Test disable
    target_id = "Dummy Plugin" if "Dummy Plugin" in mgr._manifests else "org.test.dummy"
    mgr.set_plugin_enabled(target_id, False)
    assert not mgr.is_plugin_enabled(target_id)
    assert mgr.get_loaded_plugin(target_id) is None

    # Test re-enable
    mgr.set_plugin_enabled(target_id, True)
    assert mgr.is_plugin_enabled(target_id)
    reloaded_plugin = mgr.get_loaded_plugin(target_id)
    assert reloaded_plugin is not None

    # Unload
    mgr.unload_all_plugins()
    assert reloaded_plugin.shutdown_called is True


def test_package_zip_install_and_uninstall(tmp_path, qapp):
    user_packages_dir = tmp_path / "user_packages"
    user_packages_dir.mkdir()

    # Create a zip package in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_content = json.dumps({
            "id": "com.zip.test",
            "name": "Zip Plugin",
            "version": "2.0.0",
            "entrypoint": "plugin.py"
        })
        plugin_code = """
from openreview.packages.plugin_base import OpenReviewPlugin
class ZipPlugin(OpenReviewPlugin):
    pass
"""
        zf.writestr("manifest.json", manifest_content)
        zf.writestr("plugin.py", plugin_code)

    zip_path = tmp_path / "my_plugin.zip"
    zip_path.write_bytes(zip_buffer.getvalue())

    mgr = PackageManager(user_dir=user_packages_dir)
    installed_pkg = mgr.install_package_from_zip(zip_path)
    assert installed_pkg.name == "Zip Plugin"
    assert installed_pkg.version == "2.0.0"

    # Verify directory exists
    expected_dir = user_packages_dir / installed_pkg.name
    assert expected_dir.exists()
    assert (expected_dir / "manifest.json").exists()

    # Test uninstall
    success = mgr.uninstall_package(installed_pkg.name)
    assert success is True
    assert not expected_dir.exists()


def test_package_manager_dialog_immediate_toggle(tmp_path, qapp):
    """Verify clicking Enable/Disable in PackageManagerDialog immediately updates button text, style, and table status without jumping selection."""
    from openreview.ui.package_manager_dialog import PackageManagerDialog

    user_packages_dir = tmp_path / "user_packages"
    user_packages_dir.mkdir()

    # Create dummy plugin folder
    plugin_dir = user_packages_dir / "my_tool"
    plugin_dir.mkdir()

    manifest_json = plugin_dir / "manifest.json"
    manifest_json.write_text(json.dumps({
        "id": "my_tool",
        "name": "My Tool",
        "version": "1.0.0",
        "enabled": False,
        "entrypoint": "plugin.py",
    }))

    (plugin_dir / "plugin.py").write_text("""
from openreview.packages.plugin_base import OpenReviewPlugin
class MyToolPlugin(OpenReviewPlugin):
    pass
""")

    mgr = PackageManager(user_dir=user_packages_dir)
    dlg = PackageManagerDialog(pkg_mgr=mgr)

    # Find row with My Tool
    tool_row = -1
    for r in range(dlg.table.rowCount()):
        item = dlg.table.item(r, 0)
        if item and item.text() == "My Tool":
            tool_row = r
            break
    assert tool_row >= 0

    # Select My Tool
    dlg.table.selectRow(tool_row)
    dlg._on_row_selected()

    assert dlg.lbl_det_name.text() == "My Tool"
    assert dlg.btn_toggle_enable.text() == "Enable Plugin"
    assert dlg.table.item(tool_row, 2).text() == "Disabled"

    # Click Enable Plugin button
    dlg.btn_toggle_enable.click()

    # Must immediately update:
    assert dlg.btn_toggle_enable.text() == "Disable Plugin"
    assert dlg.table.item(tool_row, 2).text() == "Enabled"
    assert dlg.table.currentRow() == tool_row
    assert mgr.is_plugin_enabled("My Tool") is True

    # Click Disable Plugin button
    dlg.btn_toggle_enable.click()

    # Must immediately update back:
    assert dlg.btn_toggle_enable.text() == "Enable Plugin"
    assert dlg.table.item(tool_row, 2).text() == "Disabled"
    assert dlg.table.currentRow() == tool_row
    assert mgr.is_plugin_enabled("My Tool") is False

    dlg.close()

