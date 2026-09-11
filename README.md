# DeskPilot — Linux Camera Automation

Fondasi Python untuk mengontrol desktop dengan kamera dan gestur tangan. GUI menampilkan video kamera bercermin, kerangka 21 titik per tangan, label jari, identitas kiri/kanan, status gestur, dan tombol virtual. Tahap berikutnya dapat memasukkan perintah suara/AI melalui kontrak `Action` yang sama.

**Tahap 1:** kamera + GUI + gestur + backend Linux. AI, mikrofon, STT, dan TTS belum diimplementasikan.

## Jalankan

Python **3.10–3.13**, webcam, dan sesi desktop Linux lokal diperlukan. Python 3.12 disarankan untuk awal. Jangan menjalankan aplikasi sebagai root.

```bash
git clone https://github.com/pal3241/automation.git
cd automation
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m deskpilot
```

Jika Python bawaan distro belum didukung dependensi MediaPipe, gunakan Python 3.12 yang dipasang terpisah untuk membuat virtual environment. Jangan mengganti Python sistem.

Paket sistem yang mungkin diperlukan:

```bash
# Fedora
sudo dnf install mesa-libGL mesa-libEGL mesa-libGLES portaudio libxcb xcb-util-cursor

# Ubuntu / Debian
sudo apt install python3-venv libgl1 libegl1 libgles2 libportaudio2 libxcb-cursor0
```

Untuk Wayland, pastikan `xdg-desktop-portal` dan backend desktop yang sesuai (misalnya GNOME atau KDE) tersedia. Program menggunakan D-Bus RemoteDesktop, bukan emulasi X11 melalui XWayland.

Pertama kali menekan **Mulai kamera**, aplikasi mengunduh model resmi Hand Landmarker (~8 MB) ke `~/.cache/deskpilot/hand_landmarker.task`. Setelah itu pelacakan dapat digunakan offline. Tidak ada gambar kamera atau tangkapan desktop yang dikirim ke server. Portal Wayland meminta pemilihan satu monitor untuk memperoleh koordinat; program tidak membaca stream video layar.

Model juga dapat disiapkan lebih dulu:

```bash
python scripts/download_model.py
python -m deskpilot --model /path/hand_landmarker.task
```

## Urutan penggunaan

1. Buka aplikasi, pilih nomor kamera dan tangan kontrol kanan/kiri.
2. Mulai kamera. Cocokkan label KANAN/KIRI dengan tanganmu pada tampilan bercermin.
3. Hubungkan desktop. Pada Wayland, izinkan **keyboard + pointer** dan pilih **satu monitor penuh** pada dialog portal.
4. Aktifkan kontrol melalui tombol GUI atau arahkan telunjuk ke tombol virtual AKTIFKAN selama 0,9 detik dengan tangan tidak mencubit.
5. Buka tangan sekali untuk mengaktifkan pengenal gestur, lalu coba gestur di bawah.
6. Lepaskan semua cubitan sebelum beralih ke gestur berikutnya.

Mulai dengan `python -m deskpilot --preview` jika ingin menguji deteksi tanpa mengirim input ke desktop. Hubungkan backend Preview dan aktifkan kontrol untuk melihat perubahan status gestur.

## Gestur

Semua cubitan memakai **ibu jari + jari yang disebutkan**. Pilihan tangan kontrol mengunci kepemilikan sehingga tangan lain tidak mengambil alih kursor ketika tangan utama hilang.

| Gestur | Hasil |
| --- | --- |
| Telunjuk + ibu jari, tahan dan gerakkan | Menggerakkan kursor secara relatif dari posisi saat ini; awal cubitan tidak melompatkan kursor |
| Lepas cubitan telunjuk | Kursor berhenti; tangan bebas digerakkan untuk mengambil posisi baru |
| Tengah + ibu jari | Klik kiri sekali tepat pada lokasi layar yang dipetakan dari ujung telunjuk; tidak perlu membawa kursor lebih dulu |
| Manis + ibu jari, tahan dan gerakkan | Menunjuk lokasi jendela lalu menahan modifier + tombol mouse kiri untuk memindahkannya |
| Kelingking + ibu jari, tahan dan gerakkan | Menunjuk lokasi jendela lalu menahan modifier + tombol mouse resize yang dipilih untuk mengubah ukurannya |
| Kedua tangan mencubit telunjuk, renggangkan / dekatkan | Ctrl + scroll untuk zoom in / out pada aplikasi yang mendukungnya |
| Telunjuk tidak mencubit berada di tombol kamera 0,9 detik | Aktifkan/jeda atau Stop, satu aktivasi sampai jari keluar dari tombol |

**Klik langsung** berarti posisi ujung telunjuk pada gambar kamera dipetakan ke layar yang dipilih: kiri atas kamera = kiri atas layar. Cubit jari tengah saat telunjuk menunjuk target. Penunjuk bundar di kamera membantu membidik, sementara kursor sistem hanya dipindah pada saat klik. Ini bukan deteksi otomatis tombol aplikasi atau proyeksi tombol ke meja.

**Clutch kursor bukan mouse-down.** Cubit telunjuk hanya membawa penunjuk; tidak menyeret file. Pemindahan dan resize jendela memakai gestur khusus. Dua klik terpisah dapat menjadi double-click menurut pengaturan desktop; tidak ada gestur double-click khusus pada tahap ini.

