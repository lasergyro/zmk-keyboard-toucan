# Toucan Overlay

A minimal macOS menu-bar (tray) app that shows the current keymap render as a
floating **liquid-glass** overlay — handy while training on the layout.

* Lives in the menu bar (no Dock icon).
* Two **configurable global shortcuts**:
  * **Toggle** (default **⌥⌘K**) — show/hide the overlay.
  * **Hold to show** (default **⌥⌘L**) — the overlay is visible only while the
    keys are held, then hides on release (a pinned overlay stays put).
* Starts **hidden** — bring it up with the toggle shortcut or the menu. It
  first appears in the **top-right corner**, sized to ~a quarter of the screen.
  **Drag anywhere** to move it; **resize from the edges** with a locked aspect
  ratio. Nothing inside is selectable.
* **Start at Login** (menu toggle) registers the app with macOS via
  `SMAppService`, so it also shows up in System Settings › General › Login
  Items — flipping it there and in the menu stay in sync.
* Renders [`draw/keymap.svg`](../draw/keymap.svg), post-processed to **drop the
  bottom footer/watermark label** and make the background a semi-hazy frosted
  **liquid glass** (`NSGlassEffectView` on macOS 26+, falling back to
  `NSVisualEffectView`) so it floats unobtrusively over whatever you're typing
  in.
* **Costs ~11 MB idle.** The drawing is pre-rendered to a **vector PDF** at
  build time, so the running app is an image view — it never starts WebKit, and
  the window itself is only built the first time you show the overlay.
* The global hotkeys use Carbon `RegisterEventHotKey` — **no Accessibility
  permission required**.

## Build & run

Requires Xcode (uses the installed Swift toolchain).

```sh
cd overlay
./build.sh --run      # build ToucanOverlay.app and launch it
./build.sh            # just build
./build.sh --debug    # debug build
```

The script assembles `ToucanOverlay.app` (a proper `LSUIElement` bundle so the
status item behaves), copies the current `draw/keymap.svg` in as a fallback,
pre-renders it to `keymap.pdf` (`ToucanOverlay --render-pdf in.svg out.pdf`),
and ad-hoc signs the result.

## Menu

| Item | Action |
|------|--------|
| **Toggle Overlay** | show/hide the overlay (also the toggle shortcut) |
| **Hold to Show** | shows the current hold-to-show shortcut |
| **Reset Position (top-right)** | move it back to the default corner |
| **Reload Keymap** | re-read the SVG (after re-running `draw-keymap.sh`) |
| **Choose Keymap SVG…** | point at a different SVG file |
| **Set Toggle Shortcut…** | record a new toggle shortcut (needs a modifier) |
| **Set Hold-to-Show Shortcut…** | record a new hold-to-show shortcut (needs a modifier) |
| **Start at Login** | check to launch the app automatically when you log in |
| **Quit** | quit |

## Which SVG is shown?

Resolved in this order:

1. `TOUCAN_KEYMAP_SVG` environment variable, if set.
2. The path chosen via **Choose Keymap SVG…** (stored in `UserDefaults`).
3. Auto-discovered `draw/keymap.svg` by walking up from the app's location —
   so when `ToucanOverlay.app` lives inside this repo it tracks the **live**
   drawing. Re-run `../draw-keymap.sh` then **Reload Keymap** to refresh.
4. The copy bundled into the app at build time (fallback).

## How it's drawn

WebKit is the only renderer that gets the generated SVG right (the SVG support
in `NSImage` ignores most of keymap-drawer's stylesheet), but a resident
`WKWebView` costs three XPC helper processes — ~70 MB for a drawing that never
changes. So the SVG is rendered to a **vector PDF exactly once**, and the app
displays that: sharp at any window size and on any display, unlike a
pre-rendered bitmap, and ~60 KB instead of tens of MB.

The PDF comes from, in order: the copy `build.sh` rendered into the bundle → a
content-keyed cache in `~/Library/Caches/dev.toucan.overlay/` → a fresh render.
Only the last one needs WebKit, and it runs as a short-lived
`--render-pdf` **child process**, because WebKit's GPU and Networking helpers
outlive the web view that started them and would otherwise stay attached to the
menu-bar app for the rest of the session. In practice you hit it only after
changing the keymap without rebuilding the app — once per new drawing.

## Icon

The menu-bar glyph and the `.app` icon are both the **left half of the keymap**
outlines (`icon/`). Regenerate after a layout change:

```sh
./icon/build-icon.sh   # rewrites icon.svg, ToucanOverlay.icns, menu-bar template
```

`build.sh` copies `icon/ToucanOverlay.icns` into the bundle; the menu-bar
template (`Sources/ToucanOverlay/Resources/toucan-menubar.pdf`) ships as a
Swift-package resource.

## Notes

* Window position/size persist between launches, **per display** — each
  monitor remembers its own size and location (keyed by display UUID), so
  switching or reconnecting screens restores the right layout instead of
  landing off-screen. **Reset Position** re-centers on the current display.
* **Start at Login** registers the bundle at its current path, so re-enable it
  after moving `ToucanOverlay.app` (e.g. into `/Applications`). It's greyed out
  when the binary is run outside the `.app` bundle, since `launchd` has nothing
  to point at. If macOS marks the registration as needing approval, the app
  opens the Login Items pane for you.
* The post-processing (footer removal + transparent/liquid-glass background)
  lives in `Sources/ToucanOverlay/KeymapSVG.swift` and runs as part of the
  render, so it always reflects the latest generated keymap without a separate
  export step.
* Memory: ~11 MB with the overlay never shown, ~19 MB once it has been (the
  window's backing store). The panel is kept after the first show so toggling
  and hold-to-show stay instant.
