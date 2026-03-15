from __future__ import annotations

import os


_SOURCE_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_SOURCE_DIR, ".."))

CARD_IMAGE_DIR = os.path.join(_PROJECT_ROOT, "Source", "assets", "images", "cards")
SOLUTION_DIR = os.path.join(_PROJECT_ROOT, "Source", "assets", "solution")
