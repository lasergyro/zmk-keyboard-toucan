from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_pan_modifier(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
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
    
    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    scroll_events = [ev for ev in trace.events if ev.startswith("S,")]
    move_events = [ev for ev in trace.events if ev.startswith("M,") and not ev.endswith(",0")]
    
    if len(move_events) > 0:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError(f"Unexpected move events found while PAN held: {move_events}")
        
    if len(scroll_events) == 0:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError("No scroll events were generated.")
        
    print("  test_pan_modifier passed.")
