import os
import sys


def test_gui_app_still_exposes_runtime_methods_after_merge():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Source"))

    from gui.app import FreeCellApp

    assert hasattr(FreeCellApp, "_update_victory_logic")
    assert hasattr(FreeCellApp, "_draw_lose_celebration")
    assert hasattr(FreeCellApp, "_draw_victory_celebration")
