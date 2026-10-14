#!/usr/bin/env python3
"""
OpenReview Launcher Script.
Run this script to launch OpenReview in development mode:
    python run.py
"""
import sys
from pathlib import Path

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from openreview.app import main

if __name__ == "__main__":
    sys.exit(main())
