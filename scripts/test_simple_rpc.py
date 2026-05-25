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
sys.path.append(str(Path(__file__).resolve().parent))
from debug_tool import RPCSession

def test_simple_rpc_standardized():
    print("Executing standardized simple RPC test...")
    
    with RPCSession("left") as s:
        # 1. Setup environment
        print("  Resetting and Quarantining...")
        s.request("clear")
        s.request("quarantine on")
        
        # 2. Queue simple scenario: press and release Tab (pos 0)
        print("  Queueing scenario: pos 0 down -> 100ms -> pos 0 up")
        scenario = [
            "P,0,0,1",
            "P,100,0,0"
        ]
        
        # 3. Execute and capture
        print("  Running scenario and capturing trace...")
        trace = s.run_scenario(scenario)
        
        # 4. Cleanup
        s.request("quarantine off")
        s.request("clear")
        
        print("\nCaptured Trace:")
        has_tab = False
        for line in trace:
            print(f"  {line}")
            # HID keycode for TAB is 43
            if "K," in line and ",43,1" in line:
                has_tab = True
                
        if has_tab:
            print("\nSUCCESS: Simple RPC test passed requirements.")
            return 0
        else:
            print("\nFAILED: Expected Tab keycode not found in trace.")
            return 1

if __name__ == "__main__":
    sys.exit(test_simple_rpc_standardized())
