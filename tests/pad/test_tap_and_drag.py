from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_tap_and_drag(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
    print("  Running test_tap_and_drag...")
    scenario = []
    
    # First tap
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    scenario.append(f"A,50,{CENTER_X},{CENTER_Y},20")
    scenario.append(f"A,20,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    
    # Wait between taps (must be < drag_window_timeout_ms)
    wait_time = max(10, params['drag_window_timeout_ms'] - 50)
    scenario.append(f"A,{wait_time},{CENTER_X},{CENTER_Y},0")
    
    # Second tap, hold and move
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    
    # Wait past drag-pending-timeout to trigger drag
    drag_pending_time = params['drag_pending_timeout_ms'] + 50
    scenario.append(f"A,{drag_pending_time},{CENTER_X},{CENTER_Y},20")
    
    # Move
    for i in range(1, 4):
        scenario.append(f"A,20,{CENTER_X + i * 40},{CENTER_Y},20")
        
    # Lift
    scenario.append(f"A,20,{CENTER_X + 3 * 40},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X + 3 * 40},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X + 3 * 40},{CENTER_Y},0")
    
    # Wait to flush
    scenario.append(f"A,500,{CENTER_X + 3 * 40},{CENTER_Y},0")
    
    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    btn_down_events = [ev for ev in trace.events if ev.startswith("B,") and ev.endswith(",1")]
    btn_up_events = [ev for ev in trace.events if ev.startswith("B,") and ev.endswith(",0")]
    move_events = [ev for ev in trace.events if ev.startswith("M,")]
    
    if len(btn_down_events) != 2 or len(btn_up_events) != 2 or not move_events:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError(f"Expected tap then drag. Found {len(btn_down_events)} downs, {len(btn_up_events)} ups, {len(move_events)} moves!")
    
    print("    PASS tap_and_drag")
