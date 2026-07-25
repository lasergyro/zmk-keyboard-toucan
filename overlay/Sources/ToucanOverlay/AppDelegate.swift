import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusItem: NSStatusItem!
    private let overlay = OverlayController()
    private let recorder = ShortcutRecorder()

    /// Kept around so the menu can re-read the system's login-item state each
    /// time it opens (the user may have flipped it in System Settings).
    private var loginItem: NSMenuItem?

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
        // Starts hidden — bring it up with the toggle shortcut or the menu.
        registerHotKeys()
    }

    // MARK: Status item / menu

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.image = statusItemImage()
        }
        rebuildMenu()
    }

    /// The status-bar glyph: the left half of the keymap, as a monochrome
    /// template (matches the app icon). Falls back to an SF Symbol.
    private func statusItemImage() -> NSImage? {
        if let url = Bundle.module.url(forResource: "toucan-menubar", withExtension: "pdf"),
           let image = NSImage(contentsOf: url) {
            image.size = NSSize(width: 16 * (image.size.width / image.size.height), height: 16)
            image.isTemplate = true
            return image
        }
        let fallback = NSImage(systemSymbolName: "keyboard", accessibilityDescription: "Toucan Overlay")
        fallback?.isTemplate = true
        return fallback
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
        let login = menu.addItem(withTitle: "Start at Login",
                                 action: #selector(toggleStartAtLogin), keyEquivalent: "")
        loginItem = login
        for item in menu.items { item.target = self }
        refreshLoginItemState()

        // Quit is added after the retargeting loop: its action lives on NSApp,
        // so it must target NSApp (targeting self would fail validation and
        // grey the item out).
        menu.addItem(.separator())
        let quit = menu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)),
                                keyEquivalent: "q")
        quit.target = NSApp
        menu.delegate = self
        statusItem.menu = menu
    }

    /// Mirrors the system's current login-item state into the menu item.
    private func refreshLoginItemState() {
        loginItem?.state = LoginItem.isEnabled ? .on : .off
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

    @objc private func toggleStartAtLogin() {
        let wantEnabled = !LoginItem.isEnabled
        if let error = LoginItem.setEnabled(wantEnabled) {
            alert("Couldn’t \(wantEnabled ? "enable" : "disable") Start at Login",
                  error.localizedDescription)
        } else if wantEnabled && LoginItem.requiresApproval {
            // Registration succeeded but macOS is holding it for the user's
            // approval, so send them to the pane where they can grant it.
            alert("Start at Login needs your approval",
                  "Enable “Toucan Overlay” under Login Items in System Settings.")
            LoginItem.openSystemSettings()
        }
        refreshLoginItemState()
    }

    private func alert(_ message: String, _ informative: String) {
        let a = NSAlert()
        a.messageText = message
        a.informativeText = informative
        NSApp.activate(ignoringOtherApps: true)
        a.runModal()
    }
}

extension AppDelegate: NSMenuDelegate {
    /// The login-item state can change outside the app (System Settings), so
    /// re-read it every time the menu is opened rather than trusting our copy.
    func menuNeedsUpdate(_ menu: NSMenu) { refreshLoginItemState() }
}

extension AppDelegate: NSMenuItemValidation {
    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        item.action == #selector(toggleStartAtLogin) ? LoginItem.isSupported : true
    }
}
