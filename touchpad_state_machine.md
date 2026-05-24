
## Touchpad State Machine (Target)

### State Enum

```c
enum pinnacle_gesture_state {
    PINNACLE_STATE_INACTIVE,
    PINNACLE_STATE_TAP_PENDING,
    PINNACLE_STATE_MOVING,
    PINNACLE_STATE_DRAG_WINDOW,
    PINNACLE_STATE_DRAGGING,
    PINNACLE_STATE_DRAG_JUMP,
    PINNACLE_STATE_SCROLL_ACTIVE,
    PINNACLE_STATE_SCROLL_DEAD,
};
```

### State Parameters

| Parameter | Type | Relevant states | Meaning |
|-----------|------|-----------------|---------|
| `is_left` | bool | TAP_PENDING, DRAG_WINDOW, DRAGGING, DRAG_JUMP | true = left-click gesture; false = right-click gesture |
| `scroll_direction` | enum | SCROLL_ACTIVE, SCROLL_DEAD | HORIZONTAL or VERTICAL — set at touch-start, kept through dead zone |

### State Summary

| State | Finger down? | Button held? | PAD layer |
|-------|-------------|--------------|-----------|
| INACTIVE | no | no | OFF |
| TAP_PENDING | yes | no | ON |
| MOVING | yes | no | ON |
| DRAG_WINDOW | no | yes | ON |
| DRAGGING | yes | yes | ON |
| DRAG_JUMP | no | yes | ON |
| SCROLL_ACTIVE | yes | no | ON |
| SCROLL_DEAD | yes | no | ON |

**PAD layer rule**: ON on any INACTIVE → non-INACTIVE transition (`BTN_TOUCH=1`, immediate); OFF is **deferred** — `BTN_TOUCH=0` is scheduled `pad_off_timeout_ms` (default 200 ms) after entering INACTIVE. If a new gesture starts within that window the timer is cancelled and the layer stays ON, avoiding a brief flicker. Implemented via `zip_behaviors` mapping `BTN_TOUCH → mo 4` (ZMK Momentary Layer).

"Finger down" ≡ `state ∉ {INACTIVE, DRAG_WINDOW, DRAG_JUMP}`.  
"In scroll mode" ≡ `state ∈ {SCROLL_ACTIVE, SCROLL_DEAD}`.

### Coordinate System Note

Hardware x increases from **right to left** (x=0 = physical right, x=1024 = physical left). Y-invert is enabled in hardware. All zone conditions below are in scaled 0–1024 space after these inversions.

### Zone Classification (at touch-start, in scaled 0–1024 space)

| Zone | Condition | Enters | `is_left` set |
|------|-----------|--------|--------------|
| Rim | `dist_sq(pos, center) > SCROLL_RIM_SQ` AND `x > PAD_CENTER` (left half only) | SCROLL_ACTIVE | — |
| Secondary (right-click) | `x ≤ X_RCLICK_MIN` | TAP_PENDING | false |
| Primary | `x > X_RCLICK_MIN` | TAP_PENDING | true |


Rim is checked first. Right half of the pad (`x ≤ PAD_CENTER`) is never scroll-initiating — it always enters TAP_PENDING, making right-click easy to activate.

**Scroll direction** (set at INACTIVE → SCROLL_ACTIVE):
- `y > PAD_CENTER` (lower half) → HORIZONTAL (`INPUT_REL_HWHEEL`)
- `y ≤ PAD_CENTER` (upper half) → VERTICAL (`INPUT_REL_WHEEL`)

Constants: X_RCLICK_MIN=300; PAD_CENTER=512
### Touch-End Rule (common)

`num_z_idle == NUM_ZIDLE` (3 consecutive z=0 packets ≈ 30ms at 100Hz) signals lift. This condition triggers any state's 'lift' transition below. It is not repeated per transition. Equally, 'contact' means z>0.

### Key Transitions

