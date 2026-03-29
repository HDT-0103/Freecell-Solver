"""Application entrypoint.

Single responsibility: bootstrap and run FreeCellApp.
"""
from __future__ import annotations

import argparse
import os
import sys


SOURCE_DIR = os.path.join(os.path.dirname(__file__), "Source")
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from Source.utils.benchmark_runner import run_benchmark_mode


def _ensure_source_on_path() -> None:
    if SOURCE_DIR not in sys.path:
        sys.path.insert(0, SOURCE_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["gui", "benchmark"], default="gui")
    return parser.parse_args()


def run_gui_mode() -> None:
    from Source.gui.app import FreeCellApp

    FreeCellApp().run()


def main() -> None:
    _ensure_source_on_path()
    args = parse_args()

    if args.mode == "benchmark":
        run_benchmark_mode()
        return

    run_gui_mode()

if __name__ == "__main__":
    main()
