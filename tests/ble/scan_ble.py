import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning for 10 seconds...")
    devices = await BleakScanner.discover(timeout=10.0)
    for d in devices:
        print(f"[{d.address}] {d.name} (RSSI: {d.rssi})")
        if "Toucan" in str(d.name) or "ZMK" in str(d.name):
            print(f"  -> FOUND MATCH: {d}")

if __name__ == "__main__":
    asyncio.run(main())
