# ZMK config for beekeeb Toucan Keyboard

[The beekeeb Toucan Keyboard](https://beekeeb.com/toucan-keyboard/) is a wireless split 42-key column‑stagger keyboard with a display and a trackpad, featuring an aggressive stagger on the pinky columns.

## Firmware Features

**Touchpad Implementation**
The right half features a touchpad built on a centralized **modified absolute mode with a state machine**.
- Tap-to-click
- Primary and secondary click
- Click-and-drag via click followed by hard press
- Uninterrupted drag by lifting from edge 
- Scroll mode on the outer edge

**Text Output Modes**
Each USB/BLE endpoint keeps its own persisted text-output mode. New profiles default to `macOS Unicode`.
Leader sequences:
- `YL` → `Linux Unicode`
- `YM` → `macOS Unicode`
- `YI` → `iOS Apple macros`
- `YSB` → Switch to USB output
- `LQ` → Toggle Greek LaTeX mode

## Development Workflow

For AI coding agents and developers looking to build, debug, and understand the internal workings of this firmware, please reference **[plan.md](plan.md)**.
It contains:
- The unified Agent Quick Reference (build, upload, test commands)
- Touchpad and state machine architecture deep-dive
- Local debugging notes and gotchas
- The structured port plan roadmap for future features

## License

The code in this repo is available under the MIT license.

The included shield nice_view_gem is modified from https://github.com/M165437/nice-view-gem licensed under the MIT License.
ZMK code snippets are taken from the ZMK documentation under the MIT license.
The embedded font QuinqueFive is designed by GGBotNet, licensed under the SIL Open Font License, Version 1.1.
