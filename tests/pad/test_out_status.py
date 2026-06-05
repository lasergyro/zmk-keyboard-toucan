from tests.pad.helpers import RPCSession
import time

def test_out_status():
    print("Connecting to keyboard via RPC...")
    rpc = RPCSession(selector="left")
    
    # Check current status
    status = rpc.send_command("out status")
    print(f"Initial status: {status}")
    
    # Set to ble
    print("Sending 'out ble'...")
    res = rpc.send_command("out ble")
    print(f"Result: {res}")
    
    time.sleep(0.5)
    
    # Check status again
    status = rpc.send_command("out status")
    print(f"New status: {status}")

    # Clear the override
    rpc.send_command("out clear")
    print("Cleared override.")

if __name__ == "__main__":
    test_out_status()
