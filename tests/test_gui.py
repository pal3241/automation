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
