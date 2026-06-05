# BLE Generic Desktop (DND) Investigation & Debugging

## Objective
Investigate and resolve why the `SYS_DND` (Do Not Disturb) keycode was not functioning correctly over Bluetooth, despite working over the USB debug bridge.

## Findings
1. **ZMK Native Support**: The Zephyr Mechanical Keyboard (ZMK) firmware already has full native support for Generic Desktop reports over BLE. The `generic_desktop_input` report descriptor (which includes `SYS_DND`, Usage 0x9B) is properly implemented in `external/zmk/app/src/hog.c` and correctly routed in `endpoints.c`.
2. **The Real Issue**: The testing failure was caused by the dual-connection state during debugging. When connected via USB, ZMK prefers USB. Forcing the transport via `out ble` changes the preferred transport, but ZMK performs a safety check (`is_ble_ready()`). If the *currently active BLE profile* on the keyboard is not actively connected to a host, ZMK falls back to USB silently. Because the Mac was paired to a different profile or the bond was stale, the `out ble` command did not actually switch the output, leading the tests to falsely report that BLE DND was failing.

## Work Completed
1. **Test Infrastructure Organization**: 
   - Moved compiled C test binaries and sources (`listen_all`, `listen_dnd`) out of the repository root and into `tests_c/`.
   - Moved root-level Python Bluetooth scripts (`test_ble.py`, `scan_ble.py`, `test_focus.py`) into `tests/ble/`.
2. **Automated Testing**:
   - Created `tests/pad/test_ble_dnd.py` to automate testing by switching to BLE, tapping the DND keycode, capturing the event on macOS, and restoring the transport to USB.
   - Created `tests/pad/force_pair_and_test.py` to script the unpairing and repairing process using `blueutil` to guarantee an active connection before testing.
3. **Debug RPC Enhancements**:
   - Added `out <usb|ble>` command to manually override the preferred transport.
   - Added `ble clear` command to wipe all Bluetooth pairing bonds on the keyboard from the terminal, bypassing the need for a dedicated physical key.
   - Added `ble next` and `ble prev` commands to switch between BLE profiles.
   - Added `ble status` command to print the currently active profile index and its connection status.

## Next Steps / Takeaways
- Always ensure the correct BLE profile is active and connected (verify with `ble status`) before trusting that `out ble` has switched the transport.
- When iterating on GATT characteristics or HID report descriptors, stale caching on macOS may require clearing bonds on the board (`ble clear`) and "Forgetting" the device in macOS settings.
