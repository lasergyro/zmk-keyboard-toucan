# Theory on test_tap_and_drag failure

**Context**
- `test_double_click` is passing, which means it correctly records two down/up cycles for `btn=1`.
- `test_tap_and_drag` is failing. Its trace dump is:
  `['B,269,1,1', 'B,60,1,0', 'M,496,-18,0', 'M,1,-69,0', 'M,5,-69,0']`

**Observation 1:**
The button release (`B,60,1,0`) happens exactly 60ms after the first press (`B,269,1,1`). This `60ms` precisely matches the `tap_click_work` delay! So `B,269,1,1` is the FIRST tap's button press, and `B,60,1,0` is the FIRST tap's release.

**Observation 2:**
The SECOND tap's button press is completely missing. Why? Because the `test_tap_and_drag` wait time between taps was changed to 300ms, which exceeds the right half's `drag_window_timeout_ms` (defaults to 150ms). Since the wait time exceeded the window, the second tap was treated as a completely new touch. And since its Z value (20) was less than `force_drag_z_threshold` (30), it fell into the `PINNACLE_STATE_MOVING` state, which does not emit any button clicks.

**The Core Firmware Bug (When wait_time < drag_window_timeout_ms):**
If a user performs a double tap or tap-and-drag very quickly, the second tap enters `PINNACLE_STATE_DRAGGING_PENDING` and immediately emits `btn=1`. However, the `tap_click_work` scheduled by the *first* tap's release is still running (scheduled for 60ms in the future). When `tap_click_work` fires, it emits `btn=0`, **canceling the button hold of the second tap/drag**. 
This is why the original test failed with "0 downs, 0 ups, 3 moves": the drag's button press was instantly canceled by the first tap's delayed release.

**Solution:**
We must decouple the second tap's button emission from the state transition to `DRAGGING_PENDING`.
1. **In `DRAG_WINDOW` -> `DRAGGING_PENDING`**: Do *not* emit `btn=1`. Let the state machine wait.
2. **In `drag_pending_timeout_cb` (Tap-and-Drag)**: When the timeout fires (e.g. 150ms later), `tap_click_work` (60ms) will have already fired, ensuring the first tap was cleanly released. Here we transition to `DRAGGING` and emit `btn=1` for the drag.
3. **In `DRAGGING_PENDING` -> Lift (Double Click)**: If the finger lifts before the timeout, we must emit the second click. We emit `btn=1` and schedule `tap_click_work` to emit `btn=0`. Since human double clicks take >100ms, the first tap's 60ms work will have already fired.

This perfectly resolves the overlapping button state issues without needing complex queueing logic.

## Test Script Flaws and Fixes

While debugging `test_tap_and_drag`, another crucial layer of complexity was discovered regarding the test environment itself:

**Observation 3: Dropped Lift Events due to BLE Queue Overflows**
The test scripts were injecting touch events (`qi/qo` commands) into the **left** (central) half of the keyboard. The left half would then send these events over BLE to the right half. A tap scenario queues 5 events instantly:
1. `z=20` (down)
2. `z=20` (wait)
3. `z=0` (lift)
4. `z=0` (debounce)
5. `z=0` (debounce)

Because these were all queued instantly on the left side, the BLE batching mechanism filled up, and the latter events (crucially, the `z=0` lift event) were dropped. This caused the state machine on the right side to get "stuck" in `TAP_PENDING`, assuming the finger was still held down, and eventually transitioning to `MOVING` (breaking the tap sequence).

**The Solution:**
1. Inject the `qi/qo` commands directly into the **right** half's RPC session. This is where the physical trackpad logic runs, so injecting locally bypasses the BLE transmission bottleneck entirely.
2. Send the `hid trace on` / `hid trace off` commands to the **left** half's RPC session, because the left side acts as the central USB HID device.
3. Manage the timing carefully: after the right half finishes executing the `qo` command, the left half must sleep for `0.5s` before stopping the `hid trace`, to allow all BLE batched events to arrive from the right side.

The tests have now been successfully decoupled to use dual RPC sessions (`rpc_right` and `rpc_left`), split into multiple granular files in `tests/pad/`, and executed via `tests/run_pad_tests.py`.
