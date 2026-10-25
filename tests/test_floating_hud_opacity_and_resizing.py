"""
Tests for FloatingHUDCard dynamic resizing expansion, glass opacity controls,
Preferences integration, and elimination of ghost widget overlap in ImageInfoWidget.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from openreview.widgets.floating_hud import FloatingHUDCard
from openreview.ui.image_info_dialog import ImageInfoWidget
from openreview.core.preferences import PreferencesManager, UserPreferences
from openreview.ui.preferences_dialog import PreferencesDialog
from openreview.core.shortcuts import ShortcutManager


def test_floating_hud_card_resizing_expansion(qtbot):
    content = QWidget()
    content_layout = QVBoxLayout(content)
    label = QLabel("Dynamic Content Label", content)
    content_layout.addWidget(label)

    hud = FloatingHUDCard(
        title="Test HUD",
        content_widget=content,
        initial_pos=QPoint(10, 10),
    )
    qtbot.addWidget(hud)
    hud.resize(400, 300)
    hud.show()
    qtbot.waitExposed(hud)

    # Initial height of content widget
    h1 = content.height()
    assert h1 > 0

    # Resize HUD card taller
    hud.resize(400, 600)
    hud.layout().activate()
    h2 = content.height()

    # Content widget should expand dynamically with stretch=1 to fill the card
    assert h2 > h1
    assert h2 >= 540  # 600 minus title bar, grip bar, and layout margins


def test_floating_hud_card_opacity_updates(qtbot):
    content = QWidget()
    hud = FloatingHUDCard(
        title="Opacity Test HUD",
        content_widget=content,
    )
    qtbot.addWidget(hud)

    # Default opacity should be 85%
    assert abs(hud._hud_opacity - 0.85) < 1e-4

    # Test 50% opacity -> alpha = 127
    hud.set_hud_opacity(0.50)
    assert abs(hud._hud_opacity - 0.50) < 1e-4

    # Test 100% opacity -> alpha = 255
    hud.set_hud_opacity(1.0)
    assert abs(hud._hud_opacity - 1.0) < 1e-4

    # Test clamping: < 0.3 clamps to 0.3
    hud.set_hud_opacity(0.1)
    assert abs(hud._hud_opacity - 0.30) < 1e-4


def test_image_info_widget_no_ghost_overlap_on_update(qtbot):
    info1 = {
        "file_name": "shot_01.exr",
        "all_metadata_tags": {"camera": "Alexa"},
    }
    widget = ImageInfoWidget(info1)
    qtbot.addWidget(widget)

    old_content = widget._scroll_area.widget()
    assert old_content is not None

    # Call update_info to simulate frame change or source switch
    info2 = {
        "file_name": "shot_02.exr",
        "all_metadata_tags": {"camera": "Red V-Raptor"},
    }
    widget.update_info(info2)
    new_content = widget._scroll_area.widget()

    # Ensure previous content was detached and replaced
    assert new_content is not old_content
    assert widget.meta_table.rowCount() == 1
    assert widget.meta_table.item(0, 1).text() == "Red V-Raptor"


def test_preferences_hud_opacity_slider_and_persistence(qtbot):
    pref_mgr = PreferencesManager()
    prefs = pref_mgr.prefs
    prefs.hud_opacity = 0.80

    dialog = PreferencesDialog(pref_mgr)
    qtbot.addWidget(dialog)

    # Check slider loaded value
    assert dialog.slider_hud_opacity.value() == 80
    assert dialog.lbl_hud_opacity_val.text() == "80%"

    # Test slider interaction emits signal
    emitted = []
    dialog.hud_opacity_changed.connect(lambda v: emitted.append(v))

    dialog.slider_hud_opacity.setValue(65)
    assert len(emitted) == 1
    assert abs(emitted[0] - 0.65) < 1e-4
    assert dialog.lbl_hud_opacity_val.text() == "65%"

    # Test gathering preferences saves the value
    gathered = dialog._gather_prefs()
    assert abs(gathered.hud_opacity - 0.65) < 1e-4


def test_preferences_default_hud_opacity():
    prefs = UserPreferences()
    assert abs(prefs.hud_opacity - 0.85) < 1e-4


def test_shortcuts_batch_and_apply_performance(monkeypatch, qtbot):
    pref_mgr = PreferencesManager()
    dialog = PreferencesDialog(pref_mgr)
    qtbot.addWidget(dialog)

    # Count how many times mgr.save is invoked during _apply
    save_calls = []
    monkeypatch.setattr(pref_mgr, "save", lambda *args, **kwargs: save_calls.append(1))

    dialog._apply()

    # Must only save exactly once (not 50+ times)
    assert len(save_calls) == 1


def test_markup_tool_palette_opacity_sync(qtbot):
    from openreview.widgets.markup_tools import MarkupToolPalette

    palette = MarkupToolPalette()
    qtbot.addWidget(palette)

    # Initial default matches preferences HUD opacity (0.85)
    assert abs(palette._hud_opacity - 0.85) < 1e-4

    # Dynamically update opacity
    palette.set_hud_opacity(0.60)
    assert abs(palette._hud_opacity - 0.60) < 1e-4

    # Test clamping
    palette.set_hud_opacity(0.10)
    assert abs(palette._hud_opacity - 0.30) < 1e-4

    palette.set_hud_opacity(1.50)
    assert abs(palette._hud_opacity - 1.00) < 1e-4
