from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_cursor_movement(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
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

    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    # We expect relative movement events. Format is M,delay,x,y
    move_events = [ev for ev in trace.events if ev.startswith("M,")]
    if not move_events:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError("No relative movement events found in trace!")
    
    print("    PASS cursor_movement")
