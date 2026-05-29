# ZMK config for beekeeb Toucan Keyboard

[The beekeeb Toucan Keyboard](https://beekeeb.com/toucan-keyboard/) is a wireless split 42-key column‑stagger keyboard with a display and a trackpad, featuring an aggressive stagger on the pinky columns.

## Overview

### Firmware Features

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


### Keymap Structure

For exact key assignments, see  "Config Files".

- **Layers** — defined in [[config/toucan.keymap]]. See Architecture for indices.
- **Homerow mods** — timeless HRMs on the home row (GUI–ALT–SHIFT–CTRL, pinky to index, symmetric). Uses `MAKE_HRM` / `ZMK_HOLD_TAP` from zmk-helpers.
- **Combos** — two-key horizontal and vertical combos in `config/combos.dtsi`. Produce symbols, navigation shortcuts, and namespace-combo triggers.
- **Leader sequences** — three namespaces triggered by combo macros (`greek_ns`, `german_ns`, `sys_ns`). `&leader` is never invoked bare. See [[config/leader.dtsi]] and [[config/leader_greek.dtsi]] for sequences.
- **Visualization** — [[draw/config.yaml]] is the single source of truth for annotation slot positions and colors; `draw/generate-keymaps.rb` derives all layer/leader CSS from it. Run `./draw-keymap.sh` to regenerate [[draw/keymap.svg]].


### Keymap Visualization

Keymap visualization config (annotation positions, colors, binding labels) in [[draw/config.yaml]].

### Repository Structure

- `artifacts/`: Build outputs (`.uf2` firmware binaries) for release and debug targets.
- `boards/`: Shield definitions, devicetree overlays, and Kconfig options for the Toucan and displays.
- `config/`: The core ZMK keymap, combos, macros, and leader sequence definitions.
- `debug-logs/`: Destination for serial and RPC logs captured via `./debug.sh logs`.
- `draw/`: Configuration and scripts to generate the SVG keymap using `keymap-drawer`.
- `dts/`: Custom Devicetree bindings.
- `external/`: Git submodules for ZMK, Cirque input drivers, and other helper modules.
- `include/`: C header files for custom RPC interfaces and ZMK behaviors.
- `plans/`: Archived development plans, roadmaps, and AI agent artifacts.
- `references/`: Reference material, datasheets, and HID usage tables.
- `scripts/`: Utility shell scripts and Python tools for live tuning and RPC communication.
- `src/`: Custom C source code implementing RPC endpoints, behaviors, and ZMK Studio integration.
- `tests/`: Python-based automated gesture pipeline and RPC tests.

## Development Workflow

### First time setup:

#### macOS — Removable Volume Access

When flashing UF2 firmware to devices (e.g. XIAO nRF52840 in bootloader mode), macOS requires explicit UI authorization before the AI assistant can access newly-mounted removable volumes. The volume may appear in `/Volumes/` but `cp` or other write operations will silently fail or appear to hang until the user approves the access prompt. Permission after given will be persistent.

**What this looks like in practice:** The UF2 bootloader volume (e.g. `/Volumes/XIAO-BOOT`) mounts correctly, but the `cp` command blocks or fails until macOS shows the user a permission dialog. The user must approve it for the copy to proceed.

### Recovery Procedures

1. **Full Reset**: `./upload.sh reset`
2. **Physical Reset**: Double-tap RST on each XIAO → bootloader → drop UF2 manually.
3. **Touchpad First**: Right half owns Pinnacle hardware — flash it first if pad dies.

**BLE vs USB**: ZMK routes mouse events over USB when plugged in. Unplug after flashing to test BLE behavior.

---

### Tests

All tests (e.g., `tests/test_pad.py`, `tests/test_simple_rpc.py`) should follow this standard recipe:

#### Test Recipe
1. **Clean Abstraction**: Import and use `debug_tool.RPCSession` from `scripts/debug_tool.py` for all communication. Never import `serial_rpc.py` directly.
2. **Isolate Environment**: Always request `quarantine on` at the beginning of the test to block physical interference, and `quarantine off` when done.
3. **Queued Execution**: Do not use `time.sleep()` in test scripts. All timing and event sequences must be queued via `qi` (or `run_scenario()`) and executed via `qo`.
4. **Global Position Injection**: Peripheral key events must be injected at the Central (left) half using their global position indices.

#### Testing Tips & Gotchas
- **Peripheral Injection for Touch**: The split transport batches the BLE/RPC messages, causing them to arrive at the peripheral almost simultaneously. This means that timing/waits should be managed on the left half, with some flushing of messages.
- **Timestamp Drift**: Be aware that the `left_log` and `right_log` Zephyr uptime timestamps can drift or start with several seconds of offset.

See [[rpc.md]] for debug RPC commands.

---


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

#### Debug Cycle

 1. Build Debug Firmware
```bash
./debug.sh build
```
Outputs to `artifacts/debug/`. Always use this for touchpad / overlay changes.

 2. Flash Both Halves
```bash
# Flash both halves over USB RPC (both halves must be connected via USB)
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug both

# If one half is not detected, flash individually:
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug left
ARTIFACTS_DIR=artifacts/debug ./upload.sh --debug right
```

 3. Verify Devices
```bash
./debug.sh devices
```
Expected: 4 lines — left rpc, left log, right rpc, right log.

 4. Run Automated Tests
```bash
pkill -9 -f "python.*debug|debug.sh|pyserial" || true
python3 tests/test_pad.py
```

 5. Live Logs
```bash
./debug.sh logs both
./debug.sh logs right   # Pinnacle driver logs appear here
```
Logs saved to `debug-logs/<timestamp>-<side>-<port>.log`.

#### Build Release Firmware
```bash
./build.sh && ARTIFACTS_DIR=artifacts/release ./upload.sh both
```

---

## Architecture
Touchpad specific notes in [[touchpad.md]].
Generic Desktop HID usage page reference (e.g. System Do Not Disturb) is in [[references/generic_desktop.md]].

### Layers
| Index | Name | Activation | Physical Key (42-key) |
|-------|------|------------|-----------------------|
| 0 | BASE | Default | - |
| 1 | NAV | `&mo 1` | Left Thumb (Middle) |
| 2 | FN | `&mo 2` | Left Thumb (Outer) |
| 3 | PAD | `BTN_TOUCH` | Touchpad (automatic) |
| 4 | PAN | `&mo 4` | Held from Pad layer |

### Config Files
| File | Role |
|------|------|
| [[boards/shields/toucan/toucan.dtsi]] | Input listener + processor chain |
| [[config/toucan.keymap]] | Layer definitions and key bindings |
| [[config/combos.dtsi]] | Two-key combo definitions |
| [[config/leader.dtsi]] / [[config/leader_greek.dtsi]] | Leader sequences (SYS, German, Greek namespaces) |


## Agent Command Guidelines

**Knowledge Item Reference**: The core commands and workflow constraints for this project have been extracted to a Knowledge Item at [commands.md](file:///Users/ma/.gemini/antigravity-ide/knowledge/toucan_basic_commands/artifacts/commands.md). Ensure you review it if context is lost.

To prevent repetitive mistakes during future sessions, follow these rules when using tools:
- **Avoid `cat | grep` or `grep` in bash**: Always prioritize the `grep_search` tool over running `grep` in a bash command. Do not use `cat` for viewing files or `grep` for searching files via the `run_command` tool.
- **File Finding**: Do not use `find . -name "..."` as an unbounded bash command (it runs as a long background task). Instead, use `grep_search` with the `Includes` filter or `list_dir` to find files efficiently.
- **Task Logs**: Never use `cat` to read a background task's log file (e.g., `.system_generated/tasks/task-xxx.log`) manually, as it may not exist yet or might be truncated.
- **Background Tasks**: Do not poll a running background task repeatedly using `manage_task status`. Launch the task and yield your turn by making no more tool calls; the system will automatically notify you and wake you up when the task completes.

## License

The code in this repo is available under the MIT license.

The included shield nice_view_gem is modified from https://github.com/M165437/nice-view-gem licensed under the MIT License.
ZMK code snippets are taken from the ZMK documentation under the MIT license.
The embedded font QuinqueFive is designed by GGBotNet, licensed under the SIL Open Font License, Version 1.1.


---
