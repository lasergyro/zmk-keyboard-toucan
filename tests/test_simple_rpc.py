#!/usr/bin/env python3
"""
Standardized Simple RPC Test.
- Exclusive use of debug_tool.RPCSession.
- Centralized orchestration on Left half.
- Exclusive use of pad_qi/pad_qo for timed events.
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from debug_tool import RPCSession

def test_simple_rpc_standardized():
    with RPCSession("left") as s:
        s.request("clear")
        s.request("quarantine on")
        
        scenario = [
            "P,0,0,1",
            "P,100,0,0"
        ]
        
        trace = s.run_scenario(scenario)
        
        s.request("quarantine off")
        s.request("clear")
        
        has_tab = False
        for line in trace:
            if "K," in line and ",43,1" in line:
                has_tab = True
                
        assert has_tab, "Expected Tab keycode not found in trace."
