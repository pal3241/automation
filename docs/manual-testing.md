# Real-device acceptance checklist

Automated tests cover logic and simulated input. Complete this checklist on an actual webcam with Windows, X11, and the target Wayland compositor before calling the hardware integration verified.

- [ ] Fresh venv installation and first model download; restart offline with cached model.
- [ ] Permission denied/camera busy/unplugged: useful error and release, no UI freeze.
- [ ] Right and left labels match real hands in mirrored camera preview; all 21 landmarks and five fingertip labels display.
- [ ] Start with pinched hand: no action until opened. No hand steals another hand’s active gesture.
- [ ] Index clutch begins without jumping, tracks motion, stops at release; repositioning open hand leaves cursor stationary.
- [ ] Middle pinch holds left at its saved cursor; release completes one click.
- [ ] Camera virtual Activate/Pause/Stop uses dwell once per entry, never also dispatches a desktop click.
- [ ] With zoom mode enabled, two index pinches (including staggered starts) zoom supported content both directions. Release cannot turn into an unexpected drag.
- [ ] Physically confirm configured Super/Alt + left/right/middle mouse drag works in the desktop first.
- [ ] Pinky pinch moves or resizes a normal window according to the selected mode; release frees modifiers/buttons. Fullscreen/fixed-size window limitation is visible in docs.
- [ ] Hand loss/occlusion during move/resize releases keys; no automatic resume while still pinched.
- [ ] Stop and app close during drag release inputs. Esc/Space checked with app focus only.
- [ ] Wayland grant keyboard/pointer + one full monitor, test logical scaling (100%, 150%, 200%), both click corners and relative motion.
- [ ] Wayland deny/cancel/revoke: release/close, status error, reconnect possible. Cancel connection while permission dialog is open.
- [ ] Unsupported Wayland portal gives clear failure; Preview still works.
- [ ] X11 monitor layout mapping documented; check a multi-monitor root with negative monitor origin.
- [ ] Windows 10/11: DirectShow/MSMF camera fallback, clicks, drag, right-click, and Ctrl+scroll work in normal non-elevated apps.
- [ ] Windows multi-monitor: pointer reaches every edge, including a monitor left/above the primary display and mixed DPI scaling.
- [ ] Windows pinky move/resize targets the window below its saved cursor; maximized/minimized targets show a clear error and do not stick input.
- [ ] Windows overlay shows both logical cursors, remains click-through, does not take focus, and follows the complete virtual desktop geometry.
- [ ] Windows elevated application is not assumed controllable from a non-elevated DeskPilot process.
- [ ] With MouseMux V2 SDK enabled and Multiplex mode active, two hands move different desktop pointers simultaneously while physical mouse remains independent.
- [ ] MouseMux: hold left drag with both hands; releasing or losing one hand does not release the other. Stop releases both, and closing DeskPilot destroys only its two virtual users.
- [ ] MouseMux: SDK missing/stopped/full-screen coordinate limits fail clearly without sending actions through the shared SendInput pointer. Check negative-screen-coordinate monitor layout.
- [ ] Left/right labels match physical hands with default swap on and off on different webcam models; setting persists on the next launch.
- [ ] Track CPU/FPS and practical latency at 640x480; reduce background load if necessary.

Record distro, session type, compositor version, Python/dependency versions, camera model, and observed results. Do not interpret unit-test success as this checklist being complete.

## v0.2 dual-hand acceptance

- [ ] Middle pinch presses left once; release clicks. Keep middle pinched, add index, move, remove index, then release middle: exactly one down/up and no target jump.
- [ ] Ring pinch performs one right-click, never a window move. Pinky dropdown controls window move versus resize.
- [ ] Both logical cursor positions move independently. Left can control without Right present. A second hand cannot click/steal while first hand drags; no delayed click after release.
- [ ] Two-cursor camera drawing and map agree. X11 overlay passes physical clicks and does not steal focus. Wayland does not attempt global overlay.
- [ ] Stationary hand jitter is reduced; slow precise movement remains usable; quick movement has acceptable lag at 20/30/60 FPS.
- [ ] Detector output order changes, brief label flips, crossed hands, occlusion, disappearance, and re-entry: verify identity/rearm rather than assuming simulated tests prove camera accuracy.
- [ ] Stop camera, toggle swap labels, restart. Verify actual physical Left/Right separately with palm facing camera.
- [ ] Zoom toggle off allows both clutches without zoom. Toggle on gives Ctrl+scroll and requires opening both hands afterward.
- [ ] Small display: main control buttons/Stop remain visible without scrolling sidebar.
