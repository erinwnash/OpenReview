"""
Package Manifest Parser and Data Model.
Validates manifest.json / package.json metadata for OpenReview extensions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class PackageManifest:
    """Represents the metadata of an OpenReview extension package."""
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    entrypoint: str = "plugin.py"
    min_openreview_version: str = "0.1.0"
    enabled: bool = True
    menu_items: List[Dict[str, str]] = field(default_factory=list)
    package_path: str = ""
    is_builtin: bool = False
    id: str = ""
    category: str = "General"
    tags: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = self.name

    @classmethod
    def from_file(cls, manifest_path: Path, is_builtin: bool = False) -> PackageManifest:
        """Load manifest from json file."""
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data, package_dir=manifest_path.parent, is_builtin=is_builtin)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], package_dir: Optional[Path] = None, is_builtin: bool = False) -> PackageManifest:
        pkg_dir = Path(package_dir) if package_dir else Path(".")
        name = str(data.get("id", data.get("name", pkg_dir.name))).strip()
        if not name:
            name = pkg_dir.name

        display_name = str(data.get("name", name)).strip()

        return cls(
            name=display_name,
            id=str(data.get("id", name)),
            version=str(data.get("version", "1.0.0")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            entrypoint=str(data.get("entrypoint", data.get("entry_point", "plugin.py"))),
            min_openreview_version=str(data.get("min_openreview_version", "0.1.0")),
            enabled=bool(data.get("enabled", True)),
            menu_items=list(data.get("menu_items", data.get("menus", []))),
            package_path=str(pkg_dir.resolve()),
            is_builtin=is_builtin,
            category=str(data.get("category", "General")),
            tags=list(data.get("tags", [])),
            hooks=list(data.get("hooks", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "min_openreview_version": self.min_openreview_version,
            "enabled": self.enabled,
            "menu_items": self.menu_items,
            "category": self.category,
            "tags": self.tags,
            "hooks": self.hooks,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> PackageManifest:
        return cls.from_dict(json.loads(json_str))

