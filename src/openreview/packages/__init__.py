"""
OpenReview Package and Plugin Management Subsystem.
"""
from openreview.packages.manifest import PackageManifest
from openreview.packages.plugin_base import OpenReviewPlugin, PluginContext
from openreview.packages.package_manager import PackageManager
from openreview.packages.updater import SoftwareUpdater, UpdateInfo

__all__ = [
    "PackageManifest",
    "OpenReviewPlugin",
    "PluginContext",
    "PackageManager",
    "SoftwareUpdater",
    "UpdateInfo",
]
