import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def leave_on_ble():
    print("Connecting to keyboard...")
    rpc = RPCSession(selector="left")
    
    print("\nForcing output to BLE...")
    rpc.request("out ble")
    print("Done. Keyboard is now in BLE mode.")

if __name__ == "__main__":
    leave_on_ble()
