import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def test_ble_commands():
    print("Connecting to keyboard via RPC...")
    with RPCSession(selector="left") as rpc:
        # Test basic status
        print("\n--- Initial Status ---")
        for line in rpc.request('ble status'):
            print(line)
        
        # Test switching endpoints
        print("\n--- Testing Transport Override ---")
        print("Forcing output to BLE...")
        for line in rpc.request("out ble"):
            print(line)
            
        time.sleep(0.5)
        
        print("Restoring output to USB...")
        for line in rpc.request("out usb"):
            print(line)
            
        # Test BLE profile switching
        print("\n--- Testing Profile Navigation ---")
        print("Switching to next profile...")
        for line in rpc.request('ble next'):
            print(line)
            
        time.sleep(0.5)
        
        print("New Status:")
        for line in rpc.request('ble status'):
            print(line)
            
        print("Clearing bonds on this profile...")
        for line in rpc.request('ble clear'):
            print(line)
            
        time.sleep(0.5)
        
        print("Final Status:")
        for line in rpc.request('ble status'):
            print(line)
            
    print("\nSUCCESS: All BLE debug RPC commands executed.")

if __name__ == "__main__":
    test_ble_commands()
