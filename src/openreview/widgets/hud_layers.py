"""
Multi-Channel EXR Layers & Passes HUD Widget.
Provides togglable floating widget to inspect and switch active EXR passes.
"""
from __future__ import annotations

from typing import Optional, List
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QFrame,
)


class HUDLayersWidget(QWidget):
    """Interactive widget for selecting multi-channel EXR render passes and AOVs."""

    layer_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        self._layers: List[str] = ["beauty"]
        self._current_layer: str = "beauty"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        hdr_lbl = QLabel("Multi-Channel EXR Passes / AOVs", self)
        hdr_lbl.setStyleSheet("font-weight: bold; color: #e5a823; font-size: 11px;")
        layout.addWidget(hdr_lbl)

        self.list_layers = QListWidget(self)
        self.list_layers.setStyleSheet("""
            QListWidget {
                background-color: #141414;
                border: 1px solid #2e2e2e;
                color: #cccccc;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px 6px;
            }
            QListWidget::item:selected {
                background-color: #2c281e;
                color: #e5a823;
                font-weight: bold;
            }
        """)
        self.list_layers.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_layers)

        self.refresh_list(["beauty"])

    def refresh_list(self, layers: List[str]) -> None:
        """Populate available passes list."""
        self._layers = layers if layers else ["beauty"]
        self.list_layers.clear()
        for lyr in self._layers:
            item = QListWidgetItem(lyr)
            self.list_layers.addItem(item)
            if lyr == self._current_layer:
                self.list_layers.setCurrentItem(item)

    def set_current_layer(self, layer: str) -> None:
        self._current_layer = layer
        for i in range(self.list_layers.count()):
            item = self.list_layers.item(i)
            if item.text() == layer:
                self.list_layers.setCurrentItem(item)
                break

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._current_layer = item.text()
        self.layer_changed.emit(self._current_layer)
