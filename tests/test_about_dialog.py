"""
Tests for the About dialog and license registry in OpenReview.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from openreview.resources.licenses import get_license_registry, resolve_package_version, LICENSE_REGISTRY
from openreview.ui.about_dialog import AboutDialog
import openreview


def test_license_registry_integrity():
    """Verify license registry contains all required packages and complete fields."""
    licenses = get_license_registry()
    assert len(licenses) >= 10

    package_ids = {item["id"] for item in licenses}
    expected_ids = {
        "openreview",
        "pyside6",
        "numpy",
        "opencolorio",
        "pillow",
        "opencv-python",
        "openexr",
        "psutil",
        "reportlab",
        "lucide-icons",
    }
    assert expected_ids.issubset(package_ids)

    for item in licenses:
        assert item["name"], f"Missing name in {item}"
        assert item["license_type"], f"Missing license_type in {item}"
        assert item["copyright"], f"Missing copyright in {item}"
        assert item["homepage"].startswith("http"), f"Invalid homepage in {item}"
        assert len(item["license_text"]) > 50, f"License text too short in {item}"
        assert item["version"], f"Missing resolved version in {item}"


def test_resolve_package_version():
    """Verify dynamic and fallback package version resolution."""
    assert resolve_package_version("openreview", "0.0.0") == openreview.__version__
    assert resolve_package_version("non_existent_pkg_xyz", "1.2.3") == "1.2.3"
    # PySide6 is installed in the test environment
    pyside_ver = resolve_package_version("PySide6", "0.0.0")
    assert pyside_ver != "0.0.0"


def test_about_dialog_init(qtbot):
    """Test AboutDialog initialization, tabs, and overview content."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    assert dlg.windowTitle() == "About OpenReview"
    assert dlg.tabs.count() == 2
    assert dlg.tabs.tabText(0) == "About"
    assert dlg.tabs.tabText(1) == "Licenses"

    # Verify initial selection in Licenses tab
    assert dlg.list_widget.count() >= 10
    assert dlg.detail_title.text() != ""
    assert dlg.detail_text.toPlainText() != ""


def test_about_dialog_license_selection(qtbot):
    """Test selecting different items in license list updates details."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    # Find PySide6 row
    pyside_row = -1
    for i in range(dlg.list_widget.count()):
        item = dlg.list_widget.item(i)
        data = item.data(Qt.ItemDataRole.UserRole)
        if data.get("id") == "pyside6":
            pyside_row = i
            break

    assert pyside_row >= 0
    dlg.list_widget.setCurrentRow(pyside_row)

    assert "PySide6" in dlg.detail_title.text()
    assert "LGPL" in dlg.detail_license_tag.text()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in dlg.detail_text.toPlainText()
    assert dlg.btn_homepage.isEnabled()


def test_about_dialog_search_filtering(qtbot):
    """Test searching/filtering the license list."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    initial_count = dlg.list_widget.count()
    assert initial_count >= 10

    # Filter for numpy
    dlg.search_input.setText("numpy")
    assert dlg.list_widget.count() == 1
    item = dlg.list_widget.item(0)
    data = item.data(Qt.ItemDataRole.UserRole)
    assert data["id"] == "numpy"
    assert "NumPy" in dlg.detail_title.text()

    # Filter with no match
    dlg.search_input.setText("zzzz_non_existent_string")
    assert dlg.list_widget.count() == 0
    assert dlg.detail_title.text() == "No matches found"
    assert dlg.detail_text.toPlainText() == ""

    # Clear filter
    dlg.search_input.setText("")
    assert dlg.list_widget.count() == initial_count


def test_about_dialog_copy_license(qtbot):
    """Test copying license text to clipboard."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    dlg.list_widget.setCurrentRow(0)
    current_text = dlg.detail_text.toPlainText()
    assert current_text

    dlg._copy_license_text()
    clipboard_text = QGuiApplication.clipboard().text()
    assert clipboard_text == current_text
    assert "Copied" in dlg.btn_copy.text()


def test_about_dialog_link_handling(qtbot):
    """Test switching tabs via link click."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    dlg.tabs.setCurrentIndex(0)
    assert dlg.tabs.currentIndex() == 0

    dlg._handle_link_click("#licenses")
    assert dlg.tabs.currentIndex() == 1
