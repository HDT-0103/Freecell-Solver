"""Application entrypoint.

Single responsibility: bootstrap and run FreeCellApp.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Source"))

from gui.app import FreeCellApp


def main() -> None:
    FreeCellApp().run()


if __name__ == "__main__":
    main()
