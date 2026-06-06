from .helpers import run_pad_scenario, CENTER_X, CENTER_Y, TraceLog, RPCSession

def test_tap_click(rpc_right: RPCSession, rpc_left: RPCSession, params: dict) -> None:
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
    # By adding a 500ms delay, we force the scenario executor to wait, and 
    # the tail_timeout_work will extend to 500ms beyond THAT!
    scenario.append(f"A,500,{CENTER_X},{CENTER_Y},0")

    raw_trace = run_pad_scenario(rpc_right, rpc_left, scenario)
    trace = TraceLog(raw_trace)
    
    # Look for B,delay,1,1 and B,delay,1,0
    btn_down = trace.find_all("B,1,1") or trace.find_all(",1,1")
    btn_up = trace.find_all("B,1,0") or trace.find_all(",1,0")
    
    if not btn_down or not btn_up:
        raise AssertionError("Expected tap click (BTN_LEFT) not found in trace!")
        
    print("    PASS tap_click")
