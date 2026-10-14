"""
Software Update Checker for OpenReview.
Supports querying GitHub Releases API and internal studio manifest URLs.
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Tuple

CURRENT_VERSION = "0.1.0"
GITHUB_RELEASES_URL = "https://api.github.com/repos/OpenReview/OpenReview/releases/latest"


@dataclass
class UpdateInfo:
    """Status details regarding software version and updates."""
    current_version: str
    latest_version: str
    is_update_available: bool
    release_title: str = ""
    release_notes: str = ""
    download_url: str = ""
    published_at: str = ""
    error_message: str = ""


def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Extract numeric components from a semantic version string (e.g. 'v0.2.1-beta' -> (0, 2, 1))."""
    nums = re.findall(r"\d+", v_str)
    return tuple(int(x) for x in nums) if nums else (0, 0, 0)


class SoftwareUpdater:
    """Checks for software updates across GitHub or Studio channels."""

    def __init__(self, current_version: str = CURRENT_VERSION):
        self.current_version = current_version

    def check_for_updates(
        self,
        channel: str = "github",
        custom_url: Optional[str] = None,
        timeout: float = 5.0,
    ) -> UpdateInfo:
        """
        Query the update endpoint and return UpdateInfo.
        If custom_url is provided, it takes precedence.
        """
        url = custom_url if custom_url else GITHUB_RELEASES_URL

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"OpenReview-Updater/{self.current_version} (Python/urllib)",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return UpdateInfo(
                current_version=self.current_version,
                latest_version=self.current_version,
                is_update_available=False,
                error_message=f"Network error checking for updates: {e}",
            )
        except Exception as e:
            return UpdateInfo(
                current_version=self.current_version,
                latest_version=self.current_version,
                is_update_available=False,
                error_message=f"Failed to parse update manifest: {e}",
            )

        # Parse release payload (GitHub API format or Studio manifest format)
        tag = data.get("tag_name", data.get("version", self.current_version))
        latest_ver = tag.lstrip("v")
        title = data.get("name", f"OpenReview {tag}")
        notes = data.get("body", data.get("description", "No release notes provided."))
        download_url = data.get("html_url", data.get("download_url", ""))

        # Check if assets contain an installer or direct link
        assets = data.get("assets", [])
        if assets and isinstance(assets, list):
            download_url = assets[0].get("browser_download_url", download_url)

        curr_tuple = parse_version_tuple(self.current_version)
        latest_tuple = parse_version_tuple(latest_ver)
        has_update = latest_tuple > curr_tuple

        return UpdateInfo(
            current_version=self.current_version,
            latest_version=latest_ver,
            is_update_available=has_update,
            release_title=title,
            release_notes=notes,
            download_url=download_url,
            published_at=data.get("published_at", ""),
        )
