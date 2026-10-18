"""
OpenReview static resources and icon asset loaders.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from PySide6.QtGui import QIcon

if getattr(sys, "frozen", False):
    _meipass = Path(sys._MEIPASS)
    PROJECT_ROOT = _meipass
    if (_meipass / "openreview" / "resources").exists():
        RESOURCES_DIR = _meipass / "openreview" / "resources"
    else:
        RESOURCES_DIR = _meipass
else:
    RESOURCES_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = Path(__file__).resolve().parents[3]

ICONS_DIR = RESOURCES_DIR / "icons" if (RESOURCES_DIR / "icons").exists() else RESOURCES_DIR


def get_app_icon_path() -> Path:
    """Return the absolute path to the primary application icon."""
    for root in (PROJECT_ROOT, RESOURCES_DIR, RESOURCES_DIR.parent):
        svg_icon = root / "openreview-primary-logo.svg"
        if svg_icon.exists():
            return svg_icon
    ico = ICONS_DIR / "openreview.ico"
    if ico.exists():
        return ico
    return ICONS_DIR / "openreview.png"


def get_app_logo_path() -> Path:
    """Return the absolute path to the OpenReview horizontal logo for the About dialog."""
    for root in (PROJECT_ROOT, RESOURCES_DIR, RESOURCES_DIR.parent):
        svg_logo = root / "openreview-logo-horizontal.svg"
        if svg_logo.exists():
            return svg_logo
    return get_app_icon_path()


def get_app_icon() -> QIcon:
    """Return a QIcon loaded with openreview-primary-logo.svg and multi-resolution icon assets."""
    icon = QIcon()
    found_svg = False
    for root in (PROJECT_ROOT, RESOURCES_DIR, RESOURCES_DIR.parent):
        svg_icon = root / "openreview-primary-logo.svg"
        if svg_icon.exists():
            try:
                from PySide6.QtSvg import QSvgRenderer
                from PySide6.QtGui import QPixmap, QPainter
                from PySide6.QtCore import Qt, QRectF
                renderer = QSvgRenderer(str(svg_icon))
                if renderer.isValid():
                    for sz in (16, 20, 24, 32, 48, 64, 128, 256, 512):
                        pix = QPixmap(sz, sz)
                        pix.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(pix)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        renderer.render(painter, QRectF(0, 0, sz, sz))
                        painter.end()
                        icon.addPixmap(pix)
                    found_svg = True
                    break
            except Exception:
                pass
            temp = QIcon(str(svg_icon))
            for sz in (16, 20, 24, 32, 48, 64, 128, 256, 512):
                pix = temp.pixmap(sz, sz)
                if not pix.isNull():
                    icon.addPixmap(pix)
            icon.addFile(str(svg_icon))
            found_svg = True
            break
    if not found_svg:
        for name in ["openreview.ico", "openreview.png", "favicon-32x32.png", "favicon-16x16.png"]:
            p = ICONS_DIR / name
            if p.exists():
                icon.addFile(str(p))
    return icon


def get_favicon_path() -> Path:
    """Return the absolute path to the favicon."""
    for root in (PROJECT_ROOT, RESOURCES_DIR, RESOURCES_DIR.parent):
        svg_icon = root / "openreview-primary-logo.svg"
        if svg_icon.exists():
            return svg_icon
    fav = ICONS_DIR / "favicon.ico"
    if fav.exists():
        return fav
    return ICONS_DIR / "favicon.png"


def get_branch_closed_icon_path() -> Path:
    """Return the absolute path to the smooth antialiased vector closed branch arrow."""
    svg_p = ICONS_DIR / "branch_closed.svg"
    if svg_p.exists():
        return svg_p
    return ICONS_DIR / "branch_closed.png"


def get_branch_open_icon_path() -> Path:
    """Return the absolute path to the smooth antialiased vector open branch arrow."""
    svg_p = ICONS_DIR / "branch_open.svg"
    if svg_p.exists():
        return svg_p
    return ICONS_DIR / "branch_open.png"


def get_spin_up_icon_path(pressed: bool = False) -> Path:
    """Return the absolute path to the spinbox up-arrow solid triangle SVG."""
    name = "spin_up_pressed.svg" if pressed else "spin_up.svg"
    return ICONS_DIR / name


def get_spin_down_icon_path(pressed: bool = False) -> Path:
    """Return the absolute path to the spinbox down-arrow solid triangle SVG."""
    name = "spin_down_pressed.svg" if pressed else "spin_down.svg"
    return ICONS_DIR / name


def get_markup_icon(name: str) -> QIcon:
    """Return a styled QIcon with both normal and active/checked vector states."""
    icon = QIcon()
    p_norm = ICONS_DIR / "markup" / f"{name}.svg"
    p_act = ICONS_DIR / "markup" / f"{name}_active.svg"
    if p_norm.exists():
        icon.addFile(str(p_norm), state=QIcon.State.Off)
    if p_act.exists():
        icon.addFile(str(p_act), state=QIcon.State.On)
    elif p_norm.exists():
        icon.addFile(str(p_norm), state=QIcon.State.On)
    return icon


_VFX_ICON_CACHE: dict[str, QIcon] = {}


def get_vfx_icon(name: str) -> QIcon:
    """Return a cached high-DPI QIcon loaded from resources/icons/<name>.svg."""
    if name in _VFX_ICON_CACHE:
        return _VFX_ICON_CACHE[name]

    svg_p = ICONS_DIR / f"{name}.svg"
    icon = QIcon()
    if svg_p.exists():
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPixmap, QPainter
            from PySide6.QtCore import Qt, QRectF
            renderer = QSvgRenderer(str(svg_p))
            if renderer.isValid():
                for sz in (16, 20, 24, 32, 48):
                    pix = QPixmap(sz, sz)
                    pix.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pix)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    renderer.render(painter, QRectF(0, 0, sz, sz))
                    painter.end()
                    icon.addPixmap(pix)
        except Exception:
            icon.addFile(str(svg_p))
    else:
        icon.addFile(str(svg_p))

    _VFX_ICON_CACHE[name] = icon
    return icon


def get_docs_dir() -> Path:
    """Return the absolute path to the HTML documentation directory."""
    for root in (PROJECT_ROOT, RESOURCES_DIR, Path(sys.executable).parent if getattr(sys, "frozen", False) else PROJECT_ROOT):
        docs_dir = root / "docs" / "html"
        if docs_dir.exists():
            return docs_dir
    return PROJECT_ROOT / "docs" / "html"


def get_licenses() -> list[dict]:
    """Return the license registry for OpenReview and its third-party components."""
    from openreview.resources.licenses import get_license_registry
    return get_license_registry()

