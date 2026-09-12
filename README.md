# DeskPilot — Camera Automation untuk Linux & Windows

Fondasi Python untuk mengontrol desktop dengan kamera dan gestur tangan. GUI menampilkan video kamera bercermin, kerangka 21 titik per tangan, label jari, identitas kiri/kanan, status gestur, dan tombol virtual. Tahap berikutnya dapat memasukkan perintah suara/AI melalui kontrak `Action` yang sama.

**Tahap 1:** kamera + GUI + gestur + backend Linux/Windows. AI, mikrofon, STT, dan TTS belum diimplementasikan.

## Jalankan

Python **3.10–3.13** dan webcam diperlukan. Python 3.12 disarankan. Pada Linux jangan menjalankan aplikasi sebagai root.

Panduan langkah demi langkah terpisah: [Windows](INSTALL_WINDOWS.txt) dan [Linux](INSTALL_LINUX.txt).

### Windows 10/11

Pasang Python 3.12 64-bit dan Git. Di PowerShell:

```powershell
git clone https://github.com/pal3241/automation.git
cd automation
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m deskpilot
```

Untuk memperbarui instalasi Windows:

```powershell
cd automation
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m deskpilot
```

Untuk **dua pointer Windows independen**, jalankan [MouseMux V2](https://www.mousemux.com/pages/sdk-windows/), aktifkan Windows SDK sesuai panduan MouseMux, lalu gunakan mode **Multiplex**. DeskPilot memilih backend `MouseMux V2 (dua pointer independen)` secara default di Windows. Setiap tangan membuat satu pengguna virtual di MouseMux; mouse fisik tetap milik pengguna/perangkatnya sendiri. Jika tidak memiliki MouseMux atau SDK tidak tersedia, pilih `Windows / SendInput (satu pointer)` untuk mode lama. Program tidak menginstal atau mengubah konfigurasi MouseMux secara otomatis. Dukungan SDK/fitur dapat bergantung pada edisi MouseMux; periksa persyaratan lisensinya.

Backend SendInput biasa tidak membutuhkan driver Python tambahan. Bila kamera tidak terbuka, tutup Camera/Teams/OBS atau aplikasi lain yang memakai webcam, lalu coba nomor kamera lain di GUI.

### Linux

Untuk Fedora dengan Python sistem 3.14, gunakan Python 3.12 terpisah melalui uv (file `.python-version` proyek juga menunjuk 3.12):

```bash
# Pasang uv jika belum tersedia
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

git clone https://github.com/pal3241/automation.git
cd automation
uv python install 3.12
uv venv --python 3.12 .venv312
uv pip install --python .venv312/bin/python -e .
.venv312/bin/python -m deskpilot
```

Untuk memperbarui checkout yang sudah ada:

```bash
cd ~/automation
git pull --ff-only
uv pip install --python .venv312/bin/python -e .
.venv312/bin/python -m deskpilot
```

Python sistem tetap digunakan oleh Fedora. Jangan menghapus batas versi Python proyek untuk memaksa instalasi 3.14.

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

1. Buka aplikasi, isi **ID kamera** seperti `0,1` untuk dua perspektif (`0,1,2` untuk tiga; maksimal delapan kamera). ID pertama adalah kamera utama untuk tombol virtual. Jika label suatu kamera dari arah belakang terbalik, masukkan ID-nya di **Balik label kamera**, misalnya `1`.
2. Mulai kamera. Cocokkan label KANAN/KIRI dengan tanganmu pada tampilan bercermin. Default pertukaran label sekarang aktif; jika kameramu sudah benar, matikan **Tukar label kiri/kanan kamera** sebelum mulai menangkap gambar.
3. Hubungkan desktop. Windows langsung memakai API lokal. Pada Wayland, izinkan **keyboard + pointer** dan pilih **satu monitor penuh** pada dialog portal.
4. Aktifkan kontrol melalui tombol GUI atau arahkan telunjuk ke tombol virtual AKTIFKAN selama 0,9 detik dengan tangan tidak mencubit.
5. Buka tangan sekali untuk mengaktifkan pengenal gestur, lalu coba gestur di bawah.
6. Lepaskan semua cubitan sebelum beralih ke gestur berikutnya.

Mulai dengan `python -m deskpilot --preview` jika ingin menguji deteksi tanpa mengirim input ke desktop. Hubungkan backend Preview dan aktifkan kontrol untuk melihat perubahan status gestur.

## Kamera multiperspektif (v0.5)

Setiap kamera menjalankan capture dan pelacakannya sendiri, lalu semua tayangan muncul dalam grid yang dapat digulir. Model pertama kali diunduh satu kali secara tersinkronisasi sehingga beberapa kamera tidak menulis file yang sama bersamaan. Hasilnya **bukan rekonstruksi 3D/triangulasi**: satu tangan yang terlihat di beberapa kamera dipilih sebagai satu sumber kendali berdasarkan label kanan/kiri, bukan dihitung sebagai dua tangan. Kamera yang sedang dipakai dipertahankan sampai tangan tidak terlihat; saat pindah ke kamera lain, identitas berubah dan **tangan harus dibuka lalu dicubit lagi** untuk mencegah kursor melompat. Tidak ada sinkronisasi hardware antarkamera. Mulailah dengan dua kamera karena setiap kamera membutuhkan inferensi tambahan dan dapat menurunkan FPS.

Tombol virtual hanya aktif pada kamera pertama; Stop di GUI tetap dapat dipakai saat kamera utama terhalang. Seluruh gambar tetap diproses lokal. Jika satu kamera gagal dibuka, status kegagalannya terlihat per ID dan kamera lain tetap bisa digunakan. Untuk resize, kedua tangan wajib terlihat bersama pada **satu kamera yang sama** agar jaraknya bermakna; sudut pandang berbeda tidak dikalibrasi dan tidak digabung untuk mengukur tarikan.

## Gestur — dua kursor dan sentuhan jari

Setiap tangan memiliki **posisi kursor virtual sendiri**, warna hijau R (kanan) dan ungu L (kiri). Kedua penunjuk terlihat di atas tampilan kamera dan peta posisi layar pada GUI. Posisi awal berasal dari telunjuk saat tangan pertama kali terdeteksi; setelah itu tersimpan, tidak mengikuti tangan terbuka. Cubit telunjuk untuk membawa kursor ke target, lalu lepaskan sebelum klik. Klik memakai posisi kursor tangan itu, bukan memetakan ulang ujung jari yang sedang menekuk.

| Gestur dengan ibu jari | Hasil |
| --- | --- |
| Telunjuk menyentuh ibu jari | Menggerakkan kursor tangan tersebut; lepas untuk berhenti |
| Jari tengah menyentuh ibu jari | Menekan tombol kiri satu kali; lepas tengah untuk menyelesaikan klik |
| Tengah tetap menyentuh ibu jari, lalu telunjuk ikut menyentuh | Drag dengan tombol kiri yang sama, tanpa klik kedua; gerakkan tangan |
| Lepas telunjuk saat tengah masih menyentuh | Drag berhenti bergerak, tombol kiri tetap ditahan |
| Lepas tengah / buka tangan | Lepas tombol kiri dan drop |
| Jari manis menyentuh ibu jari | Klik kanan sekali per cubitan |
| Satu tangan: kelingking menyentuh ibu jari | Pindah jendela dari posisi kursor tangan itu |
| Kedua tangan: kelingking menyentuh ibu jari, lalu tarik keluar/dalam | Perbesar/perkecil jendela di posisi kursor tangan aktif, dalam kamera yang sama |
| Centang **Ujung telunjuk: cubit untuk tarik jendela**, lalu cubit telunjuk + ibu jari | Ambil jendela tepat di posisi ujung telunjuk dan tarik mengikuti ujung jari; lepas untuk menjatuhkan |
| Dua tangan mencubit telunjuk | Dua kursor bergerak sendiri; jika **Mode zoom dua tangan** dicentang, berubah menjadi Ctrl+scroll |
| Telunjuk terbuka di tombol virtual 0,9 detik | Aktifkan/jeda/Stop, satu aktivasi per masuk area |

Secara default cubitan telunjuk adalah clutch tanpa mouse-down; untuk drag file/titlebar gunakan tengah + telunjuk + ibu jari. Jika **mode ujung telunjuk** diaktifkan, cubitan telunjuk berubah menjadi *ambil dan tarik jendela* (bukan pembawa kursor). Ujung jari yang dicerminkan dipetakan langsung ke seluruh desktop, bukan hanya jendela GUI; arahkan kamera ke layar dari depan dan uji dulu di Preview. Perubahan mode memerlukan putus/hubung ulang backend. Gestur dua kelingking melepaskan aksi satu tangan yang sedang aktif sebelum memulai resize, dan melepas satu tangan mengakhiri resize; buka kedua tangan untuk mengaktifkan gestur berikutnya.

### Dua tangan dan mouse sistem

Backend XTest, RemoteDesktop dan Windows SendInput mengirim tindakan lewat **satu mouse sistem**. Tangan pertama yang memulai gestur menguasainya sampai gestur dilepas. Jika mulai tepat bersamaan, pilihan Prioritas bersamaan menentukan pemilik. Tangan kedua tetap bisa menggerakkan kursor virtualnya, tetapi tidak mengirim klik atau merebut drag. Buka lalu cubit ulang tangan kedua untuk mengambil alih setelah tangan pertama selesai. Tidak ada klik tertunda yang diantrikan.

Pada backend **MouseMux V2**, tangan kanan dan kiri masing-masing punya pointer desktop dan tombol sendiri, sehingga bisa menunjuk, klik, dan drag bersamaan tanpa merebut pointer sistem. Dua pointer desktop digambar oleh MouseMux sendiri; overlay tambahan DeskPilot mati pada mode ini agar tidak menjadi empat. Pindah/resize jendela memakai API Windows per tangan. Mode zoom dua tangan dinonaktifkan khusus backend MouseMux V2: SDK pesan yang dipakai di sini tidak menyediakan perintah scroll pointer. Jika MouseMux ditutup, DeskPilot menghentikan kontrol dan tidak diam-diam kembali ke satu pointer.

Pada Windows SendInput dan sesi Qt/X11, tersedia overlay transparan yang melewatkan klik untuk melihat dua kursor *visual* di atas desktop. Pada Wayland, lihat kedua posisi di GUI, sementara pointer sistem mengikuti tangan pemilik. **Tanpa MouseMux, dua kursor visual bukan dua pointer OS yang dapat mengklik bersamaan.** Mode zoom dua tangan default mati supaya tidak bertabrakan dengan gerakan dua kursor.

### Gerakan lebih halus dan label tangan

- Filter adaptif berbasis waktu menyaring jitter saat pelan dan merespons lebih cepat saat tangan bergerak. Posisi telapak menjadi referensi gerak agar menekuk telunjuk tidak membuat kursor melompat.
- Respons gerakan lebih rendah = lebih halus; lebih tinggi = lebih responsif. Sensitivitas mengubah jarak perpindahan. Ubah setelah memutuskan koneksi desktop.
- Aktivasi cubitan menunggu sekitar 55 ms dan memakai dua ambang jarak untuk menekan/melepas. Pelepasan tangan dan input yang hilang tidak menunggu debounce aktivasi.
- Pelacakan menggunakan posisi/prediksi telapak, bukan urutan tangan yang dikembalikan model. Label dikunci setelah sedikitnya tiga frame dengan bukti klasifikasi yang cukup.
- Kalau dua jalur terlalu ambigu (misalnya tangan saling menutupi), input dihentikan dan tangan diakuisisi ulang. Tangan yang terdeteksi kembali harus dibuka sebelum bisa mengontrol lagi.
- Pertukaran label **aktif secara default mulai v0.4** karena sumber kamera pengguna melaporkan label kebalik pada tampilan bercermin. Jika masih terbalik, hentikan kamera dan ubah centang **Tukar label kiri/kanan kamera**; kemudian mulai ulang. Pengaturan lama dimigrasikan sekali ke default baru, dan perubahan manual sesudahnya disimpan.
- Confidence yang ditampilkan merupakan keyakinan label saat akuisisi, bukan jaminan kualitas pose setiap frame. Identitas bisa tetap ambigu pada oklusi, pencahayaan buruk, atau tangan bersilangan; tidak ada klaim akurasi sempurna.

Zoom memakai Ctrl+scroll pada aplikasi yang mendukungnya, bukan pembesaran seluruh layar OS. Pastikan pointer berada di konten yang diinginkan sebelum mengaktifkan zoom. Setelah zoom selesai, buka kedua tangan untuk melanjutkan.

## Kompatibilitas desktop dan batasannya

| Lingkungan | Jalur input | Catatan |
| --- | --- | --- |
| Windows 10/11 | Win32 `SendInput` + `SetWindowPos` | Pointer, klik, drag, Ctrl+scroll, desktop multi-monitor, pindah/resize jendela target |
| Windows 10/11 + MouseMux V2 SDK aktif | Win32 registered messages ke MouseMux + `SetWindowPos` | Dua pointer desktop independen, dua klik/drag simultan; zoom dua tangan belum tersedia di mode ini |
| X11 | python-xlib / XTest | Pointer, klik, Ctrl+scroll; pemetaan absolut mencakup root desktop (gabungan monitor) |
| GNOME/KDE Wayland dengan RemoteDesktop + ScreenCast portal | D-Bus Notify methods | Memerlukan izin dan metadata ukuran monitor; satu monitor dipilih untuk klik absolut |
| Wayland tanpa portal RemoteDesktop yang memadai | Preview kamera | GUI menampilkan error jelas; kontrol tidak dianggap aktif |
| macOS | Belum tersedia | Gunakan mode Preview; belum ada backend input macOS |

Pada **Windows**, satu cubitan kelingking memilih jendela di bawah kursor untuk dipindah; dua cubitan kelingking mengubah ukuran jendela ketika tangan ditarik keluar/dalam. Mode ujung telunjuk mengambil jendela tepat di bawah ujung jari. Pulihkan jendela yang maximized/minimized sebelum gestur. Windows dapat menolak input atau perubahan jendela milik aplikasi yang dijalankan sebagai Administrator; jalankan DeskPilot dengan tingkat hak yang sama hanya jika benar-benar diperlukan.

Pada **Linux**, pindah/resize bergantung pada shortcut window manager. Default Super+left-drag untuk pindah; resize memakai mouse tengah saat sesi terdeteksi GNOME, atau kanan untuk desktop lain. GUI menyediakan pilihan modifier Super/Alt dan mouse resize kanan/tengah. Sesuaikan dengan shortcut desktop. Jendela fullscreen atau aplikasi dengan ukuran tetap mungkin menolak resize. Program tidak mengubah pengaturan desktop secara otomatis.

Pada GNOME, periksa konfigurasi `mouse-button-modifier` dan `resize-with-right-button` jika pindah/resize belum berfungsi. Pada KDE, periksa pengaturan Window Actions → Modifier key dan aksi tombol kanan. Uji dahulu dengan mouse fisik dan modifier yang dipilih.

Sesi desktop aktual tetap perlu diuji pada perangkat pengguna. Keberadaan kode backend tidak berarti seluruh compositor dan versi distro sudah diuji. Kamera, pencahayaan, oklusi, dan akurasi klasifikasi tangan memengaruhi hasil. Ukuran tangan/kepercayaan dinormalisasi, tetapi penentuan jari terbuka pada panel status merupakan heuristik geometri.

## Penghentian dan kegagalan

- Tombol GUI Stop, tombol kamera STOP, serta Esc/Space **ketika jendela DeskPilot memiliki fokus** menjeda kontrol.
- Esc/Space **bukan global hotkey**. Saat aplikasi lain aktif, gunakan tombol kamera STOP atau kembali ke DeskPilot memakai mouse fisik.
- Hilangnya tangan pemilik input atau confidence rendah segera menghasilkan release. Kamera/frame yang macet memicu watchdog sekitar 300 ms, di luar latensi transport desktop.
- Setelah kehilangan tracking, buka tangan sebelum mencubit kembali. Tidak ada kelanjutan drag otomatis.
- Antrean hanya menyimpan frame terbaru. Pause membatalkan input yang belum dijalankan. Tidak ada antrean gerakan panjang.
- Modifier/tombol dilepas saat pergantian gestur, jeda, error, atau penutupan normal. OS/portal yang hang atau proses yang dibunuh paksa tidak dapat dijamin menerima release; pada Wayland sesi portal ditutup saat cleanup.
- Kontrol desktop hanya aktif setelah kamu menekan Aktifkan. AI/voice belum dapat mengirim tindakan.
- Mouse fisik tetap tersedia, tetapi tahap ini **belum mendeteksi pengambilalihan mouse fisik secara otomatis**. Jeda gestur sebelum menggunakan mouse.

## Struktur

- `deskpilot/gestures.py`: dua state kursor, klik/drag, arbitrasi pemilik, debounce, zoom, dan dwell.
- `deskpilot/tracking.py`: asosiasi identitas tangan dan filter adaptif.
- `deskpilot/multicamera.py`: validasi ID kamera, deduplikasi dua sudut, dan rearm saat perpindahan kamera.
- `deskpilot/cursors.py`: peta dua kursor dan overlay transparan X11/Windows.
- `deskpilot/controller.py`: satu pemilik input, mailbox terbatas, pembatalan dan watchdog.
- `deskpilot/backends/`: kontrak tindakan, preview, Win32, MouseMux V2 opsional, X11, dan Wayland portal.
- `deskpilot/camera.py`: pengunduhan model tersinkronisasi, capture dan inferensi per kamera.
- `deskpilot/app.py`: GUI, overlay kamera, pengaturan, arbitrasi tombol virtual.
- `tests/`: tes transisi gestur, kepemilikan input, watchdog, portal mock, dan rendering GUI.

Pengaturan daftar kamera, pembalikan label per kamera, mode ujung jari, prioritas tangan, sensitivitas, dan respons gerakan disimpan melalui Qt QSettings. Untuk mengubah sumber kamera hentikan semua kamera dulu; untuk mengubah mode gestur/tangan/sensitivitas/modifier, putuskan lalu hubungkan kembali backend.

## Pengembangan

```bash
python -m pip install -e '.[dev]'
ruff check .
QT_QPA_PLATFORM=offscreen pytest -q
```

Lihat [arsitektur](docs/architecture.md) dan [checklist perangkat nyata](docs/manual-testing.md). GitHub Actions menjalankan tes Linux pada Python 3.10, 3.12, dan 3.13, serta tes Windows pada Python 3.12; hasil CI harus diperiksa, bukan diasumsikan.

## Referensi

- [MediaPipe Hand Landmarker Python](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [XDG RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [XDG ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
- [Python Xlib](https://python-xlib.github.io/)
- [Microsoft SendInput](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput)
- [MouseMux V2 Windows SDK](https://www.mousemux.com/pages/sdk-windows/)

Lisensi kode: MIT, sesuai LICENSE repo. Model dan dependensi mengikuti lisensi masing-masing.
