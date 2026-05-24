# Toucan Development Plan & Agent Reference

---

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

### Layers: BASE=0, NAV=1, FN=2, NUM=3, PAD=4, PAN=5

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
| `config/toucan.keymap` | Layer definitions and key bindings |
| `config/combos.dtsi` | Two-key combo definitions |
| `config/leader.dtsi` / `config/leader_greek.dtsi` | Leader sequences (SYS, German, Greek namespaces) |
| `draw/config.yaml` | Keymap visualization config (annotation positions, colors, binding labels) |

---

## Keymap Structure

For exact key assignments, see the source files above. High-level structure:

- **Layers** — defined in `config/toucan.keymap`. Six layers: BASE, NAV, FN, NUM, PAD, PAN.
- **Homerow mods** — timeless HRMs on the home row (GUI–ALT–SHIFT–CTRL, pinky to index, symmetric). Uses `MAKE_HRM` / `ZMK_HOLD_TAP` from zmk-helpers.
- **Combos** — two-key horizontal and vertical combos in `config/combos.dtsi`. Produce symbols, navigation shortcuts, and namespace-combo triggers.
- **Leader sequences** — three namespaces triggered by combo macros (`greek_ns`, `german_ns`, `sys_ns`). `&leader` is never invoked bare. See `config/leader.dtsi` and `config/leader_greek.dtsi` for sequences.
- **Visualization** — `draw/config.yaml` is the single source of truth for annotation slot positions and colors; `draw/generate-keymaps.rb` derives all layer/leader CSS from it. Run `./draw-keymap.sh` to regenerate `draw/keymap.svg`.

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

**RPC commands** (right half only via `debug_rpc.c`):
- `get` — read all params (single line: `OK get key=val ...`)
- `set <param> <value>` — update param in RAM and persist to NVS

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

## Roadmap

### Completed
- Round 1: Touchpad gesture implementation — state machine, smart drag, force drag, persistent params, live tuning.
- Round 2: Leader key — German umlauts, Greek characters, SYS namespace (BT, output modes, studio, reset, boot). Modules: `zmk-leader-key`, `zmk-unicode`.
- Round 3: Combos, HRMs, layer restructure — six layers (BASE/NAV/FN/NUM/PAD/PAN), timeless homerow mods, two-key symbol/nav combos, namespace combo mechanism, schematic drawer refactor.

### Deferred
- Gaming layer, Swapper/Alt-Tab, extended Unicode sets
- Testing infrastructure (`pad_qi`/`pad_qo` synthetic tests, `rstart`/`rend` real-world traces) — see `rpc.md`

---

## Recovery Procedures

1. **Full Reset**: `./upload.sh reset`
2. **Physical Reset**: Double-tap RST on each XIAO → bootloader → drop UF2 manually.
3. **Touchpad First**: Right half owns Pinnacle hardware — flash it first if pad dies.

**BLE vs USB**: ZMK routes mouse events over USB when plugged in. Unplug after flashing to test BLE behavior.
