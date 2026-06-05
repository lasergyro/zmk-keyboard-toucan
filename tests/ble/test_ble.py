import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    print("Scanning for Toucan...")
    devices = await BleakScanner.discover(timeout=5.0)
    toucan_device = None
    for d in devices:
        if d.name and "Toucan" in d.name:
            toucan_device = d
            break
            
    if not toucan_device:
        print("Toucan not found. Is it paired/connected or advertising?")
        return
        
    print(f"Found {toucan_device.name} [{toucan_device.address}]")
    
    try:
        async with BleakClient(toucan_device) as client:
            print("Connected!")
            for service in client.services:
                print(f"Service: {service.uuid} {service.description}")
                for char in service.characteristics:
                    print(f"  Char: {char.uuid} {char.description} ({','.join(char.properties)})")
                    if "report map" in char.description.lower() or char.uuid.startswith("00002a4b"):
                        val = await client.read_gatt_char(char.uuid)
                        print(f"    Report Map: {val.hex()}")
    except Exception as e:
        print(f"Error connecting: {e}")

asyncio.run(main())
