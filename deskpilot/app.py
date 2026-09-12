"""Native Qt camera console. Run `python -m deskpilot --preview` to explore safely."""

import argparse
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraWorker
from .controller import Controller
from .cursors import CursorMap, DesktopCursors, draw_cursors
from .gestures import CONNECTIONS, FINGERS, Dwell, Settings

STYLE = """
QWidget { background: #10151f; color: #e4edf8; font-family: 'DejaVu Sans'; font-size: 13px; }
QMainWindow { background: #10151f; }
QLabel#title { font-size: 24px; font-weight: bold; }
QScrollArea { border: none; }
QGroupBox { border: 1px solid #2a374b; border-radius: 10px; margin-top: 14px; padding: 14px 10px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #8ea9c7; }
QPushButton { background: #24334a; border: 1px solid #374e6e; padding: 10px; border-radius: 7px; }
QPushButton:hover { background: #344b6b; }
QPushButton:disabled { color: #65758b; background: #18212e; }
QPushButton#start { background: #176951; border-color: #35bd95; }
QPushButton#stop { background: #782b3b; border-color: #da5970; font-weight: bold; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #1c2738; border: 1px solid #3a4c64; padding: 6px; }
QLabel#muted { color: #8fa3bb; }
"""


class CameraView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(560, 420)
        self.frame = None
        self.hands = []
        self.fps = 0
        self.mode = "idle"
        self.active = False
        self.labels = True
        self.dwell_target = None
        self.progress = 0.0
        self.cursors = {}
        self.owner = None

    @staticmethod
    def buttons():
        return {"toggle": QRectF(0.04, 0.05, 0.23, 0.12), "stop": QRectF(0.74, 0.05, 0.22, 0.12)}

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0a1019"))
        ratio = self.frame.width() / self.frame.height() if self.frame else 4 / 3
        width = min(self.width(), self.height() * ratio)
        height = width / ratio
        area = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
        if self.frame:
            p.drawImage(area, self.frame)
        else:
            p.setPen(QColor("#a3b5cc"))
            p.setFont(QFont("DejaVu Sans", 14))
            p.drawText(
                area, Qt.AlignCenter, "KAMERA → TANGAN → TINDAKAN\n\nTekan ‘Mulai kamera’ untuk memulai"
            )

        def point(xy):
            return QPointF(area.x() + xy[0] * width, area.y() + xy[1] * height)

        for hand in self.hands:
            color = QColor("#60ebca" if hand.side == "Right" else "#d5a0ff")
            p.setPen(QPen(color, 2))
            for a, b in CONNECTIONS:
                p.drawLine(point(hand.points[a]), point(hand.points[b]))
            for i, xy in enumerate(hand.points):
                p.setBrush(color if i in FINGERS else QColor("#f4f7fc"))
                p.drawEllipse(point(xy), 5 if i in FINGERS else 3, 5 if i in FINGERS else 3)
                if self.labels and i in FINGERS:
                    p.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
                    p.drawText(point(xy) + QPointF(8, -8), FINGERS[i])
            p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
            p.drawText(
                point(hand.points[0]) + QPointF(5, 25),
                f"{'KANAN' if hand.side == 'Right' else 'KIRI'} · {hand.confidence:.0%}",
            )
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(color, 3))
            p.drawEllipse(point(hand.points[8]), 13, 13)
        p.save()
        p.translate(area.x(), area.y())
        draw_cursors(p, self.cursors, self.owner, width, height)
        p.restore()
        for name, normalized in self.buttons().items():
            r = QRectF(
                area.x() + normalized.x() * width,
                area.y() + normalized.y() * height,
                normalized.width() * width,
                normalized.height() * height,
            )
            p.setPen(QPen(QColor("#ff7288" if name == "stop" else "#64f0c6"), 2))
            p.setBrush(QColor(74, 20, 35, 220) if name == "stop" else QColor(12, 52, 48, 225))
            p.drawRoundedRect(r, 9, 9)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
            p.drawText(
                r, Qt.AlignCenter, "STOP" if name == "stop" else ("JEDA" if self.active else "AKTIFKAN")
            )
            if self.dwell_target == name:
                p.fillRect(QRectF(r.x(), r.bottom() - 5, r.width() * self.progress, 5), QColor("#ffffff"))
        p.fillRect(QRectF(area.x(), area.bottom() - 35, width, 35), QColor(8, 15, 25, 220))
        p.setPen(QColor("#c4d4e8"))
        p.setFont(QFont("DejaVu Sans", 10))
        p.drawText(
            QRectF(area.x() + 12, area.bottom() - 35, width - 24, 35),
            Qt.AlignVCenter,
            f"{self.fps:.0f} FPS  •  {len(self.hands)} tangan  •  {self.mode.upper()}  •  Kamera dicerminkan",
        )
        p.end()


