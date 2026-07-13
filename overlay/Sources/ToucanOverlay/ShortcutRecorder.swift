import AppKit

/// A tiny window that captures the next modifier+key combination.
final class ShortcutRecorder {

    private var window: NSWindow?
    private var monitor: Any?
    private var onCapture: (Shortcut) -> Void = { _ in }

    func begin(_ onCapture: @escaping (Shortcut) -> Void) {
        self.onCapture = onCapture

        let w = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 340, height: 130),
            styleMask: [.titled, .closable],
            backing: .buffered, defer: false
        )
        w.title = "Set Overlay Shortcut"
        w.level = .floating
        w.isReleasedWhenClosed = false
        w.center()

        let label = NSTextField(labelWithString: "Press the new shortcut…\n\n(needs a modifier · ⎋ to cancel)")
        label.alignment = .center
        label.maximumNumberOfLines = 0
        label.frame = NSRect(x: 20, y: 20, width: 300, height: 90)
        w.contentView?.addSubview(label)

        window = w
        NSApp.activate(ignoringOtherApps: true)
        w.makeKeyAndOrderFront(nil)

        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            self?.handle(event)
            return nil   // swallow the event
        }
    }

    private func handle(_ event: NSEvent) {
        if event.keyCode == 53 { finish(nil); return }   // Escape
        let mods = event.modifierFlags.intersection([.command, .option, .control, .shift])
        guard !mods.isEmpty else { return }              // require at least one modifier
        finish(Shortcut(keyCode: event.keyCode, modifiers: mods))
    }

    private func finish(_ shortcut: Shortcut?) {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
        window?.close()
        window = nil
        if let shortcut { onCapture(shortcut) }
    }
}
