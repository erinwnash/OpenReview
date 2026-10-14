"""
Top Floating Annotation and Markup Tool Strip.
Figma / Miro-inspired glassmorphic capsule pill HUD overlaid at the top of the viewport canvas,
featuring drawing tools, live brush size & opacity sliders, circular color swatches, and undo/clear.
"""
from __future__ import annotations

from typing import Optional, Tuple
from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QButtonGroup,
    QFrame,
    QLabel,
    QSlider,
    QGraphicsDropShadowEffect,
)
from openreview.models.annotations import ShapeType
from openreview.resources import get_markup_icon


class MarkupToolPalette(QFrame):
    """
    Floating horizontal annotation capsule pill positioned at the top of the viewport canvas.
    """

    tool_changed = Signal(object)  # Optional[ShapeType]: None = Select / Pan mode
    color_changed = Signal(tuple)  # (r, g, b, a)
    stroke_width_changed = Signal(float)  # Stroke width in pixels (1.0 to 32.0)
    opacity_changed = Signal(float)  # Stroke opacity (0.1 to 1.0)
    clear_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MarkupToolPalette")
        self.setFixedHeight(42)
        self._current_tool: Optional[ShapeType] = None
        self._current_color: Tuple[int, int, int, int] = (255, 209, 59, 255)  # Vibrant Yellow (#ffd13b)
        self._current_width: float = 5.0
        self._current_opacity: float = 1.0

        # Dragging & layout state
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._user_dragged: bool = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#MarkupToolPalette {
                background-color: rgba(18, 20, 26, 0.90);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-top: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
            }
            QFrame#MarkupToolPalette > QPushButton {
                min-width: 26px;
                min-height: 26px;
                max-width: 26px;
                max-height: 26px;
                padding: 3px;
                border: 1px solid transparent;
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 0.04);
            }
            QFrame#MarkupToolPalette > QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border-color: rgba(255, 255, 255, 0.25);
            }
            QFrame#MarkupToolPalette > QPushButton:checked {
                background-color: rgba(229, 168, 35, 0.25);
                border-color: #e5a823;
            }
            QFrame#MarkupToolPalette > QSlider {
                background: transparent;
                background-color: transparent;
            }
            QFrame#MarkupToolPalette > QSlider::groove:horizontal {
                height: 3px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 1px;
            }
            QFrame#MarkupToolPalette > QSlider::sub-page:horizontal {
                background: #e5a823;
                border-radius: 1px;
            }
            QFrame#MarkupToolPalette > QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.35);
                width: 10px;
                height: 10px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 5px;
            }
            QFrame#MarkupToolPalette > QSlider::handle:horizontal:hover {
                background: #e5a823;
                border-color: #ffffff;
            }
            QFrame#MarkupToolPalette > QLabel {
                color: #b0b0b0;
                font-size: 11px;
                background: transparent;
            }
        """)

        # Drop shadow for floating glass elevation
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 0. Subtle Drag Grip Indicator
        self.lbl_grip = QLabel("⠿", self)
        self.lbl_grip.setStyleSheet("color: #666666; font-size: 14px; padding-right: 2px;")
        self.lbl_grip.setToolTip("Drag to move annotation toolbox")
        self.lbl_grip.setCursor(Qt.CursorShape.SizeAllCursor)
        layout.addWidget(self.lbl_grip, 0, Qt.AlignmentFlag.AlignVCenter)

        # 1. Tools Group
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        # Select / Pan Mode (Default)
        self.btn_select = QPushButton(self)
        self.btn_select.setIcon(get_markup_icon("select"))
        self.btn_select.setIconSize(QSize(16, 16))
        self.btn_select.setToolTip("Pan / Select Mode (Esc / Alt+LMB)")
        self.btn_select.setCheckable(True)
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self._select_tool(None))
        self.btn_group.addButton(self.btn_select)
        layout.addWidget(self.btn_select, 0, Qt.AlignmentFlag.AlignVCenter)

        # Pen Tool
        self.btn_pen = QPushButton(self)
        self.btn_pen.setIcon(get_markup_icon("pen"))
        self.btn_pen.setIconSize(QSize(16, 16))
        self.btn_pen.setToolTip("Freehand Pen Tool (D)")
        self.btn_pen.setCheckable(True)
        self.btn_pen.clicked.connect(lambda: self._select_tool(ShapeType.PEN))
        self.btn_group.addButton(self.btn_pen)
        layout.addWidget(self.btn_pen, 0, Qt.AlignmentFlag.AlignVCenter)

        # Line Tool
        self.btn_line = QPushButton(self)
        self.btn_line.setIcon(get_markup_icon("line"))
        self.btn_line.setIconSize(QSize(16, 16))
        self.btn_line.setToolTip("Straight Line Tool")
        self.btn_line.setCheckable(True)
        self.btn_line.clicked.connect(lambda: self._select_tool(ShapeType.LINE))
        self.btn_group.addButton(self.btn_line)
        layout.addWidget(self.btn_line, 0, Qt.AlignmentFlag.AlignVCenter)

        # Arrow Tool
        self.btn_arrow = QPushButton(self)
        self.btn_arrow.setIcon(get_markup_icon("arrow"))
        self.btn_arrow.setIconSize(QSize(16, 16))
        self.btn_arrow.setToolTip("Arrow Tool")
        self.btn_arrow.setCheckable(True)
        self.btn_arrow.clicked.connect(lambda: self._select_tool(ShapeType.ARROW))
        self.btn_group.addButton(self.btn_arrow)
        layout.addWidget(self.btn_arrow, 0, Qt.AlignmentFlag.AlignVCenter)

        # Rectangle Tool
        self.btn_box = QPushButton(self)
        self.btn_box.setIcon(get_markup_icon("rect"))
        self.btn_box.setIconSize(QSize(16, 16))
        self.btn_box.setToolTip("Rectangle Tool")
        self.btn_box.setCheckable(True)
        self.btn_box.clicked.connect(lambda: self._select_tool(ShapeType.RECTANGLE))
        self.btn_group.addButton(self.btn_box)
        layout.addWidget(self.btn_box, 0, Qt.AlignmentFlag.AlignVCenter)

        # Circle Tool
        self.btn_circle = QPushButton(self)
        self.btn_circle.setIcon(get_markup_icon("circle"))
        self.btn_circle.setIconSize(QSize(16, 16))
        self.btn_circle.setToolTip("Circle / Ellipse Tool")
        self.btn_circle.setCheckable(True)
        self.btn_circle.clicked.connect(lambda: self._select_tool(ShapeType.CIRCLE))
        self.btn_group.addButton(self.btn_circle)
        layout.addWidget(self.btn_circle, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text Tool
        self.btn_text = QPushButton(self)
        self.btn_text.setIcon(get_markup_icon("text"))
        self.btn_text.setIconSize(QSize(16, 16))
        self.btn_text.setToolTip("Text Annotation Tool")
        self.btn_text.setCheckable(True)
        self.btn_text.clicked.connect(lambda: self._select_tool(ShapeType.TEXT))
        self.btn_group.addButton(self.btn_text)
        layout.addWidget(self.btn_text, 0, Qt.AlignmentFlag.AlignVCenter)

        # Divider 1
        div1 = self._create_divider()
        layout.addWidget(div1, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Live Brush Size Slider (Compact responsive width: 56px)
        lbl_size_icon = QLabel(self)
        lbl_size_icon.setPixmap(get_markup_icon("brush_size").pixmap(14, 14))
        lbl_size_icon.setFixedSize(14, 14)
        lbl_size_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_size_icon.setToolTip("Brush Stroke Width")
        layout.addWidget(lbl_size_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.slider_size = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_size.setRange(1, 32)
        self.slider_size.setValue(5)
        self.slider_size.setFixedWidth(100)
        self.slider_size.setToolTip("Brush Stroke Width (1 - 32px)")
        self.slider_size.valueChanged.connect(self._on_size_slider_changed)
        layout.addWidget(self.slider_size, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_size = QLabel("5px", self)
        self.lbl_size.setFixedWidth(26)
        self.lbl_size.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_size.setStyleSheet("color: #ffd13b; font-family: monospace; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.lbl_size, 0, Qt.AlignmentFlag.AlignVCenter)

        # Live Opacity Slider (Responsive width: 90px)
        lbl_opac_icon = QLabel(self)
        lbl_opac_icon.setPixmap(get_markup_icon("opacity").pixmap(14, 14))
        lbl_opac_icon.setFixedSize(14, 14)
        lbl_opac_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_opac_icon.setToolTip("Brush Stroke Opacity")
        layout.addWidget(lbl_opac_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setFixedWidth(90)
        self.slider_opacity.setToolTip("Brush Stroke Opacity (10% - 100%)")
        self.slider_opacity.valueChanged.connect(self._on_opacity_slider_changed)
        layout.addWidget(self.slider_opacity, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_opacity = QLabel("100%", self)
        self.lbl_opacity.setFixedWidth(32)
        self.lbl_opacity.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_opacity.setStyleSheet("color: #cccccc; font-family: monospace; font-size: 10px;")
        layout.addWidget(self.lbl_opacity, 0, Qt.AlignmentFlag.AlignVCenter)

        # Divider 2
        div2 = self._create_divider()
        layout.addWidget(div2, 0, Qt.AlignmentFlag.AlignVCenter)

        # 3. Circular Color Swatches + Custom Color Picker
        swatches = [
            ((255, 209, 59, 255), "#ffd13b", "Yellow"),
            ((255, 77, 79, 255), "#ff4d4f", "Red"),
            ((37, 194, 112, 255), "#25c270", "Green"),
            ((24, 144, 255, 255), "#1890ff", "Blue"),
            ((255, 255, 255, 255), "#ffffff", "White"),
        ]
        self.swatch_group = QButtonGroup(self)
        self.swatch_group.setExclusive(True)
        self.swatch_buttons = []

        for rgba, hex_code, tip in swatches:
            btn = QPushButton(self)
            btn.setFixedSize(16, 16)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_code};
                    border: 1px solid rgba(0, 0, 0, 0.4);
                    border-radius: 8px;
                    min-width: 16px;
                    min-height: 16px;
                    max-width: 16px;
                    max-height: 16px;
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
                QPushButton:checked {{
                    border: 2px solid #ffffff;
                }}
            """)
            if hex_code == "#ffd13b":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, c=rgba: self._set_color(c))
            self.swatch_group.addButton(btn)
            self.swatch_buttons.append(btn)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Custom Color Picker Button
        self.btn_custom_color = QPushButton(self)
        self.btn_custom_color.setIcon(get_markup_icon("color_picker"))
        self.btn_custom_color.setIconSize(QSize(16, 16))
        self.btn_custom_color.setToolTip("Custom Color Picker & Swatch...")
        self.btn_custom_color.setFixedSize(26, 26)
        self.btn_custom_color.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 6px;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                padding: 3px;
            }
            QPushButton:hover {
                border-color: #ffd13b;
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        self.btn_custom_color.clicked.connect(self._open_custom_color_dialog)
        layout.addWidget(self.btn_custom_color, 0, Qt.AlignmentFlag.AlignVCenter)

        # Divider 3
        div3 = self._create_divider()
        layout.addWidget(div3, 0, Qt.AlignmentFlag.AlignVCenter)

        # 4. Actions: Undo / Redo / Clear / Close
        self.btn_undo = QPushButton(self)
        self.btn_undo.setIcon(get_markup_icon("undo"))
        self.btn_undo.setIconSize(QSize(16, 16))
        self.btn_undo.setToolTip("Undo Annotation (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        layout.addWidget(self.btn_undo, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_redo = QPushButton(self)
        self.btn_redo.setIcon(get_markup_icon("redo"))
        self.btn_redo.setIconSize(QSize(16, 16))
        self.btn_redo.setToolTip("Redo Annotation (Ctrl+Y / Ctrl+Shift+Z)")
        self.btn_redo.clicked.connect(self.redo_requested.emit)
        layout.addWidget(self.btn_redo, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_clear = QPushButton(self)
        self.btn_clear.setIcon(get_markup_icon("clear"))
        self.btn_clear.setIconSize(QSize(16, 16))
        self.btn_clear.setToolTip("Clear Annotations on this frame (Delete)")
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.btn_clear, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_close = QPushButton(self)
        self.btn_close.setIcon(get_markup_icon("close"))
        self.btn_close.setIconSize(QSize(13, 13))
        self.btn_close.setToolTip("Close Annotation Toolbox (X)")
        self.btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignVCenter)

        # Never steal keyboard focus from viewport/timeline
        for btn in self.findChildren(QPushButton):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_size.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_opacity.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _create_divider(self) -> QFrame:
        div = QFrame(self)
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setFixedHeight(18)
        div.setStyleSheet("background-color: rgba(255, 255, 255, 0.12);")
        return div

    # --------------------------------------------------------------------------
    # Interactive Sliders & Actions
    # --------------------------------------------------------------------------
    def _on_size_slider_changed(self, val: int) -> None:
        self._current_width = float(val)
        self.lbl_size.setText(f"{val}px")
        self.stroke_width_changed.emit(self._current_width)

    def _on_opacity_slider_changed(self, val: int) -> None:
        self._current_opacity = float(val) / 100.0
        self.lbl_opacity.setText(f"{val}%")
        self.opacity_changed.emit(self._current_opacity)

    def _open_custom_color_dialog(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        init_col = QColor(*self._current_color)
        dlg = QColorDialog(init_col, self.window())
        dlg.setWindowTitle("Choose Custom Annotation Color")
        dlg.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dlg.setStyleSheet("""
            QColorDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            QPushButton {
                background-color: #2c2c2c;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 3px;
                padding: 4px 14px;
                min-height: 24px;
                min-width: 80px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #ffd13b;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #ffd13b;
                color: #121212;
            }
            QLineEdit, QSpinBox {
                background-color: #141414;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 3px 6px;
                font-family: monospace;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #ffd13b;
            }
        """ + __import__("openreview.ui.theme", fromlist=["get_spinbox_arrow_stylesheet"]).get_spinbox_arrow_stylesheet())
        if dlg.exec() == QColorDialog.DialogCode.Accepted:
            col = dlg.selectedColor()
            if col.isValid():
                rgba = (col.red(), col.green(), col.blue(), col.alpha())
                self._set_color(rgba)
                self.btn_custom_color.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {col.name()};
                        border: 2px solid #ffffff;
                        border-radius: 6px;
                        min-width: 28px;
                        max-width: 28px;
                        min-height: 28px;
                        max-height: 28px;
                        padding: 4px;
                    }}
                    QPushButton:hover {{
                        border-color: #ffd13b;
                    }}
                """)

    def _select_tool(self, tool: Optional[ShapeType]) -> None:
        self._current_tool = tool
        self.tool_changed.emit(tool)

    def select_tool(self, tool: Optional[ShapeType]) -> None:
        """Programmatically select an annotation tool and update button checked states."""
        if tool is None:
            self.btn_select.setChecked(True)
        elif tool == ShapeType.PEN:
            self.btn_pen.setChecked(True)
        elif tool == ShapeType.ARROW:
            self.btn_arrow.setChecked(True)
        elif tool == ShapeType.RECTANGLE:
            self.btn_box.setChecked(True)
        elif tool == ShapeType.CIRCLE:
            self.btn_circle.setChecked(True)
        elif tool == ShapeType.TEXT:
            self.btn_text.setChecked(True)
        self._select_tool(tool)

    def _set_color(self, color: Tuple[int, int, int, int]) -> None:
        self._current_color = color
        self.color_changed.emit(color)

    def toggle_draw(self) -> None:
        """Triggered by shortcut 'D'."""
        if self._current_tool == ShapeType.PEN:
            self.btn_select.setChecked(True)
            self._select_tool(None)
        else:
            self.btn_pen.setChecked(True)
            self._select_tool(ShapeType.PEN)

    # --------------------------------------------------------------------------
    # Dynamic Auto-Centering & Dragging
    # --------------------------------------------------------------------------
    def clamp_in_parent(self) -> None:
        """Ensure the toolbox remains fully visible within the parent canvas."""
        parent = self.parentWidget()
        if parent:
            self.adjustSize()
            max_x = max(0, parent.width() - self.width())
            max_y = max(0, parent.height() - self.height())
            cx = max(0, min(self.x(), max_x))
            cy = max(0, min(self.y(), max_y))
            if cx != self.x() or cy != self.y():
                self.move(cx, cy)

    def auto_center_in_parent(self, force: bool = False) -> None:
        """Auto-center along the top of parent canvas with 12px top margin."""
        if not force and self._user_dragged:
            self.clamp_in_parent()
            return
        parent = self.parentWidget()
        if parent:
            pw = parent.width()
            self.adjustSize()
            w = self.width() if self.width() > 100 else 520
            x = max(6, (pw - w) // 2)
            self.move(x, 16)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            parent = self.parentWidget()
            if parent:
                new_pos = event.globalPosition().toPoint() - self._drag_start_pos
                # Clamp within parent bounds
                max_x = max(0, parent.width() - self.width())
                max_y = max(0, parent.height() - self.height())
                clamped_x = max(0, min(new_pos.x(), max_x))
                clamped_y = max(0, min(new_pos.y(), max_y))
                self.move(clamped_x, clamped_y)
                self._user_dragged = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


# Alias for backwards compatibility with any existing imports
FloatingAnnotationBar = MarkupToolPalette
