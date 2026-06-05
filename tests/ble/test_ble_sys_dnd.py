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
    with RPCSession(selector="left") as rpc:
        print("\n[USB Test]")
        print("Forcing output to USB...")
        rpc.request("out usb")
        time.sleep(0.5)
        
        print("Sending SYS_DND sequence via qi/qo...")
        rpc.run_scenario([
            "P,10,19,1",
            "P,50,10,1",
            "P,50,10,0",
            "P,50,19,0"
        ])
        time.sleep(1.0)
        
        print("\n[BLE Test]")
        print("Forcing output to BLE...")
        rpc.request("out ble")
        time.sleep(0.5)
        
        print("Sending SYS_DND sequence via qi/qo...")
        rpc.run_scenario([
            "P,10,19,1",
            "P,50,10,1",
            "P,50,10,0",
            "P,50,19,0"
        ])
        time.sleep(1.0)
        
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

    usb_success = stdout.count("RECEIVED SYS_DND") >= 1
    ble_success = stdout.count("RECEIVED SYS_DND") >= 2
    
    print(f"\nUSB Keystroke received: {usb_success}")
    print(f"BLE Keystroke received: {ble_success}")
    
    assert usb_success, "USB failed to receive SYS_DND"
    assert ble_success, "BLE failed to receive SYS_DND"
    print("SUCCESS!")

if __name__ == "__main__":
    verify_ble_dnd()
