from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_double_click(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
    print("  Running test_double_click...")
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
    
    # Second tap
    scenario.append(f"A,0,{CENTER_X},{CENTER_Y},20")
    scenario.append(f"A,50,{CENTER_X},{CENTER_Y},20")
    scenario.append(f"A,20,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    scenario.append(f"A,10,{CENTER_X},{CENTER_Y},0")
    
    # Wait for completion
    scenario.append(f"A,500,{CENTER_X},{CENTER_Y},0")
    
    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    btn_down_events = [ev for ev in trace.events if ev.startswith("B,") and ev.endswith(",1")]
    btn_up_events = [ev for ev in trace.events if ev.startswith("B,") and ev.endswith(",0")]
    
    if len(btn_down_events) != 2 or len(btn_up_events) != 2:
        print(f"      Trace dump: {trace.events}")
        raise AssertionError(f"Expected 2 tap clicks (BTN_LEFT) but found {len(btn_down_events)} downs and {len(btn_up_events)} ups!")
    
    print("    PASS double_click")
