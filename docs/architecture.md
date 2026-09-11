# Foundation contracts

## Threads and ownership

Qt's main thread owns widgets and GUI button hit-testing. CameraWorker owns OpenCV and MediaPipe. It writes one latest frame; Qt polls at ~30 Hz. Controller owns its backend and GestureEngine. Xlib and the portal asyncio loop are never used across threads.

GUI submits a frame only after virtual-button arbitration. A button target suppresses desktop gesturing for that frame. Input packets contain a generation and monotonic timestamp. Arming/pausing changes the generation and clears pending input. The controller discards outdated generations and stale packets, and checks cancellation before each action. A 300 ms watchdog resets state when input stops. This is a software timeout, not a hard real-time guarantee across a hung compositor.

## Gesture lifecycle

Startup, rearm, ambiguous handedness, low confidence, and hand loss require an open hand. Ratios use thumb-to-tip distance / palm width with image-aspect correction. Pinch activates below 0.30 and releases above 0.46. Handedness locks the controlling hand. A gesture remains latched until release; click is emitted only on entry.

Cursor starts from its current OS position. Smoothed camera deltas become relative desktop deltas. Releasing does not click. Middle-finger pinch emits one absolute click at the index fingertip. Ring/pinky pinch establishes a window-manager modifier drag at the pointed position. Two index pinches may upgrade cursor clutch to zoom; leaving zoom requires open hands to avoid accidental pointer jumps.

## Desktop actions

`Action(kind, values)` is the bounded contract for future producers. Supported kinds: release, move, click_at, begin_window, begin_resize, zoom. Unknown kinds fail closed. GUI toggles are internal events, not arbitrary Python or shell commands.

Future AI/STT integration should add schema validation, user intent context, action scope, and an arbiter before reaching Controller. Voice stop should disarm the existing controller. Do not let AI and camera write to separate backends simultaneously. No LLM provider, secret, microphone listener, or command interpreter is included now.

## Wayland

RemoteDesktop.CreateSession → SelectDevices(pointer + keyboard) → ScreenCast.SelectSources(one monitor) → RemoteDesktop.Start. Request signal subscriptions exist before calls, with unique tokens. Response wait is cancellable; request/session cleanup closes handles. Start validates granted devices and monitor dimensions. Absolute coordinates are local to the stream; relative movement uses logical stream units.

The backend uses Notify methods, not EIS. It does not connect both transports, does not require root, and does not inject through XWayland. The portal loop is pumped while idle for session revocation. Modifier input emulates configured compositor shortcuts; portal does not expose a general window geometry API.

## Deliberate scope

No global physical-input takeover, reliable hand identity beyond handedness, pinch-depth estimation, projected tabletop UI, desktop screenshot understanding, global panic shortcut, or arbitrary-app semantic controls. These require additional work; the GUI/docs should not claim them.