**INACTIVE → TAP_PENDING** (contact, not rim OR right half):  
Set `is_left` per zone table, save `touch_start_x/y`, set `prev_scaled_x/y` to touch position, schedule `tap_timeout(120ms)`, emit `BTN_TOUCH=1`.

**INACTIVE → SCROLL_ACTIVE** (contact, scroll rim zone AND x > 512):  
Record `scroll_ref_x/y`, reset `scroll_clicks_rem`, set `scroll_direction` (y > PAD_CENTER → HORIZONTAL, else VERTICAL), emit `BTN_TOUCH=1`.

---

**TAP_PENDING → MOVING** (`tap_timeout` fires, contact):  
Enter MOVING immediately. Snap behaviour is controlled by the `tap-snap` DTS property (default: **off**):
- **off** (default): `prev_scaled` stays at `touch_start`, so the first MOVING packet emits the delta accumulated while pending.
- **on**: `prev_scaled` is snapped to the current finger position, discarding the pending delta; cursor movement starts from zero.

`is_left` no longer relevant after this transition.

**TAP_PENDING → DRAG_WINDOW** (`tap_timeout` fires, lift):  
Emit button-down (`is_left ? BTN_0 : BTN_1` = 1), schedule `drag_window_timeout(300ms)`.

---

**MOVING → INACTIVE** (lift):  
Emit `BTN_TOUCH=0`.

---

**TAP_PENDING → DRAGGING** (`z >= force_drag_z_threshold`, contact):  
Hard press detected while pending — cancel `tap_timeout`, emit button-down (`is_left ? BTN_0 : BTN_1` = 1, sync), snap `prev_scaled_x/y` to current. Skip DRAG_WINDOW entirely.

**MOVING → DRAGGING** (`z >= force_drag_z_threshold`, contact):  
Hard press while cursor-moving — `is_left` forced true (always left), emit `BTN_0=1` (sync), snap `prev_scaled_x/y` to current. Once in DRAGGING, z drops do not exit the state.

---

**DRAG_WINDOW → DRAGGING** (contact AND `z >= double_click_drag_z_threshold`):  
Tap-then-retouch: snap `prev_scaled_x/y` to new touch position. Cancel `drag_window_timeout`.

**DRAG_WINDOW → TAP_PENDING** (contact AND `z < double_click_drag_z_threshold`):  
Light touch — cancel drag: emit button-up (`is_left ? BTN_0 : BTN_1` = 0, sync), cancel `drag_window_timeout`, recompute `is_left` from new touch position, save `touch_start_x/y`, set `prev_scaled_x/y`, schedule `tap_timeout(120ms)`. PAD stays ON (no BTN_TOUCH change).

**DRAG_WINDOW → INACTIVE** (`drag_window_timeout` fires):  
Emit button-up (`is_left ? BTN_0 : BTN_1` = 0, sync), emit `BTN_TOUCH=0`.

---

**DRAGGING → DRAG_JUMP** (lift AND `dist_sq(prev_scaled, center) > DRAG_JUMP_RIM_SQ`):  
Finger lifted near edge — schedule `drag_jump_timeout(500ms)`. Button stays held, PAD stays ON.

**DRAGGING → INACTIVE** (lift AND `dist_sq(prev_scaled, center) ≤ DRAG_JUMP_RIM_SQ`):  
Finger lifted in center — drag intentionally ended: emit button-up (sync), emit `BTN_TOUCH=0`.

---

**DRAG_JUMP → DRAGGING** (contact):  
Snap `prev_scaled_x/y` to new touch position. Cancel `drag_jump_timeout`.

**DRAG_JUMP → INACTIVE** (`drag_jump_timeout` fires):  
Emit button-up (`is_left ? BTN_0 : BTN_1` = 0, sync), emit `BTN_TOUCH=0`.

---

**SCROLL_ACTIVE → SCROLL_DEAD** (`dist_sq(pos, center) < DEAD_ZONE_SQ`):  
Finger entered dead zone — suppress scroll events. `scroll_direction` retained.

**SCROLL_ACTIVE → INACTIVE** (lift):  
Reset `scroll_clicks_rem`, emit `BTN_TOUCH=0`.

