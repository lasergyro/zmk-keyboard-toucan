import sys
import time
import subprocess
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

MAC_ADDR = "EC:6D:6A:7C:F3:96"

def force_pair_and_test():
    print("Connecting to keyboard via RPC...")
    rpc = RPCSession(selector="left")
    
    print("1. Clearing Bluetooth bonds on the keyboard...")
    res = rpc.request("ble clear")
    print(f"   Keyboard response: {res}")
    time.sleep(2)
    
    print("2. Unpairing keyboard from macOS...")
    try:
        subprocess.run(["blueutil", "--unpair", MAC_ADDR], check=False, capture_output=True)
    except Exception as e:
        print(f"   Warning: blueutil unpair failed: {e}")
    time.sleep(2)
    
    print("3. Attempting to pair from macOS...")
    try:
        res = subprocess.run(["blueutil", "--pair", MAC_ADDR], check=False, capture_output=True, text=True)
        print(f"   Pair result: {res.returncode}")
        if res.stdout: print(f"   stdout: {res.stdout.strip()}")
        if res.stderr: print(f"   stderr: {res.stderr.strip()}")
    except Exception as e:
        print(f"   Warning: blueutil pair failed: {e}")
    time.sleep(4)
    
    print("4. Attempting to connect from macOS...")
    try:
        res = subprocess.run(["blueutil", "--connect", MAC_ADDR], check=False, capture_output=True, text=True)
        print(f"   Connect result: {res.returncode}")
        if res.stdout: print(f"   stdout: {res.stdout.strip()}")
        if res.stderr: print(f"   stderr: {res.stderr.strip()}")
    except Exception as e:
        print(f"   Warning: blueutil connect failed: {e}")
    time.sleep(2)
    
    print("5. Checking connection status on keyboard...")
    res = rpc.request("ble status")
    print(f"   Keyboard response: {res}")
    
    print("6. Running test_ble_dnd.py...")
    subprocess.run(["uv", "run", "python", "tests/pad/test_ble_dnd.py"])

if __name__ == "__main__":
    force_pair_and_test()
