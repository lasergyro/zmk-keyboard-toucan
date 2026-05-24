#!/usr/bin/env python3
"""
Automated gesture pipeline tests for the Toucan keyboard touchpad.

All touchpad events are injected via the LEFT (central) RPC so they land
directly in the glidepoint_split input processor chain — no BLE split latency,
accurate gesture timing.

Coordinate space: 1024×1024, center=(512,512).
Rim zone: annulus from radius ~359 to ~512 (15% rim_percent).
"""

from __future__ import annotations

import math
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from debug_tool import paired_device, select_device
from serial_rpc import SerialRPCSession

REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_SH = REPO_ROOT / "debug.sh"

# Pinnacle coordinate space (matches circular-scroll-width/height = 1024)
CENTER_X = 512
CENTER_Y = 512
# Rim annulus: inner ≈ 359, outer = 512. Use 450 for reliable rim detection.
RIM_RADIUS = 450

# Timing — must match firmware config (toucan_right.overlay / touch_detection defaults)
TAP_TIMEOUT_MS = 120       # tap-timout-ms
TOUCH_END_MS = 30          # wait-for-new-position-ms
DRAG_WINDOW_MS = 200       # tap-drag-window-ms
TEMP_LAYER_MS = 50         # zip_temp_layer hold time

LOG_START_SETTLE_S = 1.0
STEP_TIMEOUT_S = 8.0


# ── Geometry helpers ─────────────────────────────────────────────────────────


def rim_point(angle_deg: float) -> tuple[int, int]:
    """Point on the rim at given clockwise angle (0° = bottom)."""
    rad = math.radians(angle_deg)
    return (CENTER_X + int(RIM_RADIUS * math.sin(rad)),
            CENTER_Y + int(RIM_RADIUS * math.cos(rad)))


# ── RPC helpers ──────────────────────────────────────────────────────────────


def rpc_expect_ok(session: SerialRPCSession, payload: str) -> list[str]:
    lines = session.request_lines(payload)
    if any(line.startswith("OK") for line in lines):
        return lines
    raise RuntimeError(f"RPC '{payload}' failed on {session.device}\n" + "\n".join(lines))


# ── Log helpers ──────────────────────────────────────────────────────────────


def wait_for_logs_start(proc: subprocess.Popen[str]) -> tuple[Path, Path]:
    left_log: Path | None = None
    right_log: Path | None = None
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError("debug.sh logs both exited early")
            continue
        if "Writing left serial log to " in line:
            left_log = Path(line.strip().split(" to ", 1)[1])
        elif "Writing right serial log to " in line:
            right_log = Path(line.strip().split(" to ", 1)[1])
        elif "Following logs" in line and left_log and right_log:
            return left_log, right_log
    raise RuntimeError("Timed out waiting for log paths")


def stop_logs(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)


def log_mark(log_path: Path) -> int:
    """Current line count — use as start marker for post-test assertions."""
    return len(log_path.read_text().splitlines()) if log_path.exists() else 0


def wait_for_log_after(log_path: Path, mark: int, pattern: str,
                       timeout_s: float = STEP_TIMEOUT_S) -> int:
    """Block until pattern appears in log at or after line `mark`."""
    deadline = time.monotonic() + timeout_s
    rx = re.compile(pattern)
    while time.monotonic() < deadline:
        if log_path.exists():
            lines = log_path.read_text().splitlines()
            for idx in range(mark, len(lines)):
                if rx.search(lines[idx]):
                    return idx
        time.sleep(0.05)
    raise TimeoutError(f"Timed out ({timeout_s:.1f}s) waiting for {pattern!r} after line {mark}")


def assert_no_log_after(log_path: Path, mark: int, pattern: str) -> None:
    """Assert that pattern does NOT appear in log at or after line `mark`."""
    if not log_path.exists():
        return
    rx = re.compile(pattern)
    lines = log_path.read_text().splitlines()
    for idx in range(mark, len(lines)):
        if rx.search(lines[idx]):
            raise AssertionError(
                f"Unexpected log pattern {pattern!r} at line {idx}: {lines[idx]}"
            )


# ── Test scenarios ───────────────────────────────────────────────────────────


def test_cursor_movement(rpc: SerialRPCSession, left_log: Path) -> None:
    """Inner-pad drag → non-zero cursor deltas, PAD layer on/off."""
    mark = log_mark(left_log)
    rpc_expect_ok(rpc, "touch down")
    # 6 abs events stepping +40 in X each time; first delta=0, subsequent=40
    for i in range(6):
        rpc_expect_ok(rpc, f"abs {CENTER_X + i * 40} {CENTER_Y}")
        time.sleep(0.02)
    wait_for_log_after(left_log, mark, r"PAD layer on")
    # zip_xy_transform inverts X: rightward movement → negative REL_X in log
    wait_for_log_after(left_log, mark, r"move=-[1-9][0-9]*/0")
    # Stop sending — touch ends after TOUCH_END_MS, PAD off after TEMP_LAYER_MS
    time.sleep((TOUCH_END_MS + TEMP_LAYER_MS + 80) / 1000)
    wait_for_log_after(left_log, mark, r"PAD layer off")
    print("  PASS cursor_movement")


