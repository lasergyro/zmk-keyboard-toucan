import math
import sys
import time
from toucan_debug.debug_tool import RPCSession

# Pinnacle coordinate space (0-2047), center=(1024,1024).
CENTER_X = 1024
CENTER_Y = 1024
RIM_RADIUS = 900

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

def reset_touch_state(rpc: RPCSession) -> None:
    scenario = [
        f"A,0,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,250,{CENTER_X},{CENTER_Y},0",
    ]
    rpc.run_scenario(scenario)

def run_pad_scenario(rpc_right: RPCSession, rpc_left: RPCSession, scenario: list[str]) -> list[str]:
    handle = rpc_right.session.handle
    assert handle is not None
    
    # Queue scenario on right
    handle.write(b"qi\n")
    handle.flush()
    ready_line = handle.readline().decode("utf-8", "ignore").strip()
    
    for line in scenario:
        handle.write(line.encode("utf-8") + b"\n")
        handle.flush()
        ack = handle.readline().decode("utf-8", "ignore").strip()
    
    # End queue
    handle.write(b".\n")
    handle.flush()
    end_ack = handle.readline().decode("utf-8", "ignore").strip()
    
    # Start trace on left
    rpc_left.request("rstart")
    
    # Execute on right
    handle.write(b"qo\n")
    handle.flush()
    
    # Wait for right to finish
    deadline = time.time() + 5.0
    while time.time() < deadline:
        line = handle.readline().decode("utf-8", "ignore").strip()
        if line: print(f"right_qo: {line}")
        if line.startswith("OK qo"):
            break
            
    # Stop trace on left and get events
    time.sleep(0.5)
    # The left side rpc will output B,... lines then OK rend 4.
    # To get the raw lines, we must read them directly from the serial port,
    # because rpc_left.request() drops non-OK/ERR lines!
    handle_left = rpc_left.session.handle
    assert handle_left is not None
    handle_left.write(b"rend\n")
    handle_left.flush()
    
    raw_trace = []
    deadline = time.time() + 5.0
    while time.time() < deadline:
        line = handle_left.readline().decode("utf-8", "ignore").strip()
        if line: print(f"left_rend: {line}")
        if not line:
            continue
        if line != ".":
            raw_trace.append(line)
        if line.startswith("OK rend"):
            break
            
    return raw_trace

def reset_touch_state_dual(rpc_right: RPCSession, rpc_left: RPCSession) -> None:
    scenario = [
        f"A,0,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,10,{CENTER_X},{CENTER_Y},0",
        f"A,250,{CENTER_X},{CENTER_Y},0",
    ]
    run_pad_scenario(rpc_right, rpc_left, scenario)

