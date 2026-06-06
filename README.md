# ZMK config for beekeeb Toucan Keyboard

My personal config for my Toucan keyboard, also an experiment on getting AI to autonomously debug the keyboard (automatic flashing/rpc commands for debugging/input injection and output recording). Has per-device settings for unicode output, gestures and acceleration for the touchpad, and a Do Not Disturb key. Started from https://github.com/geeksville/zmk-urob-geeksville (thanks!). Render:

![Toucan Keymap](https://raw.githubusercontent.com/lasergyro/zmk-keyboard-toucan/keymap-render/keymap.svg?sanitize=true)

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

- **Layers** — defined in [config/toucan.keymap](config/toucan.keymap). See Architecture for indices.
- **Homerow mods** — timeless HRMs on the home row (GUI–ALT–SHIFT–CTRL, pinky to index, symmetric). Uses `MAKE_HRM` / `ZMK_HOLD_TAP` from zmk-helpers.
- **Combos** — two-key horizontal and vertical combos in `config/combos.dtsi`. Produce symbols, navigation shortcuts, and namespace-combo triggers.
- **Leader sequences** — three namespaces triggered by combo macros (`greek_ns`, `german_ns`, `sys_ns`). `&leader` is never invoked bare. See [config/leader.dtsi](config/leader.dtsi) and [config/leader_greek.dtsi](config/leader_greek.dtsi) for sequences.
- **Visualization** — [draw/config.yaml](draw/config.yaml) is the single source of truth for annotation slot positions and colors; `draw/generate-keymaps.rb` derives all layer/leader CSS from it. Run `./draw-keymap.sh` to regenerate [draw/keymap.svg](draw/keymap.svg).


### Keymap Visualization

Keymap visualization config (annotation positions, colors, binding labels) in [draw/config.yaml](draw/config.yaml).

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

#### Environment Setup
This repository uses `pixi` to manage its Python environment, tools, and Zephyr dependencies.
1. Install [pixi](https://pixi.sh/latest/#installation).
2. The environment will be automatically instantiated the first time you run any of the project scripts (like `./debug.sh`, `./release.sh`, or `./draw-keymap.sh`) or when you execute commands via `pixi run`.

#### OS Setup Instructions (macOS)
To get the best experience out of the Toucan trackpad on macOS, you should perform the following configuration:
1. **Disable Mouse Acceleration**: macOS's native mouse acceleration curve can make the small Toucan trackpad feel floaty. You should disable it completely in macOS System Settings > Mouse > Advanced, or by using a tool like LinearMouse.
2. **Smooth Scrolling**: The Toucan trackpad emits standard mouse scroll wheel events, which macOS natively renders as "stepped" scrolling. For a native Mac-like smooth scrolling experience, install [MOS](https://mos.caldis.me/) and leave it running in the background.


#### macOS — Removable Volume Access

When flashing UF2 firmware to devices (e.g. XIAO nRF52840 in bootloader mode), macOS requires explicit UI authorization before the AI assistant can access newly-mounted removable volumes. The volume may appear in `/Volumes/` but `cp` or other write operations will silently fail or appear to hang until the user approves the access prompt. Permission after given will be persistent.

**What this looks like in practice:** The UF2 bootloader volume (e.g. `/Volumes/XIAO-BOOT`) mounts correctly, but the `cp` command blocks or fails until macOS shows the user a permission dialog. The user must approve it for the copy to proceed.

### Recovery Procedures

1. **Full Reset**: `./release.sh upload reset`
2. **Physical Reset**: Double-tap RST on each XIAO → bootloader → drop UF2 manually.

**BLE vs USB**: ZMK routes mouse events over USB when plugged in. Unplug after flashing to test BLE behavior.

---

### Tests

All tests (in `tests/`) should follow this standard recipe:

#### Test Recipe
1. **Clean Abstraction**: Import and use `debug_tool.RPCSession` from `scripts/debug_tool.py` for all communication. Never import `serial_rpc.py` directly.
2. **Isolate Environment**: Always request `quarantine on` at the beginning of the test to block physical interference, and `quarantine off` when done.
3. **Queued Execution**: Do not use `time.sleep()` in test scripts. All timing and event sequences must be queued via `qi` (or `run_scenario()`) and executed via `qo`.
4. **Global Position Injection**: Peripheral key events must be injected at the Central (left) half using their global position indices.

#### Testing Tips & Gotchas
- **Peripheral Injection for Touch**: The split transport batches the BLE/RPC messages, causing them to arrive at the peripheral almost simultaneously. This means that timing/waits should be managed on the left half, with some flushing of messages.
- **Timestamp Drift**: Be aware that the `left_log` and `right_log` Zephyr uptime timestamps can drift or start with several seconds of offset.

See [rpc.md](docs/rpc.md) for debug RPC commands.

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
./debug.sh upload
```

 3. Verify Devices
```bash
./debug.sh devices
```
Expected: 4 lines — left rpc, left log, right rpc, right log.

 4. Run Automated Tests
```bash
pkill -9 -f "python.*debug|debug.sh|pyserial" || true
pixi run python tests/test_pad.py
```

 5. Live Logs
```bash
./debug.sh logs both
```
Logs saved to `debug-logs/<timestamp>-<side>-<port>.log`.

#### Build Release Firmware
```bash
./release.sh build && ./release.sh upload
```

### Contributing

When contributing to this repository or its submodules, please format your commit messages according to the **[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)** specification. This makes the project history highly readable and structured.

**Format**:
`<type>(<optional scope>): <description>`

**Allowed Types**:
- `feat:` for new features or hardware capabilities.
- `fix:` for bug fixes.
- `chore:` for updating dependencies, build scripts, IDE configs, or submodules.
- `docs:` for modifying markdown documentation or diagrams.
- `test:` for adding or fixing tests.
- `refactor:` for restructuring code without changing behavior.

*Example*: `feat(pad): add tap-to-drag gesture support`

## Architecture

Touchpad specific notes in [touchpad.md](docs/touchpad.md).
Generic Desktop HID usage page reference (e.g. System Do Not Disturb) is in [plans/generic_desktop.md](plans/generic_desktop.md).

### Build Composition

The firmware build process stitches together multiple code sources into a single executable:
- **West Manifest**: `scripts/build.sh` initializes a Zephyr workspace (`.zmk-workspace`) and pulls dependencies based on `config/west.yml`. This brings in ZMK core (`external/zmk`) and remote modules (e.g., `zmk-helpers`, `zmk-leader-key`).
- **Build Configurations**: `build.yaml` declares the board and shield configurations for both halves.
- **Extra Modules**: Additional input drivers (e.g., `external/cirque-input-module`, `external/zmk-input-gestures`) are injected into the build explicitly via `-DZMK_EXTRA_MODULES` flags in `scripts/build.sh`.
- **CMake & Kconfig**: The Zephyr build system merges all Kconfig options and devicetree (`.dts`/`.dtsi`) overlays from the boards, shields, and modules into a final configuration before compiling the C sources.

### Code Execution Structure

The lifecycle and execution flow of the firmware at runtime is structured as follows:
- **Boot / Initialization**: Custom application-level modules in `src/` (such as `debug_rpc.c`, `debug_quarantine.c`, `toucan_text_state.c`) use Zephyr's `SYS_INIT` macros. These are automatically invoked by the OS during kernel boot to register listeners, initialize NVS (Non-Volatile Storage), and start threads.
- **Hardware & Drivers**: Hardware interrupts (e.g., touch events from the Pinnacle trackpad) trigger driver callbacks. The driver (e.g., `input_pinnacle.c`) processes raw hardware signals through a state machine and emits standardized Zephyr Input subsystem events.
- **Input Processor Pipeline**: Devicetree definitions (in `toucan.dtsi`) create a chain of input processors. These intercept the raw input events (like `REL_X`, `REL_Y`, `BTN_TOUCH`), apply transformations (like axis inversion), and map specific signals to layer changes or behaviors (via `zip_behaviors`).
- **ZMK Event System**: ZMK's core evaluates key presses and input events against the active `toucan.keymap`. It uses an event-driven architecture to trigger behaviors, combos, leader sequences, and text macros across the split halves.
- **RPC Communication**: The custom RPC module listens asynchronously on the USB CDC ACM (serial) port. When commands are received on the central half, they are parsed and can trigger synthetic key events or forward parameter updates to the peripheral half over BLE.

### Dependencies
The `config/west.yml` declares multiple upstream dependencies which currently track the latest available release tags (baseline `v0.3` / `v0.3.0`):
- **ZMK Firmware** (`zmkfirmware/zmk.git`): Tracked via our `toucan-fork` (incorporating `0.3` patches + custom Generic Desktop HID support).
- **ZMK Helpers** (`urob/zmk-helpers.git`): Pinned to `v0.3` (Latest: `v0.3.0`).
- **ZMK Leader Key** (`urob/zmk-leader-key.git`): Pinned to `v0.3` (Latest: `v0.3.0`).
- **ZMK Unicode** (`urob/zmk-unicode.git`): Pinned to `v0.3` (Latest: `v0.3.0`).
- **ZMK RGBLED Widget** (`caksoylar/zmk-rgbled-widget.git`): Pinned to `v0.3` (Latest: `v0.3.0`).

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
| [boards/shields/toucan/toucan.dtsi](boards/shields/toucan/toucan.dtsi) | Input listener + processor chain |
| [config/toucan.keymap](config/toucan.keymap) | Layer definitions and key bindings |
| [config/combos.dtsi](config/combos.dtsi) | Two-key combo definitions |
| [config/leader.dtsi](config/leader.dtsi) / [config/leader_greek.dtsi](config/leader_greek.dtsi) | Leader sequences (SYS, German, Greek namespaces) |

## Agent Guidelines

**Knowledge Item Reference**: The core commands and workflow constraints for this project have been extracted to a [Knowledge Item](.gemini/knowledge/toucan_basic_commands/artifacts/commands.md), and are repeated below.

**Dev logs**: for each specific issue keep a log/notes in a document in `plans/[date]-[topic].md`; keep it up to date as you resolve the issue.

**Generic Patcher**: if normal edit tools are not the first choice, use the generic patching tool `scripts/patcher.py` to make targeted changes to files without needing to write custom Python scripts each time. You can invoke it like `pixi run python scripts/patcher.py <file> --search "<search_text>" --replace "<replace_text>"`.

To prevent repetitive mistakes during future sessions, follow these rules when using tools:
- **Avoid `cat | grep` or `grep` in bash**: Always prioritize the `grep_search` tool over running `grep` in a bash command. Do not use `cat` for viewing files or `grep` for searching files via the `run_command` tool.
- **File Finding**: Do not use `find . -name "..."` as an unbounded bash command (it runs as a long background task). Instead, use `grep_search` with the `Includes` filter or `list_dir` to find files efficiently.
- **Task Logs**: Never use `cat` to read a background task's log file (e.g., `.system_generated/tasks/task-xxx.log`) manually, as it may not exist yet or might be truncated.
- **Background Tasks**: Do not poll a running background task repeatedly using `manage_task status`. Launch the task and yield your turn by making no more tool calls; the system will automatically notify you and wake you up when the task completes.

### Basic Project Commands
- **Build Firmware:**
  `./debug.sh build`
- **Flash Firmware:**
  `./debug.sh upload` 
- **Execute Python:**
  All python scripts must be run via `pixi run python`.
- **Execute Python Tests:**
  e.g. `pixi run python tests/test_pad.py`
- **Stream Live Device Logs:**
  `./debug.sh logs both`

### Hardware & Architecture Facts
- The touchpad parser (`cirque_pinnacle_inject_abs`) runs exclusively on the **Right Half**.
- Python automation scripts communicate exclusively with the **Left Half** over USB.
- Events injected via `qi` are sent from Left to Right over BLE.

## License

The code in this repo is available under the MIT license.

The included shield nice_view_gem is modified from https://github.com/M165437/nice-view-gem licensed under the MIT License.
ZMK code snippets are taken from the ZMK documentation under the MIT license.
The embedded font QuinqueFive is designed by GGBotNet, licensed under the SIL Open Font License, Version 1.1.