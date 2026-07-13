import AppKit
import Carbon.HIToolbox

/// A configurable global shortcut, persisted in UserDefaults.
struct Shortcut: Equatable {
    var keyCode: UInt16
    var modifiers: NSEvent.ModifierFlags   // only the device-independent flags

    static let toggleKey = "overlayShortcut"
    static let holdKey = "overlayHoldShortcut"

    /// Toggle default: ⌥⌘K
    static let toggleDefault = Shortcut(keyCode: UInt16(kVK_ANSI_K), modifiers: [.option, .command])
    /// Hold-to-show default: ⌥⌘L
    static let holdDefault = Shortcut(keyCode: UInt16(kVK_ANSI_L), modifiers: [.option, .command])

    var carbonModifiers: UInt32 {
        var m: UInt32 = 0
        if modifiers.contains(.command) { m |= UInt32(cmdKey) }
        if modifiers.contains(.option)  { m |= UInt32(optionKey) }
        if modifiers.contains(.control) { m |= UInt32(controlKey) }
        if modifiers.contains(.shift)   { m |= UInt32(shiftKey) }
        return m
    }

    /// Human-readable form for the menu, e.g. "⌥⌘K".
    var display: String {
        var s = ""
        if modifiers.contains(.control) { s += "⌃" }
        if modifiers.contains(.option)  { s += "⌥" }
        if modifiers.contains(.shift)   { s += "⇧" }
        if modifiers.contains(.command) { s += "⌘" }
        return s + Shortcut.keyName(keyCode)
    }

    // MARK: Persistence

    func save(forKey key: String) {
        UserDefaults.standard.set(
            ["keyCode": Int(keyCode), "modifiers": Int(modifiers.rawValue)],
            forKey: key
        )
    }

    static func load(forKey key: String, default fallback: Shortcut) -> Shortcut {
        guard let d = UserDefaults.standard.dictionary(forKey: key),
              let kc = d["keyCode"] as? Int,
              let mf = d["modifiers"] as? Int else { return fallback }
        return Shortcut(keyCode: UInt16(kc),
                        modifiers: NSEvent.ModifierFlags(rawValue: UInt(mf)))
    }

    /// Best-effort key label using the current keyboard layout, with sensible
    /// names for common non-printing keys.
    static func keyName(_ keyCode: UInt16) -> String {
        switch Int(keyCode) {
        case kVK_Space:        return "Space"
        case kVK_Return:       return "↩"
        case kVK_Tab:          return "⇥"
        case kVK_Escape:       return "⎋"
        case kVK_LeftArrow:    return "←"
        case kVK_RightArrow:   return "→"
        case kVK_UpArrow:      return "↑"
        case kVK_DownArrow:    return "↓"
        case kVK_F1:  return "F1";  case kVK_F2:  return "F2";  case kVK_F3:  return "F3"
        case kVK_F4:  return "F4";  case kVK_F5:  return "F5";  case kVK_F6:  return "F6"
        case kVK_F7:  return "F7";  case kVK_F8:  return "F8";  case kVK_F9:  return "F9"
        case kVK_F10: return "F10"; case kVK_F11: return "F11"; case kVK_F12: return "F12"
        default: break
        }
        if let c = layoutCharacter(for: keyCode) { return c.uppercased() }
        return "key\(keyCode)"
    }

    private static func layoutCharacter(for keyCode: UInt16) -> String? {
        guard let src = TISCopyCurrentKeyboardLayoutInputSource()?.takeRetainedValue(),
              let ptr = TISGetInputSourceProperty(src, kTISPropertyUnicodeKeyLayoutData)
        else { return nil }
        let data = Unmanaged<CFData>.fromOpaque(ptr).takeUnretainedValue() as Data
        var deadKeys: UInt32 = 0
        var chars = [UniChar](repeating: 0, count: 4)
        var length = 0
        let status = data.withUnsafeBytes { raw -> OSStatus in
            let layout = raw.bindMemory(to: UCKeyboardLayout.self).baseAddress!
            return UCKeyTranslate(
                layout, keyCode, UInt16(kUCKeyActionDisplay), 0,
                UInt32(LMGetKbdType()), OptionBits(kUCKeyTranslateNoDeadKeysBit),
                &deadKeys, chars.count, &length, &chars
            )
        }
        guard status == noErr, length > 0 else { return nil }
        return String(utf16CodeUnits: chars, count: length)
    }
}

/// Registers OS-level hotkeys via Carbon (no Accessibility permission needed).
final class HotKeyCenter {
    static let shared = HotKeyCenter()

    private var handlerInstalled = false
    private var pressActions: [UInt32: () -> Void] = [:]
    private var releaseActions: [UInt32: () -> Void] = [:]
    private var refs: [UInt32: EventHotKeyRef] = [:]
    private var nextID: UInt32 = 1
    private let signature: OSType = 0x54_43_4F_56   // 'TCOV'

    private init() {}

    private func installHandlerIfNeeded() {
        guard !handlerInstalled else { return }
        handlerInstalled = true
        var specs = [
            EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: OSType(kEventHotKeyPressed)),
            EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: OSType(kEventHotKeyReleased)),
        ]
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ -> OSStatus in
            var hkID = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject),
                              EventParamType(typeEventHotKeyID), nil,
                              MemoryLayout<EventHotKeyID>.size, nil, &hkID)
            if GetEventKind(event) == UInt32(kEventHotKeyReleased) {
                HotKeyCenter.shared.releaseActions[hkID.id]?()
            } else {
                HotKeyCenter.shared.pressActions[hkID.id]?()
            }
            return noErr
        }, specs.count, &specs, nil, nil)
    }

    /// Registers a hotkey. `onRelease` (optional) enables show-while-held usage.
    @discardableResult
    func register(_ shortcut: Shortcut,
                  onPress: @escaping () -> Void,
                  onRelease: (() -> Void)? = nil) -> UInt32 {
        installHandlerIfNeeded()
        let id = nextID
        nextID += 1
        pressActions[id] = onPress
        releaseActions[id] = onRelease
        var ref: EventHotKeyRef?
        let hkID = EventHotKeyID(signature: signature, id: id)
        let status = RegisterEventHotKey(UInt32(shortcut.keyCode), shortcut.carbonModifiers,
                                         hkID, GetApplicationEventTarget(), 0, &ref)
        if status == noErr, let ref {
            refs[id] = ref
        } else {
            pressActions[id] = nil
            releaseActions[id] = nil
        }
        return id
    }

    func unregister(_ id: UInt32) {
        if let ref = refs[id] { UnregisterEventHotKey(ref); refs[id] = nil }
        pressActions[id] = nil
        releaseActions[id] = nil
    }
}
