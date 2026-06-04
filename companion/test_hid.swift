import Foundation
import CoreGraphics
import IOKit.hid

@_silgen_name("CGEventCopyIOHIDEvent")
func CGEventCopyIOHIDEvent(_ event: CGEvent) -> UnsafeMutableRawPointer?

@_silgen_name("IOHIDEventGetSenderID")
func IOHIDEventGetSenderID(_ event: UnsafeMutableRawPointer) -> UInt64

let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
IOHIDManagerSetDeviceMatching(manager, nil) // Match all

IOHIDManagerRegisterDeviceMatchingCallback(manager, { context, result, sender, device in
    let product = IOHIDDeviceGetProperty(device, kIOHIDProductKey as CFString) as? String ?? "Unknown"
    // Get registry ID
    let service = IOHIDDeviceGetService(device)
    var regID: UInt64 = 0
    IORegistryEntryGetRegistryEntryID(service, &regID)
    print("Device matched: \(product) (Sender ID: \(regID))")
}, nil)

IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))

DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
    print("Test finished")
    exit(0)
}

CFRunLoopRun()
