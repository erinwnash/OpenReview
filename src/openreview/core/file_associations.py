"""
OS File Association Manager for OpenReview.
Handles Windows Registry registration and unregistration for .ovr session files
and contextual 'Open with OpenReview' shell verbs for VFX media formats.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, List

MEDIA_EXTENSIONS = [".exr", ".mov", ".mp4", ".dpx", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]


def get_openreview_executable_path() -> str:
    """Determine the executable or launcher script path for file association invocations."""
    if getattr(sys, "frozen", False):
        # Running as compiled PyInstaller executable
        return sys.executable
    # Running from Python source environment
    return sys.executable


def get_command_string() -> str:
    """Return the shell open command line string formatted with '%1' parameter."""
    exe = get_openreview_executable_path()
    if getattr(sys, "frozen", False):
        return f'"{exe}" "%1"'
    # In developer / source mode, run python -m openreview.app "%1"
    app_script = Path(__file__).resolve().parent.parent / "app.py"
    return f'"{exe}" "{app_script}" "%1"'


def get_icon_path() -> str:
    """Return the absolute path to openreview.ico if available."""
    icon_path = Path(__file__).resolve().parent.parent / "resources" / "icons" / "openreview.ico"
    if icon_path.is_file():
        return str(icon_path)
    if getattr(sys, "frozen", False):
        return f"{sys.executable},0"
    return ""


def register_file_associations() -> bool:
    """
    Register OpenReview as the default handler for .ovr (Session files)
    and add 'Open with OpenReview' contextual menu verbs for VFX media extensions
    in the current user's registry (HKCU\\Software\\Classes).
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg
        import ctypes
    except ImportError:
        return False

    cmd_str = get_command_string()
    ico_path = get_icon_path()

    try:
        # 1. Register .ovr extension -> OpenReview.Session ProgId
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.ovr") as k_ext:
            winreg.SetValueEx(k_ext, "", 0, winreg.REG_SZ, "OpenReview.Session")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\OpenReview.Session") as k_prog:
            winreg.SetValueEx(k_prog, "", 0, winreg.REG_SZ, "OpenReview Session File")

        if ico_path:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\OpenReview.Session\DefaultIcon") as k_icon:
                winreg.SetValueEx(k_icon, "", 0, winreg.REG_SZ, f'"{ico_path}",0' if not ico_path.endswith(",0") else ico_path)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\OpenReview.Session\shell\open\command") as k_cmd:
            winreg.SetValueEx(k_cmd, "", 0, winreg.REG_SZ, cmd_str)

        # 2. Register 'Open with OpenReview' for media extensions under SystemFileAssociations
        for ext in MEDIA_EXTENSIONS:
            subpath = rf"Software\Classes\SystemFileAssociations\{ext}\shell\OpenWithOpenReview"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subpath) as k_verb:
                winreg.SetValueEx(k_verb, "", 0, winreg.REG_SZ, "Open with OpenReview")
                if ico_path:
                    winreg.SetValueEx(k_verb, "Icon", 0, winreg.REG_SZ, ico_path)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{subpath}\command") as k_verb_cmd:
                winreg.SetValueEx(k_verb_cmd, "", 0, winreg.REG_SZ, cmd_str)

        # 3. Notify Windows Shell of association change
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)  # SHCNE_ASSOCCHANGED
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Failed to register file associations: {e}")
        return False


def unregister_file_associations() -> bool:
    """Remove OpenReview file associations from HKCU\\Software\\Classes."""
    if sys.platform != "win32":
        return False

    try:
        import winreg
        import ctypes
    except ImportError:
        return False

    def _delete_key_tree(root, subkey):
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as k:
                while True:
                    try:
                        child = winreg.EnumKey(k, 0)
                        _delete_key_tree(root, f"{subkey}\\{child}")
                    except OSError:
                        break
            winreg.DeleteKey(root, subkey)
        except OSError:
            pass

    try:
        _delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\.ovr")
        _delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\OpenReview.Session")

        for ext in MEDIA_EXTENSIONS:
            _delete_key_tree(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Classes\SystemFileAssociations\{ext}\shell\OpenWithOpenReview",
            )

        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Failed to unregister file associations: {e}")
        return False


def is_file_association_registered() -> bool:
    """Check if .ovr association points to OpenReview.Session in HKCU."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.ovr") as k:
            val, _ = winreg.QueryValueEx(k, "")
            return val == "OpenReview.Session"
    except Exception:
        return False
