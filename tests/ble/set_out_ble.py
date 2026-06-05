import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def set_ble():
    print("Connecting to keyboard...")
    rpc = RPCSession(selector="left")
    
    print("Initial Status:", rpc.request('ble status'))
    
    print("\nForcing output to BLE...")
    res = rpc.request("out ble")
    print(res)
    
if __name__ == "__main__":
    set_ble()
