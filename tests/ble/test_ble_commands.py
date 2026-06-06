import sys
import time
from toucan_debug.debug_tool import RPCSession

def test_ble_commands(rpc_left):
    # Test basic status
    for line in rpc_left.request('ble status'):
        pass
    
    # Test switching endpoints
    for line in rpc_left.request("out ble"):
        pass
        
    time.sleep(0.5)
    
    for line in rpc_left.request("out usb"):
        pass
        
    # Test BLE profile switching
    for line in rpc_left.request('ble next'):
        pass
        
    time.sleep(0.5)
    
    for line in rpc_left.request('ble status'):
        pass
        
    for line in rpc_left.request('ble clear'):
        pass
        
    time.sleep(0.5)
    
    for line in rpc_left.request('ble status'):
        pass
