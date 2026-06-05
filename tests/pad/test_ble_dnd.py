import sys
import time
import subprocess
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def test_ble_dnd():
    # Check if Bluetooth is connected
    try:
        bt_status = subprocess.check_output(["blueutil", "--is-connected", "EC:6D:6A:7C:F3:96"], text=True).strip()
        if bt_status != "1":
            print("\n" + "="*80)
            print("ERROR: Toucan keyboard is NOT connected via Bluetooth!")
            print("To test BLE events, you MUST connect to 'Toucan' in macOS Bluetooth Settings.")
            print("If it's paired but disconnected, click 'Connect' in the Bluetooth menu.")
            print("Wait for it to connect before running this test again.")
            print("="*80 + "\n")
            sys.exit(1)
    except Exception as e:
        print(f"Warning: Could not check bluetooth status: {e}")

    print("Starting listen_dnd to capture DND events on macOS...")
    listen_proc = subprocess.Popen(
        ["./tests_c/listen_dnd"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(1) # Give listen_dnd time to start

    rpc = RPCSession(selector="left")
    
    print("Forcing output to BLE...")
    res = rpc.request("out ble")
    assert res and res[0].startswith("OK"), f"Failed to switch to BLE: {res}"
    time.sleep(0.5)
    
    print("Activating NAV layer (holding key 19)...")
    res = rpc.request("key 19 1")
    assert res and res[0].startswith("OK"), f"Failed to hold key 19: {res}"
    time.sleep(0.1)
    
    print("Tapping SYS_DND (key 10)...")
    res = rpc.request("tap 10")
    assert res and res[0].startswith("OK"), f"Failed to tap key 10: {res}"
    time.sleep(0.1)
    
    print("Releasing NAV layer (key 19)...")
    res = rpc.request("key 19 0")
    assert res and res[0].startswith("OK"), f"Failed to release key 19: {res}"
    time.sleep(0.1)
    
    print("Restoring output to USB...")
    res = rpc.request("out usb")
    assert res and res[0].startswith("OK"), f"Failed to switch to USB: {res}"
    time.sleep(1.0)
    
    listen_proc.terminate()
    try:
        listen_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        listen_proc.kill()
        
    stdout, stderr = listen_proc.communicate()
    
    print("--- listen_dnd output ---")
    print(stdout)
    
    if "RECEIVED SYS_DND (0x01, 0x9B) state: 1" in stdout:
        print("SUCCESS: DND event was captured on macOS!")
    else:
        print("FAILED: DND event was not captured!")
        sys.exit(1)

if __name__ == "__main__":
    test_ble_dnd()
