#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <stdio.h>

void Handle_IOHIDInputValueCallback(
    void *context, IOReturn result, void *sender, IOHIDValueRef value) {
    IOHIDElementRef elem = IOHIDValueGetElement(value);
    uint32_t usagePage = IOHIDElementGetUsagePage(elem);
    uint32_t usage = IOHIDElementGetUsage(elem);
    CFIndex intValue = IOHIDValueGetIntegerValue(value);
    
    // ignore mouse movements
    if (usagePage == 1 && (usage == 0x30 || usage == 0x31 || usage == 0x38)) return;
    
    printf("HID EVENT: Page=0x%02X, Usage=0x%02X, value=%ld\n", usagePage, usage, intValue);
    fflush(stdout);
}

int main() {
    IOHIDManagerRef hidManager = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);
    IOHIDManagerSetDeviceMatching(hidManager, NULL); // Match all
    IOHIDManagerRegisterInputValueCallback(hidManager, Handle_IOHIDInputValueCallback, NULL);
    IOHIDManagerScheduleWithRunLoop(hidManager, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);
    
    IOReturn res = IOHIDManagerOpen(hidManager, kIOHIDOptionsTypeNone);
    if (res != kIOReturnSuccess) {
        printf("Failed to open HID Manager.\n");
        return 1;
    }
    
    printf("Listening for all HID events...\n");
    fflush(stdout);
    
    CFRunLoopRun();
    return 0;
}
