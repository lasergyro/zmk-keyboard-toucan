# ZMK config for beekeeb Toucan Keyboard

[The beekeeb Toucan Keyboard](https://beekeeb.com/toucan-keyboard/) is a wireless split 42-key column‑stagger keyboard with a display and a trackpad, featuring an aggressive stagger on the pinky columns.

## Firmware Features

**Touchpad Implementation**
The right half features a touchpad built on a centralized **modified absolute mode with a state machine**.
- Tap-to-click
- Primary and secondary click
- Click-and-drag via click followed by hard press
- Uninterrupted drag by lifting from edge 
- Scroll mode on the outer edge

**Text Output Modes**
Each USB/BLE endpoint keeps its own persisted text-output mode. New profiles default to `macOS Unicode`.
Leader sequences on the system prefix switch between `Linux Unicode`, `macOS Unicode`, `iOS Apple macros`.
This deals with system-dependent features, like Unicode output abilities and clipboard macros.


**Power Management & Sleep Mode**
The keyboard enters Deep Sleep automatically after 60 minutes of inactivity to conserve battery.
- To exit sleep mode, **you must press a physical key**. 
- Touching the touchpad will **not** wake the keyboard (the touchpad is suspended and not configured as a wakeup source).
- Because the halves sleep independently, if the entire keyboard has gone to sleep, you will need to press a key on **both** the left and right halves to fully wake the system.

## Development Workflow


### Git Operations with Submodules

This repository depends on Git submodules (e.g., `cirque-input-module`, `zmk`). When making changes, standard Git commands require a slightly modified workflow to ensure submodule states are tracked correctly:

1. **Check Status**: 
   ```bash
   git status
   ```
   *Note: This shows if a submodule has new commits or modified content. For a detailed status across all submodules, you can use `git submodule foreach 'git status'`.*

2. **Stage and Commit**:
   If you have modified files **inside** a submodule, you must commit them there first before committing to the main repo:
   ```bash
   cd external/cirque-input-module
   git add .
   git commit -m "Update submodule code"
   cd ../..
   ```
   After committing inside the submodule, stage the updated submodule pointer along with any other root repository changes:
   ```bash
   git add .
   ```
   Finally, commit the changes to the root repository:
   ```bash
   git commit -m "Your main repository commit message"
   ```

## Debug Cycle (Start Here)

### 1. Build Debug Firmware
```bash
./debug.sh build
```
Outputs to `artifacts/debug/`. Always use this for touchpad / overlay changes.

### 2. Flash Both Halves
```bash
# Flash both halves over USB RPC (both halves must be connected via USB)
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug both

# If one half is not detected, flash individually:
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug left
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug right
```

### 3. Verify Devices
```bash
./debug.sh devices
```
Expected: 4 lines — left rpc, left log, right rpc, right log.

### 4. Run Automated Tests
```bash
pkill -9 -f "python.*debug|debug.sh|pyserial" || true
python3 scripts/test_pad.py
```

### 5. Live Logs
```bash
./debug.sh logs both
./debug.sh logs right   # Pinnacle driver logs appear here
```
Logs saved to `debug-logs/<timestamp>-<side>-<port>.log`.

### Build Release Firmware
```bash
./build.sh && ARTIFACTS_DIR=artifacts/release ./upload.sh both
```

---

## Architecture

### Input Pipeline
```
Pinnacle (abs mode) → input_pinnacle.c (state machine)
  → emits: REL_X/REL_Y (cursor), REL_WHEEL (scroll), BTN_0/BTN_1 (clicks), BTN_TOUCH (layer)
  → glidepoint_split → glidepoint_listener
  → zip_behaviors (BTN_TOUCH → mo 4, PAD layer ON/OFF)
  → zip_xy_transform (X invert)
```

### Layers
| Index | Name | Activation | Physical Key (42-key) |
|-------|------|------------|-----------------------|
| 0 | BASE | Default | - |
| 1 | NAV | `&mo 1` | Left Thumb (Middle) |
| 2 | FN | `&mo 2` | Left Thumb (Outer) |
| 3 | PAD | `BTN_TOUCH` | Touchpad (automatic) |
| 4 | PAN | `&mo 4` | Held from Pad layer |

### Key Files
| File | Role |
|------|------|
| `external/cirque-input-module/drivers/input/input_pinnacle.c` | Pinnacle driver — state machine (git submodule, `toucan` branch) |
| `external/cirque-input-module/dts/bindings/input/cirque,pinnacle-common.yaml` | DTS binding for gesture params |
| `boards/shields/toucan/toucan.dtsi` | Input listener + processor chain |
| `boards/shields/toucan/toucan_right.overlay` | Pinnacle config + gesture param defaults |
| `boards/shields/toucan/toucan_right.conf` | `CONFIG_ZMK_POINTING`, stack sizes |
| `src/debug_rpc.c` | Debug RPC commands (get/set gesture params, persist to NVS) |
| `scripts/touchpad_params_live.py` | Live-tune: watches overlay, sends `set` RPC on save |
| `touchpad_state_machine.md` | Full state machine spec |
| [[config/toucan.keymap]] | Layer definitions and key bindings |
| [[config/combos.dtsi]] | Two-key combo definitions |
| [[config/leader.dtsi]] / [[config/leader_greek.dtsi]] | Leader sequences (SYS, German, Greek namespaces) |
| [[draw/config.yaml]] | Keymap visualization config (annotation positions, colors, binding labels) |
| [[references/generic_desktop.md]] | Generic Desktop HID usage page reference (e.g. System Do Not Disturb) |

---

## Keymap Structure

For exact key assignments, see the source files above. High-level structure:

- **Layers** — defined in [[config/toucan.keymap]]. See Architecture for indices.
- **Homerow mods** — timeless HRMs on the home row (GUI–ALT–SHIFT–CTRL, pinky to index, symmetric). Uses `MAKE_HRM` / `ZMK_HOLD_TAP` from zmk-helpers.
- **Combos** — two-key horizontal and vertical combos in `config/combos.dtsi`. Produce symbols, navigation shortcuts, and namespace-combo triggers.
- **Leader sequences** — three namespaces triggered by combo macros (`greek_ns`, `german_ns`, `sys_ns`). `&leader` is never invoked bare. See [[config/leader.dtsi]] and [[config/leader_greek.dtsi]] for sequences.
- **Visualization** — [[draw/config.yaml]] is the single source of truth for annotation slot positions and colors; `draw/generate-keymaps.rb` derives all layer/leader CSS from it. Run `./draw-keymap.sh` to regenerate [[draw/keymap.svg]].

---

## Hardware Notes

- **Driver runs on right half (peripheral).** `glidepoint@0` is only in `toucan_right.overlay`. All Pinnacle logs → `./debug.sh logs right`.
- **No physical buttons.** The Toucan has no buttons wired to the Pinnacle; `btn` is always 0. The button-loop in the driver is a no-op.
- **Z range: 0–31 (5 bits).** Typical touch: 15–30. Z=0 = no touch / idle packet. Z=0 is the only lift signal.
- **Z-idle packet mechanism.** After lift the chip sends `NUM_ZIDLE + NUM_ZIDLE_PAD = 5` packets with z=0, then goes quiet. `num_z_idle == NUM_ZIDLE (3)` is the debounced lift signal used by the state machine.
- **Scaled coordinate space: 0–1024, center (512, 512).** Raw X: 128–1920, raw Y: 64–1472. All gesture math operates in scaled space.
- **No `-lm` linking.** macOS Homebrew `arm-none-eabi-binutils` cannot find `libm.a`. Never use `zephyr_library_link_libraries(m)`. Use inline integer implementations (`atan2_16` from QMK).

---

## Gesture Params

All params live in `pinnacle_data.gesture_params` (RAM). DTS defaults are copied in at init and saved to Zephyr NVS settings on first boot; subsequent boots load from settings.

- **RPC commands** (right half only via `debug_rpc.c`, except `layers`):
  - `get` — read all params (single line: `OK get key=val ...`)
  - `set <param> <value>` — update param in RAM and persist to NVS
  - `layers` — query active layer bitmask (left/central only)


**Live tuning**: run `scripts/touchpad_params_live.py` — watches `toucan_right.overlay`, sends `set` RPC on save.

See `touchpad_state_machine.md` for the full param table and state machine spec.

---

## PAD Layer Activation

`zip_behaviors` maps `BTN_TOUCH → mo 4`. The state machine emits `BTN_TOUCH=1` on any INACTIVE→non-INACTIVE transition (immediate) and `BTN_TOUCH=0` after a `pad_off_timeout_ms` delay on →INACTIVE (deferred, cancelled if a new gesture starts). DRAG_WINDOW and DRAG_JUMP are non-INACTIVE, so PAD stays ON while any button is held.

```dts
zip_behaviors: zip_behaviors {
    compatible = "zmk,input-processor-behaviors";
    #input-processor-cells = <0>;
    codes = <INPUT_BTN_TOUCH>;
    bindings = <&mo 4>;
};
```

`zip_temp_layer` was rejected: it activates on any passing event and deactivates on an idle timeout — no event-toggled semantic.

---

## Target Feature Set (Implemented)

- **Tap-to-click** — quick tap → left click; tap in right-click zone → right click
- **Click-and-drag** — tap, lift, re-touch within `drag-window-timeout-ms` → button held while dragging
- **Force drag** — hard press (`z ≥ force-drag-z-threshold`) in TAP_PENDING or MOVING → immediate drag without tap-click cycle
- **Double-click drag** — re-touch in DRAG_WINDOW with `z ≥ double-click-drag-z-threshold` → drag; lighter touch cancels drag and returns to TAP_PENDING
- **Smart drag (DRAG_JUMP)** — brief lift near `drag-jump-rim-percent` edge during drag → DRAG_JUMP holds button; re-touch resumes drag
- **Circular scroll** — touch on outer `scroll-rim-percent` ring + circular motion → scroll wheel events (left/lower half → horizontal; upper/right → vertical)
- **Scroll exclusion band** — configurable y-band centred on pad middle (`scroll-exclusion-zone-percent`) prevents accidental scroll initiation
- **PAD layer** — ON while touchpad active, OFF after `pad-off-timeout-ms` idle

---

## Touchpad Testing Gotchas (Findings)

- **DRAG_JUMP Suppression on Lift**: If a test sequence lifts the touch (`Z=0`) while the X/Y coordinates are at the edge (rim) of the pad, the gesture engine will enter `DRAG_JUMP` mode (waiting 500ms for the finger to return). This suppresses the `INPUT_BTN_TOUCH=0` event until the timeout expires, causing `PAD layer off` assertions to fail. The qo command needs to wait at least that amount of time to be able to capture all the events before finishing its report, so change the qo command accordingly (e.g. to have a timeout that is reset every time an event is outputed).

---

## Recovery Procedures

1. **Full Reset**: `./upload.sh reset`
2. **Physical Reset**: Double-tap RST on each XIAO → bootloader → drop UF2 manually.
3. **Touchpad First**: Right half owns Pinnacle hardware — flash it first if pad dies.

**BLE vs USB**: ZMK routes mouse events over USB when plugged in. Unplug after flashing to test BLE behavior.

---

## First time setup:

### macOS — Removable Volume Access

When flashing UF2 firmware to devices (e.g. XIAO nRF52840 in bootloader mode), macOS requires explicit UI authorization before the AI assistant can access newly-mounted removable volumes. The volume may appear in `/Volumes/` but `cp` or other write operations will silently fail or appear to hang until the user approves the access prompt. Permission after given will be persistent.

**What this looks like in practice:** The UF2 bootloader volume (e.g. `/Volumes/XIAO-BOOT`) mounts correctly, but the `cp` command blocks or fails until macOS shows the user a permission dialog. The user must approve it for the copy to proceed.

## License

The code in this repo is available under the MIT license.

The included shield nice_view_gem is modified from https://github.com/M165437/nice-view-gem licensed under the MIT License.
ZMK code snippets are taken from the ZMK documentation under the MIT license.
The embedded font QuinqueFive is designed by GGBotNet, licensed under the SIL Open Font License, Version 1.1.
