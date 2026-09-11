"""Camera + inference worker. The GUI pulls one latest frame, avoiding signal backlog."""

import threading
import time
import urllib.request
from pathlib import Path

from .gestures import Hand
from .tracking import HandTracker

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def ensure_model(path):
    path = Path(path).expanduser()
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=30) as response, temporary.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 256):
                total += len(chunk)
                if total > 32 * 1024 * 1024:
                    raise RuntimeError("Ukuran model melebihi batas 32 MB")
                output.write(chunk)
        if total < 1024:
            raise RuntimeError("Unduhan model tidak lengkap")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


class CameraWorker(threading.Thread):
    def __init__(self, index, model_path, consumer, swap=False):
        super().__init__(daemon=True, name="camera-tracking")
        self.index, self.model_path, self.consumer = index, model_path, consumer
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.status = "Menyiapkan model tangan…"
        self.error = ""
        self.tracker = HandTracker(swap=swap)

    def stop(self):
        self.stop_event.set()
        self.consumer([])

    def take(self):
        with self.lock:
            result, self.latest = self.latest, None
        return result

    def run(self):
        capture = None
        try:
            import cv2
            import mediapipe as mp

            model = ensure_model(self.model_path)
            if self.stop_event.is_set():
                return
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.7,
                min_hand_presence_confidence=0.7,
                min_tracking_confidence=0.7,
            )
            capture = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self.index)
            if not capture.isOpened():
                raise RuntimeError(f"Kamera {self.index} tidak bisa dibuka; cek izin atau aplikasi lain")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_FPS, 30)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            last_timestamp, last_time, fps = -1, time.monotonic(), 0.0
            with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
                while not self.stop_event.is_set():
                    success, frame = capture.read()
                    if not success:
                        raise RuntimeError("Kamera berhenti mengirim gambar")
                    frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                    timestamp = max(last_timestamp + 1, int(time.monotonic() * 1000))
                    last_timestamp = timestamp
                    result = detector.detect_for_video(
                        mp.Image(image_format=mp.ImageFormat.SRGB, data=frame), timestamp
                    )
                    hands = [
                        Hand(
                            categories[0].category_name,
                            tuple((p.x, p.y) for p in points),
                            categories[0].score,
                            frame.shape[1] / frame.shape[0],
                        )
                        for points, categories in zip(result.hand_landmarks, result.handedness)
                    ]
                    now = time.monotonic()
                    hands = self.tracker.update(hands, now)
                    fps = fps * 0.8 + 0.2 / max(0.001, now - last_time)
                    last_time = now
                    self.consumer(hands)
                    with self.lock:
                        self.latest = (frame, hands, fps, now)
                    self.status = "Kamera aktif • diproses lokal"
        except Exception as exc:
            self.error = str(exc)
            self.status = "Kamera gagal: " + str(exc)
        finally:
            self.consumer([])
            if capture:
                capture.release()
