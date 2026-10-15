"""
Utility script to generate all application and favicon icons from master openreview.png.
Generates multi-resolution .ico files (16, 24, 32, 48, 64, 128, 256) and companion PNGs,
synchronizing them across src/openreview/resources/icons/, resources/, and assets/.
"""

import shutil
from pathlib import Path
from PIL import Image


def main():
    root = Path(__file__).resolve().parent.parent
    master_png_path = root / "src" / "openreview" / "resources" / "icons" / "openreview.png"

    if not master_png_path.exists():
        raise FileNotFoundError(f"Master PNG not found at: {master_png_path}")

    print(f"Loading master PNG from {master_png_path}...")
    master = Image.open(master_png_path).convert("RGBA")

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # Target folders
    target_dirs = [
        root / "src" / "openreview" / "resources" / "icons",
        root / "resources",
        root / "assets",
    ]

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nUpdating {target_dir}...")

        # 1. Master openreview.png and favicon.png
        master.save(target_dir / "openreview.png", format="PNG")
        master.save(target_dir / "favicon.png", format="PNG")

        # 2. Favicon downscaled PNGs
        fav16 = master.resize((16, 16), Image.Resampling.LANCZOS)
        fav16.save(target_dir / "favicon-16x16.png", format="PNG")

        fav32 = master.resize((32, 32), Image.Resampling.LANCZOS)
        fav32.save(target_dir / "favicon-32x32.png", format="PNG")

        # 3. Multi-resolution ICOs
        for ico_name in ["openreview.ico", "app_icon.ico", "favicon.ico"]:
            ico_path = target_dir / ico_name
            master.save(ico_path, format="ICO", sizes=sizes)
            print(f"  Saved {ico_name} ({ico_path.stat().st_size} bytes)")

    print("\nIcon generation completed successfully across all target directories.")


if __name__ == "__main__":
    main()
