import sys
import time
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def verify_ble_keystroke():
    print("Starting listen_all...")
    # NOTE: listen_all requires Input Monitoring privileges or sudo to work for Usage Page 7 (Keyboard)!
    listen_proc = subprocess.Popen(
        ["./tests_c/listen_all"], 
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
        
        print("Tapping key 104 (F13)...")
        rpc.run_scenario([
            "P,10,104,1",
            "P,50,104,0"
        ])
        time.sleep(1.0)
        
        print("\n[BLE Test]")
        print("Forcing output to BLE...")
        rpc.request("out ble")
        time.sleep(0.5)
        
        print("Tapping key 105 (F14)...")
        rpc.run_scenario([
            "P,10,105,1",
            "P,50,105,0"
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

    usb_success = "F13" in stdout
    ble_success = "F14" in stdout
    
    print(f"\nUSB F13 Received: {usb_success}")
    print(f"BLE F14 Received: {ble_success}")
    
    assert usb_success, "USB failed to receive F13 keystroke"
    assert ble_success, "BLE failed to receive F14 keystroke"
    print("SUCCESS!")

if __name__ == "__main__":
    verify_ble_keystroke()
