import sys
import time
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def test_switch():
    print("Connecting to keyboard via RPC...")
    rpc = RPCSession(selector="left")
    
    # Check current status
    print("Initial Status:", rpc.request('ble status'))
    
    print("\nForcing output to BLE...")
    res = rpc.request("out ble")
    print(res)
    time.sleep(0.5)
    
    print("Tapping a key (key 24)...")
    res = rpc.request("tap 24")
    print(res)
    time.sleep(0.5)
    
    print("\nRestoring output to USB...")
    res = rpc.request("out usb")
    print(res)
    
if __name__ == "__main__":
    test_switch()
