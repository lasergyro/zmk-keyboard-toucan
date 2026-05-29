# Toucan Keyboard - Basic Commands and Workflow

This Knowledge Item is injected at the start of conversations to ensure the agent maintains context on the essential project workflow and constraints.

## Basic Project Commands

- **Build Firmware:**
  `./debug.sh build`
- **Flash Firmware (Manual Bootloader):**
  `./upload.sh both` (Waits for physical double-tap of the RST button on the board)
- **Flash Firmware (Automatic Bootloader via RPC):**
  `./upload.sh --debug both` (Sends `bootloader` command over USB RPC to reset automatically)
- **Execute Python Tests:**
  `uv run tests/test_pad.py` or `uv run tests/test_simple_rpc.py`
  *(All python scripts must be run via `uv run` to ensure dependencies like `pyserial` are available)*
- **Stream Live Device Logs:**
  `./debug.sh logs both`

## Agent Guidelines & Meta Constraints

(Refer to `README.md` and `touchpad.md` for extended guidelines)

## Hardware & Architecture Facts

- The touchpad parser (`cirque_pinnacle_inject_abs`) runs exclusively on the **Right Half**.
- Python automation scripts communicate exclusively with the **Left Half** over USB.
- Events injected via `qi` must be sent from Left to Right over BLE using `zmk_split_central_invoke_behavior`.
