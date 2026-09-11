"""A bounded, latest-frame mailbox keeps slow OS input from accumulating actions."""

import threading
import time

from .backends import create_backend
from .gestures import GestureEngine, Settings


class Controller(threading.Thread):
    def __init__(self, backend_choice="auto", modifier="Super_L", settings=None, resize_button=3):
        super().__init__(daemon=True, name="desktop-executor")
        self.choice, self.modifier = backend_choice, modifier
        self.settings = settings or Settings()
        self.resize_button = resize_button
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.enabled = False
        self.pending = None
        self.generation = 0
        self.status = "Menghubungkan desktop…"
        self.ready = False
        self.mode = "idle"
        self.error = ""
        self.last_frame = 0.0

    def arm(self, enabled):
        with self.lock:
            self.enabled = bool(enabled and self.ready)
            self.generation += 1
            self.pending = None
        self.wake.set()

    def submit(self, hands):
        with self.lock:
            self.last_frame = time.monotonic()
            if self.enabled:
                self.pending = (self.generation, hands, self.last_frame)
        self.wake.set()

    def stop(self):
        self.arm(False)
        self.stopping.set()
        self.wake.set()

    def run(self):
        backend = None
        engine = GestureEngine(self.settings)
        seen_generation = -1
        try:
            backend = create_backend(self.choice)
            backend.modifier = self.modifier
            backend.resize_button = self.resize_button
            backend.cancel_event = self.stopping
            backend.start()
            self.ready = True
            self.status = backend.name
            while not self.stopping.is_set():
                self.wake.wait(0.02)
                self.wake.clear()
                if hasattr(backend, "pump"):
                    backend.pump()
                if not backend.ready:
                    raise RuntimeError(backend.error or "Koneksi desktop terputus")
                with self.lock:
                    generation, enabled = self.generation, self.enabled
                    packet, self.pending = self.pending, None
                if generation != seen_generation or not enabled or time.monotonic() - self.last_frame > 0.30:
                    for action in engine.reset():
                        backend.execute(action)
                    self.mode = "idle"
                    seen_generation = generation
                if not enabled or packet is None or time.monotonic() - packet[2] > 0.20:
                    continue
                if packet[0] != generation:
                    continue
                actions = engine.update(packet[1])
                self.mode = engine.mode
                for action in actions:
                    # Check cancellation before every side effect; never hold UI lock during D-Bus IO.
                    with self.lock:
                        cancelled = not self.enabled or self.generation != generation
                    if cancelled:
                        backend.release()
                        break
                    backend.execute(action)
        except Exception as exc:
            self.error = str(exc)
            self.status = "Kontrol tidak tersedia: " + str(exc)
        finally:
            self.ready = self.enabled = False
            if backend:
                try:
                    backend.close()
                except Exception as exc:
                    self.error = self.error or str(exc)
