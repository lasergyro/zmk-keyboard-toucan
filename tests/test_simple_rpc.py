#!/usr/bin/env python3
"""
Standardized Simple RPC Test.
- Exclusive use of debug_tool.RPCSession.
- Centralized orchestration on Left half.
- Exclusive use of pad_qi/pad_qo for timed events.
"""

import sys
from pathlib import Path

from toucan_debug.debug_tool import RPCSession

def test_simple_rpc_standardized(rpc_left):
    rpc_left.request("clear")
    rpc_left.request("quarantine on")
    
    scenario = [
        "P,0,0,1",
        "P,100,0,0"
    ]
    
    trace = rpc_left.run_scenario(scenario)
    
    rpc_left.request("quarantine off")
    rpc_left.request("clear")
        
    has_tab = False
    for line in trace:
        if "K," in line and ",43,1" in line:
            has_tab = True
            
    assert has_tab, "Expected Tab keycode not found in trace."
