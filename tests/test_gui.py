import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from deskpilot.app import STYLE, Window


def test_preview_gui_renders_and_starts_paused(tmp_path):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    window = Window(argparse.Namespace(preview=True, model=str(tmp_path / "model.task")))
    window.show()
    app.processEvents()
    window.tick()
    assert not window.arm_button.isEnabled()
    assert window.backend_choice.currentData() == "preview"
    assert not window.grab().isNull()
    window.close()
    app.processEvents()


def test_cursor_map_and_overlay_render_two_pointers():
    from deskpilot.cursors import CursorMap, DesktopCursors

    app = QApplication.instance() or QApplication([])
    for cls in (CursorMap, DesktopCursors):
        widget = cls()
        widget.resize(320, 180)
        widget.cursors = {"Right": (0.3, 0.4), "Left": (0.7, 0.6)}
        widget.owner = "Right"
        widget.show()
        app.processEvents()
        assert not widget.grab().isNull()
        widget.close()
