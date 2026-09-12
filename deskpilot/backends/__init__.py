"""Desktop adapters. Imports are lazy so preview works without desktop access."""

import os
import sys


def create_backend(choice="auto"):
    if choice == "preview":
        from .base import PreviewBackend

        return PreviewBackend()
    if choice == "auto":
        if sys.platform == "win32":
            choice = "windows"
        else:
            choice = (
                "wayland"
                if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY")
                else "x11"
            )
    if choice == "windows":
        from .windows import WindowsBackend

        return WindowsBackend()
    if choice == "mousemux":
        from .mousemux import MouseMuxBackend

        return MouseMuxBackend()
    if choice == "wayland":
        from .portal import PortalBackend

        return PortalBackend()
    if choice == "x11":
        from .x11 import X11Backend

        return X11Backend()
    raise ValueError(f"Backend tidak dikenal: {choice}")
