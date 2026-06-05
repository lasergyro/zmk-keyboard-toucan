#!/usr/bin/env python3
"""
macOS Mouse Event Tracer
This script uses Quartz (CoreGraphics) to intercept and print raw mouse events
(Left Down/Up, Right Down/Up) globally across macOS, including timestamps.

It will reveal the exact timing between a MouseDown and MouseUp event, allowing
you to see if the trackpad firmware is holding a click too long.

Requires: pip install pyobjc-framework-Quartz
Usage: sudo python3 trace_mouse.py
"""

import time
import sys

try:
    from Quartz import (
        CGEventTapCreate,
        CGEventTapEnable,
        CFRunLoopRun,
        CFRunLoopGetCurrent,
        CFMachPortCreateRunLoopSource,
        CFRunLoopAddSource,
        kCFAllocatorDefault,
        kCFRunLoopCommonModes,
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventRightMouseDown,
        kCGEventRightMouseUp,
        CGEventMaskBit,
        CGEventGetTimestamp
    )
except ImportError:
    print("Please install pyobjc: pip3 install pyobjc-framework-Quartz")
    sys.exit(1)

def event_callback(proxy, type_, event, refcon):
    timestamp_ns = CGEventGetTimestamp(event)
    timestamp_ms = timestamp_ns / 1_000_000.0
    
    if type_ == kCGEventLeftMouseDown:
        print(f"[{timestamp_ms:.2f}] Left Mouse DOWN")
    elif type_ == kCGEventLeftMouseUp:
        print(f"[{timestamp_ms:.2f}] Left Mouse UP")
    elif type_ == kCGEventRightMouseDown:
        print(f"[{timestamp_ms:.2f}] Right Mouse DOWN")
    elif type_ == kCGEventRightMouseUp:
        print(f"[{timestamp_ms:.2f}] Right Mouse UP")
        
    return event

def main():
    print("Starting macOS mouse tracer... (Press Ctrl+C to stop)")
    print("Capturing Left/Right Down and Up events globally.")
    
    # Create event mask for left/right mouse clicks
    event_mask = (CGEventMaskBit(kCGEventLeftMouseDown) | 
                  CGEventMaskBit(kCGEventLeftMouseUp) |
                  CGEventMaskBit(kCGEventRightMouseDown) | 
                  CGEventMaskBit(kCGEventRightMouseUp))

    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        0, # kCGEventTapOptionDefault
        event_mask,
        event_callback,
        None
    )

    if not tap:
        print("Failed to create event tap. Did you run with sudo/accessibility permissions?")
        sys.exit(1)

    run_loop_source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)

    try:
        CFRunLoopRun()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == '__main__':
    main()
