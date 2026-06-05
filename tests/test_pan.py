#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from debug_tool import RPCSession

CENTER_X = 1024
CENTER_Y = 1024

def main():
    with RPCSession("left") as rpc:
        print("Executing PAN modifier test...")
        print("  Quarantining keyboard matrix...")
        rpc.request("quarantine on")
        
        try:
            test_pan_modifier(rpc)
        finally:
            rpc.request("quarantine off")
            
    print("PASS test_pan_modifier")
    return 0

def test_pan_modifier(rpc):
    """Holding PAN modifier (key 39) converts drag to scroll."""
    print("  Running test_pan_modifier...")
    scenario = []
    # 1. Touch down in center (activates Pad = 3)
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},50")
    # 2. Press first right thumb key (pos 39 = &mo PAN) in Pad layer (activates PAN = 4)
    scenario.append(f"P,100,39,1")
    # 3. Delay to let behaviors settle and layer 4 activate
    scenario.append(f"A,300,{CENTER_X},{CENTER_Y},50")
    
    # 4. Drag downwards
    current_y = CENTER_Y
    for i in range(1, 6):
        current_y = CENTER_Y + i * 40
        scenario.append(f"A,50,{CENTER_X},{current_y},50")
        
    # 5. Release key and touch
    scenario.append(f"P,100,39,0")
    scenario.append(f"A,100,{CENTER_X},{current_y},0")
    
    raw_trace = rpc.run_scenario(scenario)
    
    class TraceLog:
        def __init__(self, trace):
            self.events = trace
            
    trace = TraceLog(raw_trace)
    
    scroll_events = [ev for ev in trace.events if ev.startswith("S,")]
    move_events = [ev for ev in trace.events if ev.startswith("M,") and not ev.endswith(",0")]
    
    if len(move_events) > 0:
        print(f"      Trace dump: {trace.events}")
        print(f"\nFAILED: Unexpected move events found while PAN held: {move_events}")
        sys.exit(1)
        
    if len(scroll_events) == 0:
        print(f"      Trace dump: {trace.events}")
        print("\nFAILED: No scroll events were generated.")
        sys.exit(1)
        
    print("  test_pan_modifier passed.")

if __name__ == "__main__":
    sys.exit(main())
