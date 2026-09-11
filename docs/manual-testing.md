# Real-device acceptance checklist

Automated tests cover logic and simulated input. Complete this checklist on actual webcam + X11 and webcam + target Wayland compositor before calling the hardware integration verified.

- [ ] Fresh venv installation and first model download; restart offline with cached model.
- [ ] Permission denied/camera busy/unplugged: useful error and release, no UI freeze.
- [ ] Right and left labels match real hands in mirrored camera preview; all 21 landmarks and five fingertip labels display.
- [ ] Start with pinched hand: no action until opened. Wrong hand cannot drive pointer.
- [ ] Index clutch begins without jumping, tracks motion, stops at release; repositioning open hand leaves cursor stationary.
- [ ] Middle pinch clicks pointed small target exactly once, regardless of how long pinch is held. Release/open/re-pinch clicks again.
- [ ] Camera virtual Activate/Pause/Stop uses dwell once per entry, never also dispatches a desktop click.
- [ ] Two index pinches (including staggered starts) zoom supported content both directions without moving pointer. Release cannot turn into an unexpected drag.
- [ ] Physically confirm configured Super/Alt + left/right/middle mouse drag works in the desktop first.
- [ ] Ring pinch moves a normal window, pinky pinch enlarges/shrinks it; release frees modifiers/buttons. Fullscreen/fixed-size window limitation is visible in docs.
- [ ] Hand loss/occlusion during move/resize releases keys; no automatic resume while still pinched.
- [ ] Stop and app close during drag release inputs. Esc/Space checked with app focus only.
- [ ] Wayland grant keyboard/pointer + one full monitor, test logical scaling (100%, 150%, 200%), both click corners and relative motion.
- [ ] Wayland deny/cancel/revoke: release/close, status error, reconnect possible. Cancel connection while permission dialog is open.
- [ ] Unsupported Wayland portal gives clear failure; Preview still works.
- [ ] X11 monitor layout mapping documented; check a multi-monitor root with negative monitor origin.
- [ ] Track CPU/FPS and practical latency at 640x480; reduce background load if necessary.

Record distro, session type, compositor version, Python/dependency versions, camera model, and observed results. Do not interpret unit-test success as this checklist being complete.
