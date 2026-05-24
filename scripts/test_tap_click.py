#!/usr/bin/env python3

from __future__ import annotations

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

LOG_START_SETTLE_S = 1.0
FINAL_SETTLE_S = 1.0
STEP_TIMEOUT_S = 8.0


def rpc_expect_ok(session: SerialRPCSession, payload: str) -> list[str]:
    lines = session.request_lines(payload)
    if any(line.startswith("OK") for line in lines):
        return lines

    rendered = "\n".join(lines)
    raise RuntimeError(f"RPC '{payload}' failed on {session.device}\n{rendered}")


def wait_for_logs_start(proc: subprocess.Popen[str]) -> tuple[Path, Path]:
    left_log: Path | None = None
    right_log: Path | None = None
    deadline = time.monotonic() + 10.0

    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError("debug.sh logs both exited before startup completed")
            continue

        if "Writing left serial log to " in line:
            left_log = Path(line.strip().split(" to ", 1)[1])
        elif "Writing right serial log to " in line:
            right_log = Path(line.strip().split(" to ", 1)[1])
        elif "Following logs" in line and left_log and right_log:
            return left_log, right_log

    raise RuntimeError("Timed out waiting for debug.sh logs both to report log paths")


def stop_logs(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)


def wait_for_log_pattern(log_path: Path, pattern: str, timeout_s: float = STEP_TIMEOUT_S) -> int:
    deadline = time.monotonic() + timeout_s
    rx = re.compile(pattern)

    while time.monotonic() < deadline:
        if log_path.exists():
            lines = log_path.read_text().splitlines()
            for idx, line in enumerate(lines):
                if rx.search(line):
                    return idx
        time.sleep(0.05)

    raise TimeoutError(f"Timed out waiting for log pattern {pattern!r} in {log_path}")


def test_tap_to_click(left_log: Path, right_log: Path, left_rpc: SerialRPCSession, right_rpc: SerialRPCSession) -> None:
    """Test tap-to-click setup - synthetic events bypass driver, so this tests RPC functionality"""
    print("Testing tap-to-click RPC functionality...")
    
    # Enable quarantine to capture events
    rpc_expect_ok(left_rpc, "quarantine on")
    rpc_expect_ok(right_rpc, "quarantine on")
    
    try:
        # Start logging
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
        
        # Test that synthetic button injection works (for click-and-drag testing)
        print("Testing synthetic button injection...")
        rpc_expect_ok(right_rpc, "key 0 down")
        time.sleep(0.1)
        rpc_expect_ok(right_rpc, "key 0 up")
        time.sleep(1.0)  # Much longer wait for all logging to complete
        
        # Check logs for key injection events (quarantine drops HID reports)
        right_lines = right_log.read_text().splitlines()
        button_down_events = [line for line in right_lines if "key event: position=0 state=down" in line]
        button_up_events = [line for line in right_lines if "key event: position=0 state=up" in line]
        
        print(f"Found {len(button_down_events)} button down events")
        print(f"Found {len(button_up_events)} button up events")
        
        if len(button_down_events) == 0 or len(button_up_events) == 0:
            raise AssertionError(f"Expected button events, got {len(button_down_events)} down, {len(button_up_events)} up")
        
        print("Synthetic button injection test passed!")
        print("Note: Real tap-to-click requires physical touchpad input to test driver logic.")
        
    finally:
        try:
            rpc_expect_ok(left_rpc, "quarantine off")
        except Exception:
            pass
        try:
            rpc_expect_ok(right_rpc, "quarantine off")
        except Exception:
            pass
        if logs_proc.poll() is None:
            stop_logs(logs_proc)


def main() -> int:
    left_rpc_info = select_device("rpc", "left")
    right_rpc_info = select_device("rpc", "right")
    left_rpc_device = left_rpc_info.path
    right_rpc_device = right_rpc_info.path
    left_log_device = paired_device(left_rpc_info, "log").path
    right_log_device = paired_device(right_rpc_info, "log").path

    with SerialRPCSession(left_rpc_device, log_device=left_log_device) as left_rpc, SerialRPCSession(
        right_rpc_device, log_device=right_log_device
    ) as right_rpc:
        test_tap_to_click(None, None, left_rpc, right_rpc)

    print("PASS tap-to-click setup test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())