def test_resting_finger(rpc: SerialRPCSession, left_log: Path) -> None:
    """Stationary touch held >120ms → no click, PAD stays active."""
    mark = log_mark(left_log)
    rpc_expect_ok(rpc, "touch down")
    # 25 events at 20ms intervals = 500ms (> TAP_TIMEOUT_MS=120ms)
    # Keeps touch_end_timeout_work reset → touching=true → tap suppressed
    for _ in range(25):
        rpc_expect_ok(rpc, f"abs {CENTER_X} {CENTER_Y}")
        time.sleep(0.02)
    wait_for_log_after(left_log, mark, r"PAD layer on")
    assert_no_log_after(left_log, mark, r"buttons=0x01")
    print("  PASS resting_finger")


def test_tap_click(rpc: SerialRPCSession, left_log: Path) -> None:
    """Quick tap → left button press then release."""
    mark = log_mark(left_log)
    rpc_expect_ok(rpc, "touch down")
    rpc_expect_ok(rpc, f"abs {CENTER_X} {CENTER_Y}")
    # Don't send more events:
    #   after TOUCH_END_MS (30ms): touch_end → touching=false
    #   after TAP_TIMEOUT_MS (120ms): tap_timeout fires → seeing touching=false → click
    tap_settle_s = (TOUCH_END_MS + TAP_TIMEOUT_MS + 100) / 1000
    wait_for_log_after(left_log, mark, r"buttons=0x01", timeout_s=tap_settle_s + 1.0)
    wait_for_log_after(left_log, mark, r"buttons=0x00")
    print("  PASS tap_click")


def test_circular_scroll(rpc: SerialRPCSession, left_log: Path) -> None:
    """Rim touch + 180° clockwise arc → scroll events, no cursor movement."""
    mark = log_mark(left_log)
    rpc_expect_ok(rpc, "touch down")
    x0, y0 = rim_point(0)  # bottom of rim
    rpc_expect_ok(rpc, f"abs {x0} {y0}")
    time.sleep(0.02)
    # 12 steps of 15° each (0° → 180°)
    for angle in range(15, 181, 15):
        x, y = rim_point(angle)
        rpc_expect_ok(rpc, f"abs {x} {y}")
        time.sleep(0.02)
    wait_for_log_after(left_log, mark, r"scroll=")
    # Wait for all events to flush before checking for absence of cursor movement
    time.sleep(0.15)
    # circular_scroll zeroes out REL_X event; only scroll events should appear
    assert_no_log_after(left_log, mark, r"move=-[1-9]|move=[1-9]")
    print("  PASS circular_scroll")


# ── Orchestration ────────────────────────────────────────────────────────────


def reset_touch_state(rpc: SerialRPCSession) -> None:
    """
    Emit touch up and wait for all gesture timers to drain:
      TOUCH_END_MS: touch_detection timeout → touching=false
      TAP_TIMEOUT_MS: tap timer → fires and is suppressed (touching already false)
      TEMP_LAYER_MS: zip_temp_layer → PAD off
      +50ms margin
    """
    rpc_expect_ok(rpc, "touch up")
    time.sleep((TOUCH_END_MS + TAP_TIMEOUT_MS + TEMP_LAYER_MS + 50) / 1000)


def main() -> int:
    left_log: Path | None = None
    right_log: Path | None = None
    logs_proc: subprocess.Popen[str] | None = None

    left_rpc_info = select_device("rpc", "left")
    right_rpc_info = select_device("rpc", "right")
    left_log_device = paired_device(left_rpc_info, "log").path
    right_log_device = paired_device(right_rpc_info, "log").path

    with (
        SerialRPCSession(left_rpc_info.path, log_device=left_log_device) as left_rpc,
        SerialRPCSession(right_rpc_info.path, log_device=right_log_device) as right_rpc,
    ):
        rpc_expect_ok(left_rpc, "quarantine on")
        rpc_expect_ok(right_rpc, "quarantine on")

        try:
            logs_proc = subprocess.Popen(
                ["bash", str(DEBUG_SH), "logs", "both"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            assert logs_proc.stdout is not None
            left_log, right_log = wait_for_logs_start(logs_proc)
            time.sleep(LOG_START_SETTLE_S)

            reset_touch_state(left_rpc)

            for test_fn in [
                test_cursor_movement,
                test_resting_finger,
                test_tap_click,
                test_circular_scroll,
            ]:
                test_fn(left_rpc, left_log)
                reset_touch_state(left_rpc)

        finally:
            for session, label in [(left_rpc, "left"), (right_rpc, "right")]:
                try:
                    rpc_expect_ok(session, "quarantine off")
                except Exception:
                    pass
            if logs_proc is not None:
                stop_logs(logs_proc)

    if left_log is None or right_log is None:
        raise RuntimeError("Did not capture log paths")

    print("PASS all gesture tests")
    print(f"left_log={left_log}")
    print(f"right_log={right_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
