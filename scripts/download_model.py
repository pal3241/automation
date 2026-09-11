"""Optional pre-download. Normally the first camera start downloads the model."""

from pathlib import Path

from deskpilot.camera import ensure_model

print(ensure_model(Path.home() / ".cache/deskpilot/hand_landmarker.task"))
