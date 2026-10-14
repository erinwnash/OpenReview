"""
LUT and ASC CDL Parser and Texture Manager for OpenReview.
Supports 1D and 3D .cube LUTs, .3dl tables, and ASC CDL (.cdl, .cc, XML) profiles.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np


@dataclass
class AscCdl:
    """ASC CDL (Color Decision List) Slope, Offset, Power, and Saturation."""
    slope: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    power: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    saturation: float = 1.0
    name: str = "Default"

    @classmethod
    def from_file(cls, file_path: str) -> AscCdl:
        """Parse ASC CDL from XML (.cdl, .cc, .ccc) or plain text."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".cdl", ".cc", ".ccc", ".xml"):
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                # Find ColorCorrection / SOPNode
                slope = (1.0, 1.0, 1.0)
                offset = (0.0, 0.0, 0.0)
                power = (1.0, 1.0, 1.0)
                sat = 1.0

                for elem in root.iter():
                    tag = elem.tag.split("}")[-1]  # Strip namespaces
                    if tag == "Slope" and elem.text:
                        parts = [float(x) for x in elem.text.split()]
                        if len(parts) == 3:
                            slope = tuple(parts)
                    elif tag == "Offset" and elem.text:
                        parts = [float(x) for x in elem.text.split()]
                        if len(parts) == 3:
                            offset = tuple(parts)
                    elif tag == "Power" and elem.text:
                        parts = [float(x) for x in elem.text.split()]
                        if len(parts) == 3:
                            power = tuple(parts)
                    elif tag == "Saturation" and elem.text:
                        sat = float(elem.text.strip())

                return cls(
                    slope=slope,
                    offset=offset,
                    power=power,
                    saturation=sat,
                    name=os.path.basename(file_path),
                )
            except Exception:
                pass

        # Plain text fallback parser
        slope = [1.0, 1.0, 1.0]
        offset = [0.0, 0.0, 0.0]
        power = [1.0, 1.0, 1.0]
        sat = 1.0

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0].lower() == "slope" and len(parts) >= 4:
                    slope = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif parts[0].lower() == "offset" and len(parts) >= 4:
                    offset = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif parts[0].lower() == "power" and len(parts) >= 4:
                    power = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif parts[0].lower() == "sat" and len(parts) >= 2:
                    sat = float(parts[1])

        return cls(
            slope=(slope[0], slope[1], slope[2]),
            offset=(offset[0], offset[1], offset[2]),
            power=(power[0], power[1], power[2]),
            saturation=sat,
            name=os.path.basename(file_path),
        )


@dataclass
class CubeLut:
    """3D or 1D Cube LUT representation."""
    title: str = "Untitled"
    size_3d: int = 0
    size_1d: int = 0
    domain_min: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    domain_max: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    # 3D LUT array: shape (size, size, size, 3) in float32
    data_3d: Optional[np.ndarray] = None
    # 1D LUT array: shape (size, 3) in float32
    data_1d: Optional[np.ndarray] = None

    @classmethod
    def from_file(cls, file_path: str) -> CubeLut:
        """Parse standard Adobe / Iridas .cube or .3dl file."""
        lut = cls(title=os.path.basename(file_path))
        raw_numbers: list[float] = []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split()
                first = parts[0].upper()

                if first == "TITLE":
                    lut.title = line[5:].strip().strip('"')
                elif first == "LUT_3D_SIZE":
                    lut.size_3d = int(parts[1])
                elif first == "LUT_1D_SIZE":
                    lut.size_1d = int(parts[1])
                elif first == "DOMAIN_MIN":
                    lut.domain_min = (float(parts[1]), float(parts[2]), float(parts[3]))
                elif first == "DOMAIN_MAX":
                    lut.domain_max = (float(parts[1]), float(parts[2]), float(parts[3]))
                else:
                    try:
                        vals = [float(p) for p in parts]
                        raw_numbers.extend(vals)
                    except ValueError:
                        pass

        if lut.size_3d > 0 and len(raw_numbers) >= lut.size_3d ** 3 * 3:
            expected = lut.size_3d ** 3 * 3
            arr = np.array(raw_numbers[:expected], dtype=np.float32)
            # In .cube format: Red varies fastest, then Green, then Blue
            # Reshape into (B, G, R, 3)
            lut.data_3d = arr.reshape((lut.size_3d, lut.size_3d, lut.size_3d, 3))
        elif lut.size_1d > 0 and len(raw_numbers) >= lut.size_1d * 3:
            expected = lut.size_1d * 3
            arr = np.array(raw_numbers[:expected], dtype=np.float32)
            lut.data_1d = arr.reshape((lut.size_1d, 3))
            # Convert 1D LUT into equivalent 3D LUT for unified shader sampling
            sz = min(32, lut.size_1d)
            grid = np.linspace(0.0, 1.0, sz, dtype=np.float32)
            r_1d = np.interp(grid, np.linspace(0.0, 1.0, lut.size_1d), lut.data_1d[:, 0])
            g_1d = np.interp(grid, np.linspace(0.0, 1.0, lut.size_1d), lut.data_1d[:, 1])
            b_1d = np.interp(grid, np.linspace(0.0, 1.0, lut.size_1d), lut.data_1d[:, 2])

            lut_3d = np.zeros((sz, sz, sz, 3), dtype=np.float32)
            for b in range(sz):
                for g in range(sz):
                    for r in range(sz):
                        lut_3d[b, g, r] = [r_1d[r], g_1d[g], b_1d[b]]
            lut.size_3d = sz
            lut.data_3d = lut_3d

        return lut


@dataclass
class ColorGradeSettings:
    """Interactive Color Adjustments & Grade Parameters."""
    gain: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    gamma: float = 1.0
    saturation: float = 1.0
    contrast: float = 1.0
    hue: float = 0.0                  # Angle in degrees
    brightness: float = 0.0           # Display brightness trim
    invert_colors: bool = False
    show_out_of_range: bool = False   # Out-of-range false-color highlight
    active_lut: Optional[CubeLut] = None
    active_cdl: Optional[AscCdl] = None
    lut_enabled: bool = True
    cdl_enabled: bool = True

    def reset(self) -> None:
        """Reset all grading values to neutral defaults."""
        self.gain = (1.0, 1.0, 1.0)
        self.offset = (0.0, 0.0, 0.0)
        self.gamma = 1.0
        self.saturation = 1.0
        self.contrast = 1.0
        self.hue = 0.0
        self.brightness = 0.0
        self.invert_colors = False
        self.show_out_of_range = False
