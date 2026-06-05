from .helpers import run_pad_scenario, rim_point, TraceLog, RPCSession

def test_circular_scroll(rpc_right: RPCSession, rpc_left: RPCSession) -> None:
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

    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    # Scroll events are typically S,delay,1,val (where val1=1 means vertical wheel)
    scroll_events = [ev for ev in trace.events if ev.startswith("S,")]
    move_events = [ev for ev in trace.events if ev.startswith("M,") and not ev.endswith(",0")]
    
    if not scroll_events:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError("No scroll events found in trace!")
        
    print("    PASS circular_scroll")
