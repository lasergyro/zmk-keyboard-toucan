#!/usr/bin/env python3
"""
Automated test for Media layer activation.
Verifies that holding NAV (left thumb) and NUM (right thumb) activates the MEDIA layer.
"""

import sys
import time
from pathlib import Path

# Add scripts to path for helper modules
sys.path.append(str(Path(__file__).resolve().parent))
from debug_tool import select_device
from serial_rpc import SerialRPCSession

# Layers indices: BASE=0, NAV=1, FN=2, NUM=3, PAD=4, PAN=5, MEDIA=6
LAYER_NAV_BIT  = (1 << 1)
LAYER_NUM_BIT  = (1 << 3)
LAYER_MEDIA_BIT = (1 << 6)

# Key positions from 42.h / toucan.keymap
LH1_NAV = 37 # Left middle thumb (NAV)
RH2_NUM = 41 # Right outer thumb (NUM) - swapped from middle in Task 5

def get_layers(session):
    resp = session.request_lines("layers")
    if resp:
        for line in resp:
            if line.startswith("OK layers="):
                return int(line.split("=")[1], 16)
    return None

def test_media_activation():
    print("Starting automated Media layer activation test...")
    
    left_rpc_info = select_device("rpc", "left")
    right_rpc_info = select_device("rpc", "right")

    with (
        SerialRPCSession(left_rpc_info.path) as left,
        SerialRPCSession(right_rpc_info.path) as right
    ):
        # 1. Check initial state
        state = get_layers(left)
        if state is None:
            print("ERROR: Could not query layers. Is the firmware flashed with Task 5 changes?")
            return 1
            
        print(f"  Initial layer state: 0x{state:02x}")
        
        # 2. Press NAV (Left half)
        print(f"  Pressing NAV (pos {LH1_NAV})...")
        left.request_lines(f"key {LH1_NAV} down")
        time.sleep(0.2)
        
        state = get_layers(left)
        print(f"  State after NAV: 0x{state:02x}")
        if not (state & LAYER_NAV_BIT):
            print(f"  FAILED: NAV bit (0x{LAYER_NAV_BIT:02x}) not set.")
            left.request_lines(f"key {LH1_NAV} up")
            return 1
            
        # 3. Press NUM (Right half)
        print(f"  Pressing NUM (pos {RH2_NUM})...")
        right.request_lines(f"key {RH2_NUM} down")
        time.sleep(0.2)
        
        state = get_layers(left)
        print(f"  State after NAV+NUM: 0x{state:02x}")
        
        # 4. Verify Media Layer
        success = True
        if not (state & LAYER_MEDIA_BIT):
            print(f"  FAILED: MEDIA bit (0x{LAYER_MEDIA_BIT:02x}) not set.")
            success = False
        
        if not (state & LAYER_NAV_BIT) or not (state & LAYER_NUM_BIT):
            print(f"  FAILED: NAV or NUM bit lost when combined.")
            success = False
            
        # Cleanup
        print("  Releasing keys...")
        left.request_lines(f"key {LH1_NAV} up")
        right.request_lines(f"key {RH2_NUM} up")
        time.sleep(0.1)
        
        if success:
            print("SUCCESS: Media layer activation verified.")
            return 0
        else:
            return 1

if __name__ == "__main__":
    sys.exit(test_media_activation())
