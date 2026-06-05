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
    
    if (usagePage == 0x01 && usage == 0x9B) {
        printf("RECEIVED SYS_DND (0x01, 0x9B) state: %ld\n", intValue);
        fflush(stdout);
        // Exit on release
        if (intValue == 0) {
            // do not exit
        }
    }
}

int main() {
    IOHIDManagerRef hidManager = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);
    
    CFStringRef keys[2] = {CFSTR(kIOHIDDeviceUsagePageKey), CFSTR(kIOHIDDeviceUsageKey)};
    int page = 0x01; // Generic Desktop
    int usage = 0x9B; // System Do Not Disturb
    CFNumberRef pageNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberIntType, &page);
    CFNumberRef usageNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberIntType, &usage);
    
    CFTypeRef values[2] = {pageNum, usageNum};
    CFDictionaryRef matchingDict = CFDictionaryCreate(kCFAllocatorDefault, 
                                                      (const void **)keys, 
                                                      (const void **)values, 
                                                      2, 
                                                      &kCFTypeDictionaryKeyCallBacks, 
                                                      &kCFTypeDictionaryValueCallBacks);
                                                      
    IOHIDManagerSetDeviceMatching(hidManager, matchingDict);
    IOHIDManagerRegisterInputValueCallback(hidManager, Handle_IOHIDInputValueCallback, NULL);
    
    IOHIDManagerScheduleWithRunLoop(hidManager, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);
    
    IOReturn res = IOHIDManagerOpen(hidManager, kIOHIDOptionsTypeNone);
    if (res != kIOReturnSuccess) {
        printf("Failed to open HID Manager.\n");
        return 1;
    }
    
    printf("Listening for SYS_DND (Usage Page 1, Usage 0x9B)...\n");
    fflush(stdout);
    
    CFRunLoopRun();
    
    return 0;
}
