import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusItem: NSStatusItem!
    private let overlay = OverlayController()
    private let recorder = ShortcutRecorder()

    private var toggleShortcut = Shortcut.load(forKey: Shortcut.toggleKey, default: .toggleDefault)
    private var holdShortcut = Shortcut.load(forKey: Shortcut.holdKey, default: .holdDefault)
    private var toggleKeyID: UInt32?
    private var holdKeyID: UInt32?

    /// Whether the overlay was already visible when a hold-to-show press began,
    /// so releasing the hold doesn't hide a pinned overlay.
    private var holdWasVisible = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)   // menu-bar agent, no Dock icon
        setupStatusItem()
        overlay.restoreOrPosition()
        overlay.reload()
        overlay.show()                           // shown by default (top-right)
        registerHotKeys()
    }

    // MARK: Status item / menu

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "keyboard", accessibilityDescription: "Toucan Overlay")
            button.image?.isTemplate = true
        }
        rebuildMenu()
    }

    private func rebuildMenu() {
        let menu = NSMenu()
        menu.addItem(withTitle: "Toggle Overlay  (\(toggleShortcut.display))",
                     action: #selector(toggleOverlay), keyEquivalent: "")
        menu.addItem(withTitle: "Hold to Show  (\(holdShortcut.display))",
                     action: #selector(toggleOverlay), keyEquivalent: "")
        menu.addItem(withTitle: "Reset Position (top-right)",
                     action: #selector(resetPosition), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Reload Keymap", action: #selector(reloadKeymap), keyEquivalent: "")
        menu.addItem(withTitle: "Choose Keymap SVG…", action: #selector(chooseSVG), keyEquivalent: "")
        menu.addItem(withTitle: "Set Toggle Shortcut…", action: #selector(setToggleShortcut), keyEquivalent: "")
        menu.addItem(withTitle: "Set Hold-to-Show Shortcut…", action: #selector(setHoldShortcut), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        for item in menu.items { item.target = self }
        statusItem.menu = menu
    }

    // MARK: Hotkeys

    private func registerHotKeys() {
        if let id = toggleKeyID { HotKeyCenter.shared.unregister(id) }
        if let id = holdKeyID { HotKeyCenter.shared.unregister(id) }

        toggleKeyID = HotKeyCenter.shared.register(toggleShortcut, onPress: { [weak self] in
            self?.overlay.toggle()
        })

        holdKeyID = HotKeyCenter.shared.register(holdShortcut, onPress: { [weak self] in
            guard let self else { return }
            self.holdWasVisible = self.overlay.isVisible
            self.overlay.show()
        }, onRelease: { [weak self] in
            guard let self, !self.holdWasVisible else { return }
            self.overlay.hide()
        })
    }

    // MARK: Menu actions

    @objc private func toggleOverlay() { overlay.toggle() }
    @objc private func resetPosition() { overlay.resetPosition(); overlay.show() }
    @objc private func reloadKeymap() { overlay.reload() }

    @objc private func chooseSVG() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.svg]
        panel.allowsMultipleSelection = false
        panel.message = "Choose the keymap SVG to display"
        NSApp.activate(ignoringOtherApps: true)
        if panel.runModal() == .OK, let url = panel.url {
            UserDefaults.standard.set(url.path, forKey: KeymapSource.defaultsKey)
            overlay.reload()
        }
    }

    @objc private func setToggleShortcut() {
        recorder.begin { [weak self] captured in
            guard let self else { return }
            self.toggleShortcut = captured
            captured.save(forKey: Shortcut.toggleKey)
            self.registerHotKeys()
            self.rebuildMenu()
        }
    }

    @objc private func setHoldShortcut() {
        recorder.begin { [weak self] captured in
            guard let self else { return }
            self.holdShortcut = captured
            captured.save(forKey: Shortcut.holdKey)
            self.registerHotKeys()
            self.rebuildMenu()
        }
    }
}
