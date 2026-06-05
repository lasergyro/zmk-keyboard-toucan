import sys
import time
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def get_mute():
    res = subprocess.check_output(["osascript", "-e", "output muted of (get volume settings)"], text=True)
    return "true" in res.strip().lower()

def test_mute():
    print("Initial mute state:", get_mute())
    
    rpc = RPCSession(selector="left")
    rpc.request("out usb")
    time.sleep(0.5)
    
    print("Sending MUTE via USB...")
    rpc.request("key 19 1")
    time.sleep(0.5)
    rpc.request("key 2 1")
    time.sleep(0.5)
    rpc.request("key 2 0")
    time.sleep(0.5)
    rpc.request("key 19 0")
    time.sleep(0.5)
    
    print("Mute state after USB:", get_mute())

if __name__ == "__main__":
    test_mute()
