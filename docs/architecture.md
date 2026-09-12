# Foundation contracts — v0.5

## Threads and ownership

Qt owns widgets, camera button arbitration, and the optional X11/Windows overlay. One CameraWorker per ID owns its OpenCV capture, MediaPipe detector, and HandTracker; every source has a latest-frame mailbox. A shared lock guards the one-time model download. Qt pulls packets and MultiCameraFusion selects at most one observation per anatomical side, preferring a shared camera for two-hand actions. Source ID is part of the tracking identity: switching viewpoint releases input and requires an open hand. No uncalibrated multi-view triangulation or physical 3D hand matching is claimed. Controller owns GestureEngine and the desktop connection. It publishes cursor-position snapshots for the GUI. No frame queue grows without bound.

Each hand has a separate cursor position, filter, debounce state, pinch hysteresis, track ID and rearm state. Only one hand owns desktop input at a time. The existing owner is processed first. Other hands may move their logical cursors but their clicks are suppressed, not queued. They must release/regrip after the owner finishes. Priority config breaks simultaneous starts only.

Pause changes input generation, discards pending input, and asks the owning executor to release buttons/modifiers. A 300 ms watchdog releases input on frame stalls. This is not a hard real-time guarantee across a hung compositor. Missing tracks release immediately at the next observed packet.

## Hand identity

MediaPipe processes mirrored RGB video, returns two landmark sets and raw handedness categories. HandTracker associates palm centroids with previous velocity predictions by exhaustive assignments (including unmatched detections). It does not equate detection list order or current Left/Right classification with identity. Initial category votes acquire a unique anatomical label over at least three frames. Labels remain fixed for the life of the track.

Unmatched tracks expire after 250 ms; missing hands are not extrapolated into actionable observations. Near-tied assignments for two overlapping tracks drop tracking rather than swap a drag. A newly acquired track has a new integer ID; GestureEngine requires an open hand after ID changes. A camera-level swap option is applied before initial category voting and is only editable when capture is stopped. This cannot eliminate all identity ambiguity after long occlusion/crossing.

## Movement and gestures

Palm motion avoids sudden index-tip changes when folding fingers. The adaptive low-pass uses elapsed time and filtered velocity, with a small spatial deadband. Each logical cursor stores bounded normalized screen coordinates; absolute backend moves avoid losing subpixel deltas to integer relative input. On regrip, the palm anchor resets and the saved cursor stays unchanged (the system pointer may move to that hand's saved cursor on ownership acquisition).

Thumb-middle emits one left-down. Adding index upgrades to drag, retaining that button without releasing/pressing again. Removing index freezes motion, retaining left-down; removing middle releases. Thumb-ring emits right click once. One thumb-pinky begins the window-manager drag. Paired thumb-pinky on the same camera ends any earlier drag, starts one resize at the current cursor and maps the change in palm separation onto size; losing either hand releases and rearms. Thumb-index normally moves the cursor without mouse-down. Opt-in fingertip mode instead starts a window move at the absolute index tip and follows its smoothed position until release. Unrecognized multi-finger contacts reset/rearm instead of choosing a possibly destructive gesture.

Activation is debounced 55 ms by time; release is immediate. Ratios use palm width and image aspect correction with distinct pinch-on/pinch-off thresholds. Zoom is opt-in and takes priority only when both hands request index clutch; exiting zoom releases and rearms both hands.

## Desktop rendering and transport

Logical cursors are drawn in the camera view and GUI cursor map. A transparent, non-focusable, input-transparent desktop overlay is available on Windows and X11. Wayland uses the GUI representation and one portal pointer, with no claim of global overlays or independent multi-seat input.

The Windows backend uses `SendInput` absolute coordinates with `MOUSEEVENTF_VIRTUALDESK`, so the normalized gesture space covers the complete multi-monitor virtual desktop. Keyboard and button ownership still goes through `DesktopBackend`. Window move/resize selects the top-level window below the cursor and applies palm deltas with `SetWindowPos`; maximized/minimized targets fail closed. Win32 loading remains lazy so importing or testing the package on Linux does not access Windows DLLs.

When `Settings.independent` is selected for the MouseMux V2 backend, each hand instead emits tagged actions. The SDK creates two ephemeral virtual users and routes coordinates/button presses via separate registered Win32 messages; per-hand release cannot drop the other hand's drag. Zoom is disabled here (no per-user scroll setter in this transport); window actions use Win32 `SetWindowPos` on separate captured targets. SDK failure never falls back to SendInput. Mode requires a running, configured MouseMux V2 instance and must be validated on Windows hardware.

RemoteDesktop.CreateSession → SelectDevices(keyboard/pointer) → ScreenCast.SelectSources(one monitor) → Start. Requests subscribe before calls, wait cancellably, validate grants and dimensions, and close on failure. Notify input is used without EIS or root. The portal loop is pumped while idle to detect revocation. Window actions emulate the configured Super/Alt + mouse shortcut.

## Future AI / voice

`Action(kind, values)` supports release, pointer_at, left_down_at, right_click_at, begin_window, begin_resize, zoom, and legacy click_at/move. Unknown kinds fail closed. Future STT/AI must feed a validated arbiter before this single executor; never create a second uncontrolled producer of backend input. No microphone, AI provider, secret, or shell interpreter is included here.
