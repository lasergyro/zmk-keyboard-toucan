import time
import pytest
import asyncio
from bleak import BleakScanner, BleakClient

@pytest.mark.asyncio
async def test_ble_connection(rpc_left):
    # Switch output to BLE
    print("\nSwitching output to BLE...")
    rpc_left.request("out ble")
    
    # Wait for the keyboard to establish connection to the host OS
    print("Waiting for auto-connection (3 seconds)...")
    await asyncio.sleep(3)
    
    # Scan to find the device
    print("Scanning for Toucan via BLE...")
    devices = await BleakScanner.discover(timeout=5.0)
    toucan = next((d for d in devices if d.name and "Toucan" in d.name), None)
    
    assert toucan is not None, "Could not find Toucan device in BLE scan. Is it advertising or connected?"
    
    # Switch back to USB after the test
    print("\nRestoring output to USB...")
    rpc_left.request("out usb")
    await asyncio.sleep(0.5)
