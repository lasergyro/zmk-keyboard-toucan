import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession

def clear_bonds():
    print("Connecting to keyboard...")
    rpc = RPCSession(selector="left")
    print("Status:", rpc.request('ble status'))
    print("Clearing bonds:", rpc.request('ble clear'))
    print("New Status:", rpc.request('ble status'))

if __name__ == "__main__":
    clear_bonds()