class Window(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.camera = None
        self.controller = None
        self.last_seen = 0
        self.dwell = Dwell()
        self.button_hand = None
        self.overlay = DesktopCursors()
        self.preferences = QSettings("DeskPilot", "Automation")
        self.setWindowTitle("DeskPilot — Camera Control / Tahap 1")
        self.resize(1160, 800)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        title = QLabel("DESKPILOT  /  CAMERA CONTROL")
        title.setObjectName("title")
        outer.addWidget(title)
        subtitle = QLabel(
            "Pegang kursor dengan cubitan. Lepaskan untuk berhenti. Semua video diproses lokal."
        )
        subtitle.setObjectName("muted")
        outer.addWidget(subtitle)
        controls = QHBoxLayout()
        outer.addLayout(controls)
        row = QHBoxLayout()
        outer.addLayout(row, 1)
        self.view = CameraView()
        row.addWidget(self.view, 1)
        sidebar = QWidget()
        sidebar.setMinimumWidth(335)
        side = QVBoxLayout(sidebar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(365)
        scroll.setWidget(sidebar)
        row.addWidget(scroll)
        config = QGroupBox("PERANGKAT & KONTROL")
        form = QFormLayout(config)
        self.camera_id = QSpinBox()
        self.camera_id.setRange(0, 20)
        self.camera_id.setValue(int(self.preferences.value("camera", 0)))
        form.addRow("Kamera", self.camera_id)
        self.backend_choice = QComboBox()
        backends = (
            (
                ("Otomatis (Windows)", "auto"),
                ("Windows / SendInput (satu pointer)", "windows"),
                ("MouseMux V2 (dua pointer independen)", "mousemux"),
            )
            if sys.platform == "win32"
            else (("Otomatis (Linux)", "auto"), ("X11 / XTest", "x11"), ("Wayland / Portal", "wayland"))
        )
        for label, value in (*backends, ("Preview saja", "preview")):
            self.backend_choice.addItem(label, value)
        if args.preview:
            self.backend_choice.setCurrentIndex(self.backend_choice.findData("preview"))
        elif sys.platform == "win32":
            self.backend_choice.setCurrentIndex(self.backend_choice.findData("mousemux"))
        form.addRow("Backend", self.backend_choice)
        self.hand = QComboBox()
        self.hand.addItem("Kanan", "Right")
        self.hand.addItem("Kiri", "Left")
        self.hand.setCurrentIndex(int(self.preferences.value("hand", 0)))
        form.addRow("Prioritas bersamaan", self.hand)
        self.swap_hands = QCheckBox("Tukar label kiri/kanan kamera")
        # Versioned preference: earlier default was reversed on the user's mirrored webcam.
        self.swap_hands.setChecked(self.preferences.value("swap_v3", True, type=bool))
        form.addRow(self.swap_hands)
        self.modifier = QComboBox()
        self.modifier.addItem("Super", "Super_L")
        self.modifier.addItem("Alt", "Alt_L")
        form.addRow("Modifier jendela", self.modifier)
        self.resize_mouse = QComboBox()
        self.resize_mouse.addItem("Kanan (KDE)", 3)
        self.resize_mouse.addItem("Tengah (GNOME)", 2)
        if "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
            self.resize_mouse.setCurrentIndex(1)
        form.addRow("Mouse resize", self.resize_mouse)
        self.gain = QDoubleSpinBox()
        self.gain.setRange(0.3, 3.0)
        self.gain.setSingleStep(0.1)
        self.gain.setValue(float(self.preferences.value("gain", 1.5)))
        form.addRow("Sensitivitas", self.gain)
        self.smoothness = QDoubleSpinBox()
        self.smoothness.setRange(0.5, 5.0)
        self.smoothness.setSingleStep(0.25)
        self.smoothness.setValue(float(self.preferences.value("cutoff", 1.5)))
        self.smoothness.setToolTip("Lebih rendah = lebih halus; lebih tinggi = lebih responsif")
        form.addRow("Respons gerakan", self.smoothness)
        self.pinky = QComboBox()
        self.pinky.addItem("Pindah jendela", "window")
        self.pinky.addItem("Resize jendela", "resize")
        form.addRow("Cubit kelingking", self.pinky)
        self.zoom_mode = QCheckBox("Mode zoom dua tangan")
        form.addRow(self.zoom_mode)
        self.backend_choice.currentIndexChanged.connect(self.update_backend_options)
        self.update_backend_options()
        self.overlay_toggle = QCheckBox("Kursor desktop tambahan (X11 / Windows)")
        self.overlay_toggle.setChecked(True)
        form.addRow(self.overlay_toggle)
        self.show_labels = QCheckBox("Tampilkan nama jari")
        self.show_labels.setChecked(True)
        form.addRow(self.show_labels)
        side.addWidget(config)
        self.connect_button = QPushButton("Hubungkan desktop")
        self.connect_button.clicked.connect(self.connect_desktop)
        controls.addWidget(self.connect_button)
        self.camera_button = QPushButton("Mulai kamera")
        self.camera_button.clicked.connect(self.toggle_camera)
        controls.addWidget(self.camera_button)
        self.arm_button = QPushButton("Aktifkan kontrol")
        self.arm_button.setObjectName("start")
        self.arm_button.clicked.connect(self.toggle_arm)
        controls.addWidget(self.arm_button)
        stop = QPushButton("STOP  ·  Esc / Space saat app aktif")
        stop.setObjectName("stop")
        stop.clicked.connect(self.pause)
        controls.addWidget(stop)
        cursor_group = QGroupBox("DUA KURSOR • POSISI LAYAR")
        cursor_layout = QVBoxLayout(cursor_group)
        self.cursor_map = CursorMap()
        cursor_layout.addWidget(self.cursor_map)
        caption = QLabel(
            "R hijau • L ungu. Satu tangan menguasai mouse\nsampai gestur dilepas. Posisi lainnya tetap disimpan."
        )
        caption.setWordWrap(True)
        cursor_layout.addWidget(caption)
        side.addWidget(cursor_group)
        guide = QGroupBox("GESTUR")
        layout = QVBoxLayout(guide)
        label = QLabel(
            "Ibu jari + telunjuk → bawa kursor\n"
            "Ibu jari + tengah → klik kiri saat dilepas\n"
            "Tambah telunjuk saat ditahan → drag\n"
            "Ibu jari + manis → klik kanan\n"
            "Ibu jari + kelingking → aksi pilihan\n"
            "Dua cubitan → dua kursor / mode zoom\n\n"
            "Lepaskan semua cubitan antar gestur.\n"
            "Arahkan telunjuk ke tombol kamera\n"
            "selama 0,9 detik untuk menekannya.\n\n"
            "Linux: pindah/resize memakai shortcut WM.\n"
            "Zoom berlaku pada app yang mendukung\nCtrl + scroll."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        side.addWidget(guide)
        side.addStretch()
        self.details = QLabel("Tangan belum terdeteksi")
        self.details.setWordWrap(True)
        outer.addWidget(self.details)
        self.status = QLabel("Mulai kamera, hubungkan desktop, lalu aktifkan kontrol.")
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        outer.addWidget(self.status)
        self.shortcuts = [QShortcut(QKeySequence(key), self) for key in ("Escape", "Space")]
        for shortcut in self.shortcuts:
            shortcut.activated.connect(self.pause)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def connect_desktop(self):
        if self.controller and self.controller.is_alive():
            self.pause()
            self.controller.stop()
            return
        settings = Settings(
            dominant=self.hand.currentData(),
            gain=self.gain.value(),
            min_cutoff=self.smoothness.value(),
            two_hand_zoom=self.zoom_mode.isChecked(),
            pinky_action=self.pinky.currentData(),
            independent=self.backend_choice.currentData() == "mousemux",
        )
        self.controller = Controller(
            self.backend_choice.currentData(),
            self.modifier.currentData(),
            settings,
            resize_button=self.resize_mouse.currentData(),
        )
        self.controller.start()
        self.dwell = Dwell()
        self.overlay.hide()

    def update_backend_options(self):
        independent = self.backend_choice.currentData() == "mousemux"
        self.zoom_mode.setEnabled(not independent)
        self.zoom_mode.setToolTip(
            "MouseMux V2 SDK tidak menyediakan jalur scroll per pointer; gunakan mode satu pointer untuk zoom."
            if independent else "Dua cubitan telunjuk melakukan Ctrl+scroll di aplikasi yang mendukung."
        )

    def toggle_camera(self):
        if self.camera and self.camera.is_alive():
            self.pause()
            self.camera.stop()
        else:
            self.camera = CameraWorker(
                self.camera_id.value(), self.args.model, self.on_hands, swap=self.swap_hands.isChecked()
            )
            self.camera.start()

    def on_hands(self, hands):
        if self.controller:
            # GUI owns button hit testing. The controller gets input only after that arbitration.
            if not hands:
                self.controller.submit([])

    def toggle_arm(self):
        if not self.controller or not self.controller.ready:
            return
        enabled = not self.controller.enabled
        if enabled and (
            not self.camera or not self.camera.is_alive() or time.monotonic() - self.last_seen > 0.3
        ):
            return
        self.controller.arm(enabled)

    def pause(self):
        if self.controller:
            self.controller.arm(False)

    def tick(self):
        now = time.monotonic()
        packet = self.camera.take() if self.camera else None
        if packet and now - packet[3] <= 0.20:
            frame, hands, fps, timestamp = packet
            self.last_seen = timestamp
            h, w, _ = frame.shape
            self.view.frame = QImage(frame.data, w, h, frame.strides[0], QImage.Format_RGB888).copy()
            self.view.hands, self.view.fps = hands, fps
            target = None
            button_hand = None
            for candidate in sorted(hands, key=lambda h: h.side != self.hand.currentData()):
                if candidate.confidence < 0.65:
                    continue
                if all(candidate.ratio(i) >= 0.46 for i in (8, 12, 16, 20)):
                    tip = QPointF(*candidate.points[8])
                    target = next(
                        (name for name, rect in self.view.buttons().items() if rect.contains(tip)), None
                    )
                    if target:
                        button_hand = candidate.track_id, candidate.side
                        break
            if button_hand != self.button_hand:
                self.dwell = Dwell()
                self.button_hand = button_hand
            fired, progress = self.dwell.update(target, now, 0.9)
            self.view.dwell_target, self.view.progress = target, progress
            if fired:
                self.pause() if target == "stop" else self.toggle_arm()
            if self.controller:
                self.controller.submit([] if target else hands)
            descriptions = [
                f"{'Kanan' if h.side == 'Right' else 'Kiri'} {h.confidence:.0%}: "
                + (", ".join(h.extended()) or "jari menekuk")
                for h in hands
            ]
            self.details.setText("   |   ".join(descriptions) or "Tangan belum terdeteksi — input dilepas")
        if now - self.last_seen > 0.3:
            self.view.hands = []
            self.view.fps = 0
            self.dwell.update(None, now, 0.9)
            self.view.dwell_target = None
            if self.controller:
                self.controller.submit([])
        controller_alive = bool(self.controller and self.controller.is_alive())
        ready = bool(self.controller and self.controller.ready)
        active = bool(self.controller and self.controller.enabled)
        camera_alive = bool(self.camera and self.camera.is_alive() and not self.camera.stop_event.is_set())
        self.view.active = active
        self.view.mode = self.controller.mode if active else "jeda"
        self.view.labels = self.show_labels.isChecked()
        self.arm_button.setEnabled(ready and camera_alive and now - self.last_seen < 0.3)
        self.arm_button.setText("Jeda kontrol" if active else "Aktifkan kontrol")
        self.connect_button.setText(
            "Putuskan desktop"
            if ready
            else "Batalkan koneksi desktop"
            if controller_alive
            else "Hubungkan desktop"
        )
        self.connect_button.setEnabled(True)
        self.camera_button.setText("Hentikan kamera" if camera_alive else "Mulai kamera")
        for widget in (
            self.hand,
            self.gain,
            self.modifier,
            self.resize_mouse,
            self.backend_choice,
            self.smoothness,
            self.pinky,
            self.zoom_mode,
        ):
            widget.setEnabled(not controller_alive)
        if self.backend_choice.currentData() == "mousemux":
            self.zoom_mode.setEnabled(False)
        self.camera_id.setEnabled(not camera_alive)
        self.swap_hands.setEnabled(not camera_alive)
        cursors = dict(self.controller.cursors) if self.controller else {}
        owner = self.controller.owner if active else None
        self.cursor_map.cursors, self.cursor_map.owner = cursors, owner
        self.view.cursors, self.view.owner = cursors, owner
        self.cursor_map.update()
        desktop_overlay = bool(
            self.controller
            and (
                self.controller.backend_name.startswith("Windows")
                or (
                    self.controller.backend_name.startswith("X11")
                    and QApplication.platformName() == "xcb"
                )
            )
        )
        if active and desktop_overlay and self.overlay_toggle.isChecked() and self.backend_choice.currentData() != "mousemux":
            self.overlay.setGeometry(QApplication.primaryScreen().virtualGeometry())
            self.overlay.cursors, self.overlay.owner = cursors, owner
            self.overlay.show()
            self.overlay.update()
        else:
            self.overlay.hide()
        self.status.setText(
            (self.camera.status if self.camera else "Kamera belum aktif")
            + "  |  "
            + (self.controller.status if self.controller else "Desktop belum terhubung")
        )
        self.view.update()

    def closeEvent(self, event):
        self.pause()
        self.overlay.hide()
        if self.camera:
            self.camera.stop()
        if self.controller:
            self.controller.stop()
        # Input release is performed by its owning thread before allowing the window to disappear.
        if self.controller and self.controller.is_alive():
            self.status.setText("Menutup sesi desktop; batalkan dialog izin jika masih terbuka…")
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        self.preferences.setValue("camera", self.camera_id.value())
        self.preferences.setValue("hand", self.hand.currentIndex())
        self.preferences.setValue("gain", self.gain.value())
        self.preferences.setValue("cutoff", self.smoothness.value())
        self.preferences.setValue("swap_v3", self.swap_hands.isChecked())
        if self.camera:
            self.camera.join(timeout=0.5)
        self.overlay.close()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="DeskPilot camera desktop control")
    parser.add_argument("--preview", action="store_true", help="Simulate actions without controlling desktop")
    parser.add_argument("--model", default=str(Path.home() / ".cache/deskpilot/hand_landmarker.task"))
    args = parser.parse_args()
    application = QApplication(sys.argv[:1])
    application.setStyleSheet(STYLE)
    window = Window(args)
    window.show()
    sys.exit(application.exec())
