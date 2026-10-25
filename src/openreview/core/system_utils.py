"""
System & OS utility functions for OpenReview.
Provides rock-solid cross-platform file manager reveal and system integration.
"""
from __future__ import annotations

import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


def reveal_in_os_file_manager(target_path: str) -> bool:
    """
    Reveal a file or directory in the native OS file explorer (Windows Explorer, Finder, or Linux file manager).
    On Windows, uses SHOpenFolderAndSelectItems via Shell32 to avoid Windows argument quoting bugs,
    with fallback to explorer.exe /select, and directory opening.
    """
    if not target_path:
        return False

    abs_path = os.path.abspath(os.path.normpath(str(target_path)))

    try:
        if sys.platform == "win32":
            # 1. Native Windows Shell API: SHOpenFolderAndSelectItems
            try:
                import ctypes
                from ctypes import wintypes

                if os.path.exists(abs_path):
                    if os.path.isfile(abs_path):
                        il_create = ctypes.windll.shell32.ILCreateFromPathW
                        il_create.restype = ctypes.c_void_p
                        il_create.argtypes = [wintypes.LPCWSTR]

                        il_free = ctypes.windll.shell32.ILFree
                        il_free.argtypes = [ctypes.c_void_p]

                        pidl = il_create(abs_path)
                        if pidl:
                            try:
                                sh_open = ctypes.windll.shell32.SHOpenFolderAndSelectItems
                                sh_open.restype = ctypes.HRESULT
                                sh_open.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
                                hr = sh_open(pidl, 0, None, 0)
                                if hr == 0:
                                    return True
                            finally:
                                il_free(pidl)
                    else:
                        os.startfile(abs_path)
                        return True
            except Exception as e:
                logger.debug("SHOpenFolderAndSelectItems exception: %s", e)

            # 2. Windows Fallback: explorer.exe /select,"<path>"
            if os.path.isfile(abs_path):
                # Using /select,"<path>" as a raw command string prevents python list arg quoting failure
                subprocess.Popen(f'explorer.exe /select,"{abs_path}"')
                return True
            elif os.path.isdir(abs_path):
                os.startfile(abs_path)
                return True
            else:
                # Target path does not exist; locate closest existing parent directory
                parent = os.path.dirname(abs_path)
                while parent and not os.path.exists(parent):
                    new_parent = os.path.dirname(parent)
                    if new_parent == parent:
                        break
                    parent = new_parent
                if parent and os.path.exists(parent):
                    os.startfile(parent)
                    return True
                return False

        elif sys.platform == "darwin":
            if os.path.exists(abs_path):
                subprocess.Popen(["open", "-R", abs_path])
            else:
                parent = os.path.dirname(abs_path)
                if os.path.exists(parent):
                    subprocess.Popen(["open", parent])
            return True

        else:
            # Linux / Unix
            parent_dir = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
            if os.path.exists(parent_dir):
                subprocess.Popen(["xdg-open", parent_dir])
                return True
            return False

    except Exception as e:
        logger.warning("Failed to reveal '%s' in OS file manager: %s", target_path, e)
        return False
