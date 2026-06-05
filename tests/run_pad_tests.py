#!/usr/bin/env python3
import sys
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from debug_tool import RPCSession

from pad.helpers import reset_touch_state_dual
from pad.test_cursor_movement import test_cursor_movement
from pad.test_resting_finger import test_resting_finger
from pad.test_tap_click import test_tap_click
from pad.test_double_click import test_double_click
from pad.test_tap_and_drag import test_tap_and_drag
from pad.test_circular_scroll import test_circular_scroll

def main() -> int:
    print("Executing gesture pipeline tests via qi/qo...")
    
    # Send configuration to right side (where gesture logic runs)
    with RPCSession("right") as rpc_right:
        rpc_right.request("pad param set tap_enable 1")
        rpc_right.request("pad param set drag_window_timeout_ms 500")
        rpc_right.request("pad param set rclick_enable 1")
        rpc_right.request("pad param set drag_enable 1")
        rpc_right.request("pad param set scroll_enable 1")

        with RPCSession("left") as rpc_left:
            print("  Quarantining keyboard matrix...")
            rpc_left.request("quarantine on")

            try:
        
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_cursor_movement(rpc_right, rpc_left)
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_resting_finger(rpc_right, rpc_left)
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_tap_click(rpc_right, rpc_left)
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_double_click(rpc_right, rpc_left)
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_tap_and_drag(rpc_right, rpc_left)
                reset_touch_state_dual(rpc_right, rpc_left)
            
                test_circular_scroll(rpc_right, rpc_left)
            except AssertionError as e:
                print(f"\nFAILED: {e}")
                return 1
            finally:
                rpc_left.request("quarantine off")

    print("\nPASS all gesture tests")
    return 0

if __name__ == "__main__":
    sys.exit(main())
