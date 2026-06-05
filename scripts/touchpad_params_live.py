#!/usr/bin/env python3
"""
touchpad_params_live.py — Live touchpad gesture param tuning.

Connects to the right keyboard half's RPC port, reads the current gesture
params, then watches boards/shields/toucan/toucan_right.overlay for saves.
On every save it parses the gesture params in the glidepoint@0 node and sends
'set <key> <value>' RPC commands for params that changed.  Changes are
automatically persisted to the keyboard's flash settings store.

Usage:
    ./debug.sh python scripts/touchpad_params_live.py [--timeout SECS]
    ./debug.sh python scripts/touchpad_params_live.py [/dev/tty.usbmodemXXX] [--timeout SECS]
    python3 scripts/touchpad_params_live.py [/dev/tty.usbmodemXXX] [--timeout SECS]

The script keeps the RPC session open and polls the overlay file every 0.5 s.
Press Ctrl-C to exit.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict

from serial_rpc import SerialRPCSession, request_lines
from debug_tool import inventory

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY_FILE = REPO_ROOT / "boards" / "shields" / "toucan" / "toucan_right.overlay"

# Mapping from DTS property name to RPC/C field name.
# All integer params supported by pinnacle_gesture_param_get/set.
INT_PARAMS: Dict[str, str] = {
    "tap-timeout-ms":               "tap_timeout_ms",
    "drag-window-timeout-ms":       "drag_window_timeout_ms",
    "drag-jump-timeout-ms":         "drag_jump_timeout_ms",
    "pad-off-timeout-ms":           "pad_off_timeout_ms",
    "scroll-rim-percent":           "scroll_rim_percent",
    "drag-jump-rim-percent":        "drag_jump_rim_percent",
    "dead-radius-percent":          "dead_radius_percent",
    "rclick-x-min-percent":         "rclick_x_min_percent",
    "force-drag-z-threshold":            "force_drag_z_threshold",
    "double-click-drag-z-threshold":     "double_click_drag_z_threshold",
    "wheel-clicks":                 "wheel_clicks",
    "scroll-exclusion-zone-percent":"scroll_exclusion_zone_percent",
}
# Boolean params: present as bare property → 1, absent → 0.
BOOL_PARAMS: Dict[str, str] = {
    "tap-snap": "tap_snap",
    "tap-enable": "tap_enable",
    "rclick-enable": "rclick_enable",
    "drag-enable": "drag_enable",
    "scroll-enable": "scroll_enable",
}
ALL_PARAM_KEYS = list(INT_PARAMS.values()) + list(BOOL_PARAMS.values())


def find_right_rpc_device(selector: str | None) -> str:
    """Return the path of the right-half RPC device."""
    if selector and selector.startswith("/dev/"):
        return selector

    devices = [d for d in inventory(include_runtime_probe=False)
               if d.dev_type == "rpc" and d.side == "right"]
    if len(devices) == 1:
        return devices[0].path
    if not devices:
        raise SystemExit("error: no right-half RPC device found. "
                         "Is the keyboard plugged in and running debug firmware?")
    raise SystemExit("error: multiple right-half RPC devices found: "
                     + " ".join(d.path for d in devices))


def read_live_params(session: SerialRPCSession) -> Dict[str, int]:
    """Query all gesture params from the keyboard via 'get'."""
    lines = session.request_lines("get")
    if not lines or not lines[0].startswith("OK get"):
        raise RuntimeError(f"Unexpected 'get' response: {lines}")
    # Parse "OK get key=val key=val ..."
    params: Dict[str, int] = {}
    for match in re.finditer(r"(\w+)=(-?\d+)", lines[0]):
        params[match.group(1)] = int(match.group(2))
    return params


def parse_overlay_params(overlay_text: str) -> Dict[str, int]:
    """Extract gesture params from the glidepoint@0 DTS node."""
    # Find glidepoint@0 node body (heuristic: grab everything after glidepoint@0 {)
    node_match = re.search(r"glidepoint@0\s*\{(.+?)\};", overlay_text, re.DOTALL)
    node_text = node_match.group(1) if node_match else overlay_text

    params: Dict[str, int] = {}

    # Strip // line comments so commented-out properties are not matched.
    uncommented = re.sub(r"//[^\n]*", "", node_text)

    for dts_name, rpc_name in INT_PARAMS.items():
        pat = rf"\b{re.escape(dts_name)}\s*=\s*<\s*(-?\d+)\s*>"
        m = re.search(pat, uncommented)
        if m:
            params[rpc_name] = int(m.group(1))

    for dts_name, rpc_name in BOOL_PARAMS.items():
        pat = rf"\b{re.escape(dts_name)}\s*;"
        params[rpc_name] = 1 if re.search(pat, uncommented) else 0

    return params


def send_set(session: SerialRPCSession, key: str, value: int) -> bool:
    """Send 'set key value', return True on success."""
    lines = session.request_lines(f"set {key} {value}")
    ok = bool(lines and lines[0].startswith("OK"))
    if ok:
        print(f"  set {key}={value}  ✓")
    else:
        print(f"  set {key}={value}  FAILED: {lines}", file=sys.stderr)
    return ok


def watch_file_mtime(path: Path, timeout_s: int | None = None):
    """Yield each time the file's mtime changes."""
    prev: float | None = None
    start_time = time.time()
    while True:
        if timeout_s and (time.time() - start_time) > timeout_s:
            break
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        if mtime != prev:
            prev = mtime
            if mtime is not None:
                yield mtime
        time.sleep(0.5)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Live touchpad param tuning")
    parser.add_argument("device", nargs="?", help="Optional device path (e.g. /dev/tty.usbmodemXXX)")
    parser.add_argument("--timeout", type=int, help="Exit automatically after SECONDS")
    parsed = parser.parse_args(argv)
    
    device = find_right_rpc_device(parsed.device)

    print(f"Connecting to right RPC: {device}")
    print(f"Watching: {OVERLAY_FILE}")
    print()

    with SerialRPCSession(device) as session:
        # Read current live state.
        try:
            live = read_live_params(session)
        except Exception as exc:
            print(f"error: could not read params: {exc}", file=sys.stderr)
            return 1

        print("Current gesture params on keyboard:")
        for k, v in sorted(live.items()):
            print(f"  {k} = {v}")
        print()

        # Read initial overlay state.
        try:
            overlay_text = OVERLAY_FILE.read_text()
        except FileNotFoundError:
            print(f"warning: {OVERLAY_FILE} not found; "
                  "will watch for it to appear.", file=sys.stderr)
            overlay_text = ""

        overlay_params = parse_overlay_params(overlay_text)
        if overlay_params:
            print("Params found in overlay (will track changes):")
            for k, v in sorted(overlay_params.items()):
                marker = " *" if live.get(k) != v else ""
                print(f"  {k} = {v}{marker}")
            print("(* = differs from keyboard live value)")
        else:
            print("No gesture params found in overlay yet "
                  "(add them to glidepoint@0 to enable tracking).")
        print()
        print("Watching for saves — Ctrl-C to exit.")

        prev_params = dict(overlay_params)

        try:
            for _ in watch_file_mtime(OVERLAY_FILE, parsed.timeout):
                try:
                    new_text = OVERLAY_FILE.read_text()
                except FileNotFoundError:
                    continue

                new_params = parse_overlay_params(new_text)
                changed = {k: v for k, v in new_params.items()
                           if prev_params.get(k) != v}
                if not changed:
                    continue

                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] Overlay saved — {len(changed)} param(s) changed:")
                for k, v in sorted(changed.items()):
                    old = prev_params.get(k, "?")
                    print(f"  {k}: {old} → {v}")
                    send_set(session, k, v)

                prev_params = dict(new_params)
                print()
        except KeyboardInterrupt:
            print("\nExiting.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