**SCROLL_DEAD → SCROLL_ACTIVE** (`dist_sq(pos, center) ≥ DEAD_ZONE_SQ`):  
Finger exited dead zone — reset `scroll_ref_x/y` to current position, resume scrolling with same `scroll_direction`.

**SCROLL_DEAD → INACTIVE** (lift):  
Emit `BTN_TOUCH=0`.

---

### Events Emitted During States (per z>0 packet)

| State | Events emitted | Notes |
|-------|---------------|-------|
| MOVING | `INPUT_REL_X`, `INPUT_REL_Y` (delta from `prev_scaled`) | first packet emits delta from touch_start |
| DRAGGING | `INPUT_REL_X`, `INPUT_REL_Y` (delta from `prev_scaled`) | button held |
| TAP_PENDING | *(suppressed)* | delta accumulates in `prev_scaled` from touch_start |
| SCROLL_ACTIVE | `INPUT_REL_WHEEL` (VERTICAL) or `INPUT_REL_HWHEEL` (HORIZONTAL) | via `atan2_16` + `scroll_clicks_rem` |
| SCROLL_DEAD | *(suppressed)* | scroll_direction retained for resume |
| DRAG_WINDOW, DRAG_JUMP, INACTIVE | *(no touch, no packet)* | |

### Timer Values

All timers are configurable via DTS properties on the `cirque,pinnacle` node.

| Timer | DTS property | Default | Notes |
|-------|-------------|---------|-------|
| `tap_timeout` | `tap-timeout-ms` | 120 ms | debounce: finger-down must last this long before registering |
| `drag_window_timeout` | `drag-window-timeout-ms` | 300 ms | tap-to-drag: window between lift and re-touch |
| `drag_jump_timeout` | `drag-jump-timeout-ms` | 500 ms | smart drag: window for crossing pad and re-touching |
| `pad_off` | `pad-off-timeout-ms` | 200 ms | delay before `BTN_TOUCH=0`; cancelled if new gesture starts |
| `zip_behaviors` (`mo 4`) | — | immediate | `BTN_TOUCH=1` → layer ON; `BTN_TOUCH=0` → layer OFF (on `pad_off` fire) |

### Thresholds

All thresholds are configurable via DTS properties on the `cirque,pinnacle` node.

| DTS property | Default | Computed value | Purpose |
|-------------|---------|---------------|---------|
| `scroll-rim-percent` | 67 % | 343 (= 512 × 67 / 100) | Scroll-zone rim radius (INACTIVE: touch outside → SCROLL_ACTIVE) |
| `drag-jump-rim-percent` | 67 % | 343 (= 512 × 67 / 100) | Drag-jump rim radius (DRAGGING: lift outside → DRAG_JUMP) |
| `dead-radius-percent` | 20 % | 102 (= 512 × 20 / 100) | Scroll dead-zone radius |
| `rclick-x-min-percent` | 29 % | ≈ 297 (= 1024 × 29 / 100) | x ≤ this → right-click zone |
| `force-drag-z-threshold` | 27 | — | Min z for hard-press force-drag: TAP_PENDING→DRAGGING and MOVING→DRAGGING |
| `double-click-drag-z-threshold` | 20 | — | Min z for tap-then-retouch drag: DRAG_WINDOW→DRAGGING (can be lighter) |
| `scroll-exclusion-zone-percent` | 10 % | ≈ 51 units (= 1024 × 10 / 100 / 2) | Half-height of centered y-band that blocks scroll initiation; finger in band enters TAP_PENDING instead |
| `wheel-clicks` | 18 | — | Scroll clicks per full revolution |

### Optional Snap (TAP_PENDING → MOVING)

| DTS property | Default | Behaviour |
|-------------|---------|-----------|
| `tap-snap` | false (unset) | Keep `prev_scaled` at `touch_start`; first MOVING packet emits accumulated delta |
| `tap-snap` | true | Snap `prev_scaled` to current position on MOVING entry; delta starts at zero |