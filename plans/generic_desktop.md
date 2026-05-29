# Generic Desktop HID Usage Page

According to the [USB HID Usage Tables (HUT) Version 1.5](../references/hut1_5.pdf), the Generic Desktop usage page (0x01) defines controls for the system, such as sleep, power, and do not disturb.

## System Do Not Disturb (DND)
- **Usage Page**: 0x01 (Generic Desktop)
- **Usage ID**: 0x9B (System Do Not Disturb)
- **Control Type**: OOC (On/Off Control) or OSC (One Shot Control)
- **Description**: Toggle system-wide Do Not Disturb (DND) mode On/Off. 

### Integration with ZMK
To support this in ZMK:
1. A new HID report ID `ZMK_HID_REPORT_ID_GENERIC_DESKTOP` needs to be defined in `app/include/zmk/hid.h`.
2. The HID descriptor `zmk_hid_report_desc` needs to be updated to include the Generic Desktop usage page and the `System Do Not Disturb` control.
3. The HID event mapping and ZMK behavior must map a custom ZMK behavior (e.g., `SYS_DND`) to emit this HID code.
4. The key needs to be bound to the keyboard map (`toucan.dtsi` or `toucan_right.keymap`).

For a reference implementation on adding generic desktop controls to ZMK, see [ZMK PR 2473](https://github.com/zmkfirmware/zmk/pull/2473) or the local patch file [pr2473.patch](../references/pr2473.patch).
