"""
Unit and Integration Tests for Studio OpenColorIO Config Loader.
Covers OCIOManager config loading, .ocio syntax parser, display/view/colorspace discovery,
OCIOConfigDialog UI, and MainWindow top bar color space integration.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from PySide6.QtCore import Qt

from openreview.color.ocio_manager import OCIOManager
from openreview.ui.ocio_dialog import OCIOConfigDialog
from openreview.ui.main_window import MainWindow


SAMPLE_STUDIO_OCIO = """ocio_profile_version: 2

description: Studio Production ACES Pipeline v2.1

roles:
  default: Raw
  scene_linear: ACEScg
  color_picking: sRGB
  compositing_log: Cineon

displays:
  sRGB:
    - !<View> {name: ACES 1.0 - SDR Video, colorspace: ACEScg}
    - !<View> {name: Raw, colorspace: Raw}
  Rec709:
    - !<View> {name: Rec.709 - Display, colorspace: sRGB}

colorspaces:
  - !<ColorSpace>
    name: ACEScg
    family: ACES
    equalitygroup: ""
    bitdepth: 32f

  - !<ColorSpace>
    name: ACES2065-1
    family: ACES
    equalitygroup: ""
    bitdepth: 32f

  - !<ColorSpace>
    name: sRGB
    family: Utility
    equalitygroup: ""
    bitdepth: 8i

  - !<ColorSpace>
    name: Cineon
    family: Film
    equalitygroup: ""
    bitdepth: 10i

  - !<ColorSpace>
    name: Raw
    family: Raw
    equalitygroup: ""
    bitdepth: 32f

looks:
  - !<Look>
    name: WarmDailies
    process_space: ACEScg

  - !<Look>
    name: CoolShadows
    process_space: ACEScg
"""


def test_ocio_manager_custom_config_parsing(tmp_path):
    """Test loading and parsing a studio .ocio configuration file."""
    config_file = tmp_path / "studio_config.ocio"
    config_file.write_text(SAMPLE_STUDIO_OCIO, encoding="utf-8")

    mgr = OCIOManager()
    signal_received = []
    mgr.config_changed.connect(lambda: signal_received.append(True))

    success = mgr.load_config(config_file)
    assert success is True
    assert len(signal_received) == 1
    assert mgr.config_path == str(config_file.resolve())

    # Check parsed colorspaces
    spaces = mgr.get_color_spaces()
    assert "ACEScg" in spaces
    assert "ACES2065-1" in spaces
    assert "sRGB" in spaces
    assert "Cineon" in spaces
    assert "Raw" in spaces

    # Check parsed displays and views
    displays = mgr.get_displays()
    assert "sRGB" in displays
    assert "Rec709" in displays

    views = mgr.get_views("sRGB")
    assert "ACES 1.0 - SDR Video" in views
    assert "Raw" in views

    # Check roles and looks
    roles = mgr.get_roles()
    assert roles.get("scene_linear") == "ACEScg"
    assert roles.get("color_picking") == "sRGB"
    assert roles.get("compositing_log") == "Cineon"

    looks = mgr.get_looks()
    assert "WarmDailies" in looks
    assert "CoolShadows" in looks

    # Reset to default
    mgr.reset_to_default()
    assert mgr.config_path is None
    assert len(signal_received) == 2


def test_ocio_config_dialog_ui(qtbot, tmp_path, monkeypatch):
    """Test OCIOConfigDialog controls, config loading, and inspection lists."""
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None)
    config_file = tmp_path / "custom_pipe.ocio"
    config_file.write_text(SAMPLE_STUDIO_OCIO, encoding="utf-8")

    mgr = OCIOManager()
    dlg = OCIOConfigDialog(mgr)
    qtbot.addWidget(dlg)

    # Initial dialog state
    assert dlg.edit_path.text() == "Built-in ACES Studio Configuration"
    assert dlg.combo_display.count() > 0

    # Load custom config directly into dialog
    mgr.load_config(str(config_file))
    dlg._populate_ui()
    assert str(config_file.resolve()) == dlg.edit_path.text()
    assert dlg.combo_display.currentText() in ("sRGB", "Rec709")

    # Check Roles List populated
    assert dlg.list_roles.count() >= 3
    role_texts = [dlg.list_roles.item(i).text() for i in range(dlg.list_roles.count())]
    assert any("scene_linear" in t for t in role_texts)

    # Check Looks List populated
    assert dlg.list_looks.count() >= 2
    look_texts = [dlg.list_looks.item(i).text() for i in range(dlg.list_looks.count())]
    assert any("WarmDailies" in t for t in look_texts)

    # Test Reset Button
    dlg.btn_reset.click()
    assert dlg.edit_path.text() == "Built-in ACES Studio Configuration"


def test_main_window_ocio_integration(qtbot, tmp_path):
    """Test MainWindow dynamic update of top bar combos upon loading custom OCIO config."""
    config_file = tmp_path / "studio.ocio"
    config_file.write_text(SAMPLE_STUDIO_OCIO, encoding="utf-8")

    win = MainWindow()
    qtbot.addWidget(win)

    # Load custom config into MainWindow's OCIOManager
    win.ocio_manager.load_config(config_file)

    # Verify TopBar dropdowns are updated with custom config spaces and views
    input_items = [win.top_bar.input_combo.itemText(i) for i in range(win.top_bar.input_combo.count())]
    assert "ACEScg" in input_items
    assert "Cineon" in input_items

    view_items = [win.top_bar.view_combo.itemText(i) for i in range(win.top_bar.view_combo.count())]
    assert "ACES 1.0 - SDR Video" in view_items or "Raw" in view_items
