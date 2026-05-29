# Debugging Deep Sleep Wake-Up on Toucan

The current issue is that the keyboard does not wake up from deep sleep when physical keys are pressed.

## Background Context: ZMK Sleep Modes Explained

ZMK has distinct power-saving states. Understanding these is key to fixing the wake-up issue:

1. **Idle State (`CONFIG_ZMK_IDLE_TIMEOUT`)**
   - **What it does:** The keyboard stops scanning the matrix at full speed and turns off non-essential peripherals (like displays or RGB) to save active power. The CPU **remains running**, and any keypress immediately resumes full operation.
   - **Current Timeout:** `30000` (30 seconds). As noted in your configs, this drops the touchpad power consumption significantly.
   
2. **Deep Sleep (`CONFIG_ZMK_SLEEP=y` & `CONFIG_ZMK_IDLE_SLEEP_TIMEOUT`)**
   - **What it does:** The microcontroller enters **System OFF** mode. The CPU, clocks, and USB are completely powered down. The only way to wake the device is a hardware GPIO trigger (a physical keypress connecting a row and column), which causes the microcontroller to perform a hard reset and boot back up.
   - **Current Timeout:** `3600000` (60 minutes).

3. **Soft Off (`CONFIG_ZMK_PM_SOFT_OFF=y`)**
   - **What it does:** This is essentially a manual "off switch". It allows a user to press a specific key combination to immediately force the keyboard into System OFF.
   - **The Catch:** Soft Off is designed to keep the keyboard off until a specific, dedicated hardware button is pressed. When triggered (or sometimes when just enabled), it explicitly disables the normal keyboard matrix wake-up sources. 
   - **Current Timeout:** None. It is meant to be triggered manually. Since your keymap has no `&soft_off` binding, having this config enabled provides no benefit and is highly likely to be conflicting with the Deep Sleep wake-up logic.

**Why we can't use RPC to queue inputs for this:**
Because Deep Sleep (System OFF) completely powers down the CPU and USB, the RPC listener is not running. We cannot simulate a wake-up using software commands. We must test it using physical key presses.

## Addressing Flashing Concerns

**Q: If we set deep sleep to start after 15s, could we run into issues keeping the system awake long enough to flash a new version of the firmware?**
**A: No, you will not have any issues.** Flashing firmware on the Seeed Studio XIAO BLE requires double-tapping the physical reset button. Doing so boots the microcontroller into a dedicated hardware bootloader (the UF2 drive). This bootloader runs completely independent of ZMK and does not respect ZMK's sleep timeouts. It will stay awake indefinitely waiting for the firmware file. 

## Proposed Debugging Steps

To isolate why the hardware SENSE is failing to trigger, we can implement the following plan to make physical testing rapid and observable.

### 1. Rapid Sleep Testing Configurations
We will temporarily modify the configuration files (`toucan_left.conf` and `toucan_right.conf`) to drastically reduce the sleep timeout. This will allow you to quickly test whether physical keypresses are waking the device without waiting an hour.
- Set `CONFIG_ZMK_IDLE_SLEEP_TIMEOUT=15000` (15 seconds).
- Set `CONFIG_ZMK_IDLE_TIMEOUT=5000` (5 seconds).

### 2. Remove Potential `SOFT_OFF` Conflicts
In your `toucan_left.conf` and `toucan_right.conf`, `CONFIG_ZMK_PM_SOFT_OFF=y` is enabled. We will temporarily disable this. Since `CONFIG_ZMK_SLEEP=y` already provides the necessary power management APIs required by the Cirque driver, `SOFT_OFF` is functionally redundant and likely disabling the matrix wake-up sources.

### 3. Verification Plan
After flashing the debug firmware with these changes, we can verify the behavior:
1. Connect the left half via USB and run `./debug.sh logs left` to monitor the serial output.
2. Wait 15 seconds for the keyboard to enter deep sleep. (You should see `sys_poweroff()` logged, and the USB connection will drop).
3. Physically press a key on the left half.
4. If the fix is successful, the USB will reconnect, and the log will show the device booting up (with Zephyr logging the `RESETREAS` register indicating a wake from System OFF).

## User Review Required

> [!IMPORTANT]
> Does this clarify the sleep modes and alleviate concerns about the 15-second timeout? If you approve, I will make these config changes, build the debug firmware, and you can test the physical wake-up behavior.
