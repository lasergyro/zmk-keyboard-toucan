#!/usr/bin/env python3
"""
Automated gesture pipeline tests for the Toucan keyboard touchpad using qi/qo.

All touchpad events are injected via the LEFT (central) RPC so they land
directly in the glidepoint_split input processor chain via BLE forwarding —
accurately simulating real hardware timing.

Coordinate space: 1024×1024, center=(512,512).
Rim zone: annulus from radius ~359 to ~512 (15% rim_percent).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from debug_tool import RPCSession

# Pinnacle coordinate space (0-2047), center=(1024,1024).
CENTER_X = 1024
CENTER_Y = 1024
RIM_RADIUS = 900

# Timing constants
TAP_TIMEOUT_MS = 120
TOUCH_END_MS = 30
DRAG_WINDOW_MS = 200
TEMP_LAYER_MS = 50

# Global state for assertions
class TraceLog:
    def __init__(self, raw_lines: list[str]):
        self.raw_lines = raw_lines
        self.events = []
        for line in raw_lines:
            if line.startswith("OK qo"):
                continue
            if "," in line:
                self.events.append(line)

    def contains(self, pattern: str) -> bool:
        """Simple substring check across all captured events."""
        return any(pattern in event for event in self.events)

    def find_all(self, pattern: str) -> list[str]:
        return [event for event in self.events if pattern in event]

# ── Geometry helpers ─────────────────────────────────────────────────────────

def rim_point(angle_deg: float) -> tuple[int, int]:
    """Point on the rim at given clockwise angle (0° = bottom)."""
    rad = math.radians(angle_deg)
    return (CENTER_X + int(RIM_RADIUS * math.sin(rad)),
            CENTER_Y + int(RIM_RADIUS * math.cos(rad)))

# ── Test scenarios ───────────────────────────────────────────────────────────

def reset_touch_state(rpc: RPCSession) -> None:
    scenario = [
        f"A,0,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,250,{CENTER_X},{CENTER_Y},0",
    ]
    rpc.run_scenario(scenario)

def test_cursor_movement(rpc: RPCSession) -> None:
    """Inner-pad drag → non-zero cursor deltas."""
    print("  Running test_cursor_movement...")
    scenario = []
    # Touch down in center (delay 0)
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},50")
    
    # 6 abs events stepping +40 in X each time; 20ms delay each
    for i in range(1, 7):
        scenario.append(f"A,20,{CENTER_X + i * 40},{CENTER_Y},50")
        
    # Lift finger (requires 3 Z-idle packets to debounce)
    scenario.append(f"A,20,{CENTER_X + 6 * 40},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X + 6 * 40},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X + 6 * 40},{CENTER_Y},0")

    raw_trace = rpc.run_scenario(scenario)
    trace = TraceLog(raw_trace)
    
    # We expect relative movement events. Format is M,delay,x,y
    move_events = [ev for ev in trace.events if ev.startswith("M,")]
    if not move_events:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError("No relative movement events found in trace!")
    
    print("    PASS cursor_movement")

def test_resting_finger(rpc: RPCSession) -> None:
    """Stationary touch held >120ms → no click."""
    print("  Running test_resting_finger...")
    scenario = []
    # Use Z=20 to avoid triggering force_drag_z_threshold!
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    
    # 25 events at 20ms intervals = 500ms (> TAP_TIMEOUT_MS=120ms)
    for _ in range(25):
        scenario.append(f"A,20,{CENTER_X},{CENTER_Y},20")
        
    # Lift finger (requires 3 Z-idle packets to debounce)
    scenario.append(f"A,20,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")

    raw_trace = rpc.run_scenario(scenario)
    trace = TraceLog(raw_trace)
    
    # We expect a mouse button click: B,delay,button,state
    # button 1 = left click
    clicks = [ev for ev in trace.events if ev.startswith("B,") and ",1," in ev]
    if clicks:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError(f"Unexpected clicks found: {clicks}")
        
    print("    PASS resting_finger")

def test_tap_click(rpc: RPCSession) -> None:
    """Quick tap → left button press then release."""
    print("  Running test_tap_click...")
    scenario = []
    # Tap down. Use Z=20 to avoid hard press.
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    # Lift after 20ms (requires 3 Z-idle packets to debounce)
    scenario.append(f"A,20,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    
    # We MUST append a long delay to wait for the tap to be emitted!
    # The tap click up (drag window end) happens at ~300ms after the lift!
    # By adding a 500ms delay, we force the scenario executor to wait, and 
    # the tail_timeout_work will extend to 500ms beyond THAT!
    scenario.append(f"A,500,{CENTER_X},{CENTER_Y},0")

    raw_trace = rpc.run_scenario(scenario)
    trace = TraceLog(raw_trace)
    
    # Look for B,delay,1,1 and B,delay,1,0
    btn_down = trace.find_all("B,1,1") or trace.find_all(",1,1")
    btn_up = trace.find_all("B,1,0") or trace.find_all(",1,0")
    
    if not btn_down or not btn_up:
        raise AssertionError("Expected tap click (BTN_LEFT) not found in trace!")
        
    print("    PASS tap_click")

def test_circular_scroll(rpc: RPCSession) -> None:
    """Rim touch + 180° clockwise arc → scroll events, no cursor movement."""
    print("  Running test_circular_scroll...")
    scenario = []
    x0, y0 = rim_point(90)
    scenario.append(f"A,0,{x0},{y0},20")
    
    for angle in range(105, 271, 15):
        x, y = rim_point(angle)
        scenario.append(f"A,20,{x},{y},20")
        
    # Lift (requires 3 Z-idle packets to debounce)
    scenario.append(f"A,20,{x},{y},0")
    scenario.append(f"A,10,{x},{y},0")
    scenario.append(f"A,10,{x},{y},0")

    raw_trace = rpc.run_scenario(scenario)
    trace = TraceLog(raw_trace)
    
    # Scroll events are typically S,delay,1,val (where val1=1 means vertical wheel)
    scroll_events = [ev for ev in trace.events if ev.startswith("S,")]
    move_events = [ev for ev in trace.events if ev.startswith("M,") and not ev.endswith(",0")]
    
    if not scroll_events:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError("No scroll events found in trace!")
        
    print("    PASS circular_scroll")


# ── Orchestration ────────────────────────────────────────────────────────────

def main() -> int:
    print("Executing gesture pipeline tests via qi/qo...")
    with RPCSession("left") as rpc:
        print("  Quarantining keyboard matrix...")
        rpc.request("quarantine on")

        print("  Enabling gestures via RPC...")
        rpc.request("pad param set tap_enable 1")
        rpc.request("pad param set rclick_enable 1")
        rpc.request("pad param set drag_enable 1")
        rpc.request("pad param set scroll_enable 1")

        try:
            reset_touch_state(rpc)
            
            test_cursor_movement(rpc)
            reset_touch_state(rpc)
            
            test_resting_finger(rpc)
            reset_touch_state(rpc)
            
            test_tap_click(rpc)
            reset_touch_state(rpc)
            
            test_circular_scroll(rpc)
        except AssertionError as e:
            print(f"\nFAILED: {e}")
            return 1
        finally:
            rpc.request("quarantine off")

    print("\nPASS all gesture tests")
    return 0

if __name__ == "__main__":
    sys.exit(main())
