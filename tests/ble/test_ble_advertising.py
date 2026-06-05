import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from debug_tool import RPCSession
import time

def check_adv():
    print("Connecting to keyboard...")
    rpc = RPCSession(selector="left")
    
    print("Initial Status:", rpc.request('ble status'))
    
    print("Switching to next profile...")
    rpc.request('ble next')
    time.sleep(0.5)
    
    print("New Status:", rpc.request('ble status'))
    
    print("Clearing bonds on this profile...")
    rpc.request('ble clear')
    time.sleep(0.5)
    
    print("Final Status:", rpc.request('ble status'))

if __name__ == "__main__":
    check_adv()
