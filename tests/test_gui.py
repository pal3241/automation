import argparse
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication
from test_gestures import hand

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


def test_gui_shows_two_live_viewpoints_without_double_counting(monkeypatch, tmp_path):
    class Worker:
        def __init__(self, index, model, consumer, swap):
            self.index, self.swap, self.running = index, swap, False
            self.stop_event = self
            self.status = "aktif"
            self.packet = (np.zeros((40, 60, 3), dtype=np.uint8), [hand()], 30, time.monotonic())

        def is_set(self):
            return not self.running

        def is_alive(self):
            return self.running

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

        def take(self):
            return self.packet

    monkeypatch.setattr("deskpilot.app.CameraWorker", Worker)
    app = QApplication.instance() or QApplication([])
    window = Window(argparse.Namespace(preview=True, model=str(tmp_path / "model.task")))
    window.camera_ids.setText("0,1")
    window.camera_flip.setText("1")
    window.toggle_camera()
    window.tick()
    app.processEvents()
    assert len(window.views) == 2
    assert window.cameras[0].swap != window.cameras[1].swap
    assert window.views[0].frame is not None and window.views[1].frame is not None
    assert window.views[0].buttons_enabled and not window.views[1].buttons_enabled
    assert "kamera 0" in window.details.text() and "kamera 1" not in window.details.text()
    window.close()
