from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_resting_finger(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
    """Stationary touch held >120ms → no click."""
    print("  Running test_resting_finger...")
    scenario = []
    # Use Z=20 to avoid triggering force_drag_z_threshold!
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    
    # Wait past TAP_TIMEOUT_MS
    num_events = max(10, (params['tap_timeout_ms'] + 100) // 20)
    for _ in range(num_events):
        scenario.append(f"A,20,{CENTER_X},{CENTER_Y},20")
        
    # Lift finger (requires 3 Z-idle packets to debounce)
    scenario.append(f"A,20,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")

    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    # We expect a mouse button click: B,delay,button,state
    # button 1 = left click
    clicks = [ev for ev in trace.events if ev.startswith("B,") and ",1," in ev]
    if clicks:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError(f"Unexpected clicks found: {clicks}")
        
    print("    PASS resting_finger")
