import sys
import time
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def verify_ble_dnd():
    print("Starting listen_dnd...")
    listen_proc = subprocess.Popen(
        ["./tests_c/listen_dnd"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(1)

    print("Connecting to keyboard...")
    rpc = RPCSession(selector="left")
    
    print("\n[USB Test]")
    print("Forcing output to USB...")
    rpc.request("out usb")
    time.sleep(0.5)
    
    print("Activating NAV layer (holding key 19)...")
    rpc.request("key 19 1")
    time.sleep(0.5)
    
    print("Tapping SYS_DND (key 10)...")
    rpc.request("key 10 1")
    time.sleep(0.5)
    rpc.request("key 10 0")
    time.sleep(0.5)
    
    print("Releasing NAV layer (key 19)...")
    rpc.request("key 19 0")
    time.sleep(0.5)
    
    print("\n[BLE Test]")
    print("Forcing output to BLE...")
    rpc.request("out ble")
    time.sleep(0.5)
    
    print("Activating NAV layer (holding key 19)...")
    rpc.request("key 19 1")
    time.sleep(0.5)
    
    print("Tapping SYS_DND (key 10)...")
    rpc.request("key 10 1")
    time.sleep(0.5)
    rpc.request("key 10 0")
    time.sleep(0.5)
    
    print("Releasing NAV layer (key 19)...")
    rpc.request("key 19 0")
    time.sleep(0.5)
    
    print("\nRestoring output to USB...")
    rpc.request("out usb")
    time.sleep(0.5)
    
    listen_proc.terminate()
    try:
        listen_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        listen_proc.kill()
        
    stdout, stderr = listen_proc.communicate()
    
    print("\n--- Events Received by macOS ---")
    print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)

    usb_success = stdout.count("RECEIVED MUTE") >= 2
    ble_success = stdout.count("RECEIVED MUTE") >= 4
    
    print(f"\nUSB Keystroke received: {usb_success}")
    print(f"BLE Keystroke received: {ble_success}")
    
if __name__ == "__main__":
    verify_ble_dnd()