**Zoom** menggunakan Ctrl+scroll, bukan pembesaran seluruh layar OS. Arahkan kursor ke konten aplikasi yang diinginkan sebelum zoom. Kontrol zoom dua tangan mendapat prioritas atas perpindahan kursor; setelah zoom selesai, buka kedua tangan sebelum melanjutkan.

## Kompatibilitas Linux dan batasannya

| Lingkungan | Jalur input | Catatan |
| --- | --- | --- |
| X11 | python-xlib / XTest | Pointer, klik, Ctrl+scroll; pemetaan absolut mencakup root desktop (gabungan monitor) |
| GNOME/KDE Wayland dengan RemoteDesktop + ScreenCast portal | D-Bus Notify methods | Memerlukan izin dan metadata ukuran monitor; satu monitor dipilih untuk klik absolut |
| Wayland tanpa portal RemoteDesktop yang memadai | Preview kamera | GUI menampilkan error jelas; kontrol tidak dianggap aktif |
| Windows / macOS | Belum tersedia | Fondasi ini khusus Linux |

**Pindah/resize bergantung pada shortcut window manager**, bukan API universal jendela. Default Super+left-drag untuk pindah; resize memakai mouse tengah saat sesi terdeteksi GNOME, atau kanan untuk desktop lain. GUI menyediakan pilihan modifier Super/Alt dan mouse resize kanan/tengah. Sesuaikan dengan shortcut desktop. Jendela maximized/fullscreen atau aplikasi dengan ukuran tetap mungkin menolak resize. Program tidak mengubah pengaturan desktop secara otomatis.

Pada GNOME, periksa konfigurasi `mouse-button-modifier` dan `resize-with-right-button` jika pindah/resize belum berfungsi. Pada KDE, periksa pengaturan Window Actions → Modifier key dan aksi tombol kanan. Uji dahulu dengan mouse fisik dan modifier yang dipilih.

Sesi desktop aktual tetap perlu diuji pada perangkat pengguna. Keberadaan kode backend tidak berarti seluruh compositor dan versi distro sudah diuji. Kamera, pencahayaan, oklusi, dan akurasi klasifikasi tangan memengaruhi hasil. Ukuran tangan/kepercayaan dinormalisasi, tetapi penentuan jari terbuka pada panel status merupakan heuristik geometri.

## Penghentian dan kegagalan

- Tombol GUI Stop, tombol kamera STOP, serta Esc/Space **ketika jendela DeskPilot memiliki fokus** menjeda kontrol.
- Esc/Space **bukan global hotkey**. Saat aplikasi lain aktif, gunakan tombol kamera STOP atau kembali ke DeskPilot memakai mouse fisik.
- Hilangnya tangan utama atau confidence rendah segera menghasilkan release. Kamera/frame yang macet memicu watchdog sekitar 300 ms, di luar latensi transport desktop.
- Setelah kehilangan tracking, buka tangan sebelum mencubit kembali. Tidak ada kelanjutan drag otomatis.
- Antrean hanya menyimpan frame terbaru. Pause membatalkan input yang belum dijalankan. Tidak ada antrean gerakan panjang.
- Modifier/tombol dilepas saat pergantian gestur, jeda, error, atau penutupan normal. OS/portal yang hang atau proses yang dibunuh paksa tidak dapat dijamin menerima release; pada Wayland sesi portal ditutup saat cleanup.
- Kontrol desktop hanya aktif setelah kamu menekan Aktifkan. AI/voice belum dapat mengirim tindakan.
- Mouse fisik tetap tersedia, tetapi tahap ini **belum mendeteksi pengambilalihan mouse fisik secara otomatis**. Jeda gestur sebelum menggunakan mouse.

## Struktur

- `deskpilot/gestures.py`: data tangan, histeresis cubitan, clutch, zoom, dan dwell; tanpa dependensi GUI/OS.
- `deskpilot/controller.py`: satu pemilik input, mailbox terbatas, pembatalan dan watchdog.
- `deskpilot/backends/`: kontrak tindakan, preview, X11, dan Wayland portal.
- `deskpilot/camera.py`: pengunduhan model, capture kamera, dan inferensi dua tangan.
- `deskpilot/app.py`: GUI, overlay kamera, pengaturan, arbitrasi tombol virtual.
- `tests/`: tes transisi gestur, kepemilikan input, watchdog, portal mock, dan rendering GUI.

Pengaturan kamera, tangan, dan sensitivitas disimpan melalui Qt QSettings. Untuk mengubah tangan/sensitivitas/modifier/tombol resize, putuskan lalu hubungkan kembali backend.

## Pengembangan

```bash
python -m pip install -e '.[dev]'
ruff check .
QT_QPA_PLATFORM=offscreen pytest -q
```

Lihat [arsitektur](docs/architecture.md) dan [checklist perangkat nyata](docs/manual-testing.md). GitHub Actions menjalankan tes pada Python 3.10, 3.12, dan 3.13; hasil CI harus diperiksa, bukan diasumsikan.

## Referensi

- [MediaPipe Hand Landmarker Python](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [XDG RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [XDG ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
- [Python Xlib](https://python-xlib.github.io/)

Lisensi kode: MIT, sesuai LICENSE repo. Model dan dependensi mengikuti lisensi masing-masing.
