import Foundation
import CoreGraphics
import IOKit.hid

// --- Private C APIs ---
@_silgen_name("CGEventCopyIOHIDEvent")
func CGEventCopyIOHIDEvent(_ event: CGEvent) -> UnsafeMutableRawPointer?

@_silgen_name("IOHIDEventGetSenderID")
func IOHIDEventGetSenderID(_ event: UnsafeMutableRawPointer) -> UInt64

// --- State ---
class ToucanManager {
    var toucanSenderIDs = Set<UInt64>()
    let isDebug: Bool
    
    init(isDebug: Bool) {
        self.isDebug = isDebug
    }
    
    func startHIDMonitor() {
        let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        IOHIDManagerSetDeviceMatching(manager, nil) // Match all
        
        let context = Unmanaged.passUnretained(self).toOpaque()
        
        IOHIDManagerRegisterDeviceMatchingCallback(manager, { ctx, result, sender, device in
            let mySelf = Unmanaged<ToucanManager>.fromOpaque(ctx!).takeUnretainedValue()
            let product = IOHIDDeviceGetProperty(device, kIOHIDProductKey as CFString) as? String ?? "Unknown"
            
            let service = IOHIDDeviceGetService(device)
            var regID: UInt64 = 0
            IORegistryEntryGetRegistryEntryID(service, &regID)
            
            if product.lowercased().contains("toucan") {
                mySelf.toucanSenderIDs.insert(regID)
                if mySelf.isDebug {
                    print("[HID] Toucan device connected: \(product) (Sender ID: \(regID))")
                }
            } else {
                if mySelf.isDebug {
                    print("[HID] Ignored device: \(product) (Sender ID: \(regID))")
                }
            }
        }, context)
        
        IOHIDManagerRegisterDeviceRemovalCallback(manager, { ctx, result, sender, device in
            let mySelf = Unmanaged<ToucanManager>.fromOpaque(ctx!).takeUnretainedValue()
            let service = IOHIDDeviceGetService(device)
            var regID: UInt64 = 0
            IORegistryEntryGetRegistryEntryID(service, &regID)
            
            if mySelf.toucanSenderIDs.contains(regID) {
                mySelf.toucanSenderIDs.remove(regID)
                if mySelf.isDebug {
                    print("[HID] Toucan device disconnected (Sender ID: \(regID))")
                }
            }
        }, context)
        
        IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
        IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))
    }
    
    func startEventTap() {
        let eventsOfInterest: CGEventMask = (1 << CGEventType.mouseMoved.rawValue) |
                                            (1 << CGEventType.leftMouseDragged.rawValue) |
                                            (1 << CGEventType.rightMouseDragged.rawValue) |
                                            (1 << CGEventType.otherMouseDragged.rawValue)
        
        let context = Unmanaged.passUnretained(self).toOpaque()
        
        guard let tap = CGEvent.tapCreate(
            tap: .cghidEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: eventsOfInterest,
            callback: { proxy, type, event, refcon in
                let mySelf = Unmanaged<ToucanManager>.fromOpaque(refcon!).takeUnretainedValue()
                
                // Only process movement events
                if type == .mouseMoved || type == .leftMouseDragged || type == .rightMouseDragged || type == .otherMouseDragged {
                    if let hidEvent = CGEventCopyIOHIDEvent(event) {
                        let senderId = IOHIDEventGetSenderID(hidEvent)
                        
                        if mySelf.toucanSenderIDs.contains(senderId) {
                            // 170 is kCGMouseEventUnacceleratedPointerMovement
                            if let unaccelField = CGEventField(rawValue: 170) {
                                event.setIntegerValueField(unaccelField, value: 1)
                                if mySelf.isDebug {
                                    let dx = event.getIntegerValueField(.mouseEventDeltaX)
                                    let dy = event.getIntegerValueField(.mouseEventDeltaY)
                                    print("[Toucan] Bypassed OS acceleration. delta: (\(dx), \(dy))")
                                }
                            }
                        } else {
                            if mySelf.isDebug {
                                // Too noisy to print every single other movement, but good for extreme debug
                                // print("[Other] Passed through unmodified.")
                            }
                        }
                    }
                }
                
                return Unmanaged.passUnretained(event)
            },
            userInfo: context
        ) else {
            print("ERROR: Failed to create CGEventTap. Please ensure Terminal/iTerm has Accessibility permissions.")
            exit(1)
        }
        
        let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        
        if isDebug {
            print("[Tap] Event tap successfully installed and enabled.")
        }
    }
}

// --- Main ---
let args = CommandLine.arguments
let isDebug = args.contains("--debug")

print("Toucan Companion App starting... (Debug mode: \(isDebug))")
let manager = ToucanManager(isDebug: isDebug)
manager.startHIDMonitor()
manager.startEventTap()

// Keep alive
CFRunLoopRun()
