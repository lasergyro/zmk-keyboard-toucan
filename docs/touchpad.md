
# Touchpad specific notes

## Input Pipeline
```
Pinnacle (abs mode) → input_pinnacle.c (state machine)
  → emits: REL_X/REL_Y (cursor), REL_WHEEL (scroll), BTN_0/BTN_1 (clicks), BTN_TOUCH (layer)
  → glidepoint_split → glidepoint_listener
  → zip_behaviors (BTN_TOUCH → mo 4, PAD layer ON/OFF)
  → zip_xy_transform (X invert)
```

## Key Files
| File | Role |
|------|------|
| [external/cirque-input-module/drivers/input/input_pinnacle.c](../external/cirque-input-module/drivers/input/input_pinnacle.c) | Pinnacle driver — state machine (git submodule, `toucan` branch) |
| `external/cirque-input-module/dts/bindings/input/cirque,pinnacle-common.yaml` | DTS binding for gesture params |
| [boards/shields/toucan/toucan_right.overlay](../boards/shields/toucan/toucan_right.overlay) | Pinnacle config + gesture param defaults |
| [boards/shields/toucan/toucan_right.conf](../boards/shields/toucan/toucan_right.conf) | `CONFIG_ZMK_POINTING`, stack sizes |
| [scripts/touchpad_params_live.py](../scripts/touchpad_params_live.py) | Live-tune: watches overlay, sends `set` RPC on save |
| [touchpad_state_machine.md](touchpad_state_machine.md) | Full state machine spec |
---

## Hardware Notes

- **Driver runs on right half (peripheral).** `glidepoint@0` is only in `toucan_right.overlay`. All Pinnacle logs → `./debug.sh logs right`.
- **No physical buttons.** The Toucan has no buttons wired to the Pinnacle; `btn` is always 0. The button-loop in the driver is a no-op.
- **Z range: 0–31 (5 bits).** Typical touch: 15–30. Z=0 = no touch / idle packet. Z=0 is the only lift signal.
- **Z-idle packet mechanism.** After lift the chip sends `NUM_ZIDLE + NUM_ZIDLE_PAD = 5` packets with z=0, then goes quiet. `num_z_idle == NUM_ZIDLE (3)` is the debounced lift signal used by the state machine.
- **Scaled coordinate space: 0–1024, center (512, 512).** Raw X: 128–1920, raw Y: 64–1472. All gesture math operates in scaled space.
- **AXIS ORIENTATION (CRITICAL):** The X-axis increases from right to left! `x=0` is the physical right edge, and `x=1024` is the physical left edge. This means right-click zones are checked with `x < rclick_x_min`.
- **No `-lm` linking.** macOS Homebrew `arm-none-eabi-binutils` cannot find `libm.a`. Never use `zephyr_library_link_libraries(m)`. Use inline integer implementations (`atan2_16` from QMK).

## Gesture Params

All params live in `pinnacle_data.gesture_params` (RAM). DTS defaults are copied in at init and saved to Zephyr NVS settings on first boot; subsequent boots load from settings.

- **RPC commands** (right half only via `debug_rpc.c`, except `layers`):
  - `get` — read all params (single line: `OK get key=val ...`)
  - `set <param> <value>` — update param in RAM and persist to NVS
  - `layers` — query active layer bitmask (left/central only)


**Live tuning**: run [scripts/touchpad_params_live.py](../scripts/touchpad_params_live.py) — watches `toucan_right.overlay`, sends `set` RPC on save.

See [touchpad_state_machine.md](touchpad_state_machine.md) for the full param table and state machine spec.

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

## Target Feature Set (Implemented)

- **Tap-to-click** — quick tap → left click; tap in right-click zone → right click
- **Click-and-drag** — tap, lift, re-touch within `drag-window-timeout-ms` → button held while dragging
- **Force drag** — hard press (`z ≥ force-drag-z-threshold`) in TAP_PENDING or MOVING → immediate drag without tap-click cycle
- **Double-click drag** — re-touch in DRAG_WINDOW with `z ≥ double-click-drag-z-threshold` → drag; lighter touch cancels drag and returns to TAP_PENDING
- **Smart drag (DRAG_JUMP)** — brief lift near `drag-jump-rim-percent` edge during drag → DRAG_JUMP holds button; re-touch resumes drag
- **Circular scroll** — touch on outer `scroll-rim-percent` ring + circular motion → scroll wheel events (left/lower half → horizontal; upper/right → vertical)
- **Scroll exclusion band** — configurable y-band centred on pad middle (`scroll-exclusion-zone-percent`) prevents accidental scroll initiation
- **PAD layer** — ON while touchpad active, OFF after `pad-off-timeout-ms` idle

## Touchpad Testing Gotchas (Findings)

- **DRAG_JUMP Suppression on Lift**: If a test sequence lifts the touch (`Z=0`) while the X/Y coordinates are at the edge (rim) of the pad, the gesture engine will enter `DRAG_JUMP` mode (waiting 500ms for the finger to return). This suppresses the `INPUT_BTN_TOUCH=0` event until the timeout expires, causing `PAD layer off` assertions to fail. The qo command needs to wait at least that amount of time to be able to capture all the events before finishing its report, so change the qo command accordingly (e.g. to have a timeout that is reset every time an event is outputed).

