"""Selection between camera viewpoints, without pretending their pixels are calibrated 3D."""

from dataclasses import replace


def parse_camera_ids(value, limit=8):
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(not part.isdecimal() for part in parts):
        raise ValueError("Isi ID kamera seperti 0,1,2 (angka dipisahkan koma)")
    ids = tuple(int(part) for part in parts)
    if len(ids) > limit or any(i > 20 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"Gunakan 1–{limit} ID kamera unik antara 0 sampai 20")
    return ids


class MultiCameraFusion:
    """One hand per anatomical side, sticky source, safe rearm on source changes."""

    def __init__(self, ids):
        self.ids = tuple(ids)
        self.source = {}

    def reset(self):
        self.source.clear()

    def select(self, detections):
        # Each source already tracks identities on its own mirrored image.
        result = []
        shared_camera = next(
            (
                i for i in self.ids
                if {hand.side for hand in detections.get(i, ())} >= {"Right", "Left"}
            ),
            None,
        )
        for side in ("Right", "Left"):
            options = {
                camera_id: hand
                for camera_id, hands in detections.items()
                for hand in hands
                if hand.side == side and camera_id in self.ids
            }
            if not options:
                self.source.pop(side, None)
                continue
            previous = self.source.get(side)
            camera_id = (
                shared_camera
                if shared_camera is not None and shared_camera in options
                else previous if previous in options else next(i for i in self.ids if i in options)
            )
            self.source[side] = camera_id
            result.append(
                replace(
                    options[camera_id],
                    camera_id=camera_id,
                    track_id=(camera_id, options[camera_id].track_id),
                )
            )
        return result
