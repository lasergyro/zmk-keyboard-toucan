import AppKit
import WebKit

/// Keymap web view that suppresses WebKit's default right-click menu (Reload,
/// Back/Forward, …) — meaningless on a non-interactive overlay.
private final class KeymapWebView: WKWebView {
    override func willOpenMenu(_ menu: NSMenu, with event: NSEvent) {
        menu.removeAllItems()   // empty menu → nothing pops up
    }
}

/// Transparent overlay that sits above the keymap and turns any click-drag into
/// a window move. Because it covers the web view, the web content never
/// receives mouse events — so nothing inside is selectable either.
private final class DragView: NSView {
    override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) }
    override var mouseDownCanMoveWindow: Bool { true }
    override var acceptsFirstResponder: Bool { false }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
}

/// Borderless, floating, non-activating glass panel that renders the keymap.
/// Drag anywhere to move; resize from the edges with a locked aspect ratio.
final class OverlayController: NSObject, NSWindowDelegate {

    let panel: NSPanel
    private let webView: WKWebView
    private let aspect = KeymapSVG.aspect
    private let corner: CGFloat = 20
    private let resizeMargin: CGFloat = 8                 // outer ring reserved for edge-resize

    /// Default footprint: a quarter of the screen in each dimension, aspect-fit.
    private let defaultScreenFraction: CGFloat = 0.25

    // Per-display geometry: each physical display remembers its own size and
    // position, so switching/reconnecting monitors restores the right layout
    // instead of clobbering a single shared frame.
    private let framesKey = "ToucanOverlayFramesByDisplay.v1"
    private let lastDisplayKey = "ToucanOverlayLastDisplay.v1"
    /// Suppresses save-on-move/resize while we reposition programmatically.
    private var isRestoring = false

    override init() {
        let cfg = WKWebViewConfiguration()
        webView = KeymapWebView(frame: NSRect(x: 0, y: 0, width: 400, height: 400),
                                configuration: cfg)

        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 400 * aspect.height / aspect.width),
            styleMask: [.borderless, .resizable, .nonactivatingPanel],
            backing: .buffered, defer: false
        )
        super.init()

        configureWebView()
        configurePanel()
        buildContent()

        // Re-apply the per-display layout when monitors are added/removed or
        // rearranged, so the overlay stays valid on whatever screen it's on.
        NotificationCenter.default.addObserver(
            self, selector: #selector(screensChanged),
            name: NSApplication.didChangeScreenParametersNotification, object: nil)
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    // MARK: Setup

    private func configureWebView() {
        webView.setValue(false, forKey: "drawsBackground")   // transparent → glass shows through
        if #available(macOS 12.0, *) { webView.underPageBackgroundColor = .clear }
        webView.wantsLayer = true
        webView.layer?.backgroundColor = NSColor.clear.cgColor
    }

    private func configurePanel() {
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        panel.isFloatingPanel = true
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        // Dark glass reads better under the dark (gruvbox) keymap.
        panel.appearance = NSAppearance(named: .darkAqua)
        panel.aspectRatio = aspect
        panel.minSize = NSSize(width: 240, height: 240 * aspect.height / aspect.width)
        panel.delegate = self
    }

    /// Builds: [ glass ] → contentView( webView, dragView-on-top ).
    private func buildContent() {
        let content = NSView(frame: NSRect(x: 0, y: 0, width: 400, height: 328))
        content.wantsLayer = true
        content.layer?.cornerRadius = corner
        content.layer?.masksToBounds = true
        content.autoresizingMask = [.width, .height]

        webView.frame = content.bounds
        webView.autoresizingMask = [.width, .height]
        content.addSubview(webView)

        // Drag layer covers everything except the outer resize ring.
        let drag = DragView(frame: content.bounds.insetBy(dx: resizeMargin, dy: resizeMargin))
        drag.autoresizingMask = [.width, .height]
        content.addSubview(drag)

        if #available(macOS 26.0, *) {
            let glass = NSGlassEffectView()
            glass.style = .regular
            glass.cornerRadius = corner
            glass.contentView = content
            panel.contentView = glass
        } else {
            let host = NSView(frame: content.frame)
            host.wantsLayer = true
            host.layer?.cornerRadius = corner
            host.layer?.masksToBounds = true
            let vev = NSVisualEffectView(frame: host.bounds)
            vev.material = .hudWindow
            vev.blendingMode = .behindWindow
            vev.state = .active
            vev.autoresizingMask = [.width, .height]
            host.addSubview(vev)
            content.frame = host.bounds
            host.addSubview(content)
            panel.contentView = host
        }
    }

    // MARK: Actions

    func reload() {
        let processed = KeymapSVG.process(KeymapSource.load())
        webView.loadHTMLString(KeymapSVG.html(svg: processed), baseURL: nil)
    }

    var isVisible: Bool { panel.isVisible }

    func toggle() {
        if panel.isVisible { hide() } else { show() }
    }

    func show() { panel.orderFrontRegardless() }

    func hide() { panel.orderOut(nil) }

    /// Restore geometry for the display last used (if still connected),
    /// otherwise for the screen the panel is currently on.
    func restoreOrPosition() {
        restore(on: preferredScreen())
    }

    func resetPosition() { resetPosition(on: currentScreen()) }

    private func resetPosition(on screen: NSScreen?) {
        guard let screen = screen ?? NSScreen.main else { return }
        let vf = screen.visibleFrame
        let boxW = vf.width * defaultScreenFraction
        let boxH = vf.height * defaultScreenFraction
        let scale = min(boxW / aspect.width, boxH / aspect.height)
        let w = aspect.width * scale
        let h = aspect.height * scale
        let margin: CGFloat = 16
        let frame = NSRect(x: vf.maxX - w - margin, y: vf.maxY - h - margin, width: w, height: h)
        setPanelFrame(frame)
        storeFrame(frame, for: screen)
    }

    // MARK: Per-display geometry

    /// Restore the saved frame for `screen`, or fall back to the default there.
    private func restore(on screen: NSScreen?) {
        guard let screen = screen ?? NSScreen.main else { return }
        if let f = savedFrame(for: screen), isReasonable(f, on: screen) {
            setPanelFrame(f)
        } else {
            resetPosition(on: screen)
        }
    }

    @objc private func screensChanged() {
        guard panel.isVisible else { return }
        restore(on: preferredScreen())
    }

    /// The display last used if it's still connected, else the current one.
    private func preferredScreen() -> NSScreen? {
        let last = UserDefaults.standard.string(forKey: lastDisplayKey)
        return NSScreen.screens.first { displayKey(for: $0) == last } ?? currentScreen()
    }

    /// The screen the panel most overlaps, else main.
    private func currentScreen() -> NSScreen? {
        NSScreen.screens.max { overlapArea($0) < overlapArea($1) }
            .flatMap { overlapArea($0) > 0 ? $0 : nil } ?? NSScreen.main
    }

    private func overlapArea(_ screen: NSScreen) -> CGFloat {
        let r = screen.frame.intersection(panel.frame)
        return r.isNull ? 0 : r.width * r.height
    }

    /// Stable per-display identity (display UUID, surviving reconnects).
    private func displayKey(for screen: NSScreen) -> String {
        guard let num = (screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")]
                         as? NSNumber)?.uint32Value else { return "unknown" }
        if let uuid = CGDisplayCreateUUIDFromDisplayID(num)?.takeRetainedValue() {
            return CFUUIDCreateString(nil, uuid) as String
        }
        return "screen-\(num)"
    }

    private func savedFrame(for screen: NSScreen) -> NSRect? {
        guard let frames = UserDefaults.standard.dictionary(forKey: framesKey) as? [String: String],
              let s = frames[displayKey(for: screen)] else { return nil }
        let r = NSRectFromString(s)
        return r == .zero ? nil : r
    }

    private func storeFrame(_ frame: NSRect, for screen: NSScreen) {
        var frames = UserDefaults.standard.dictionary(forKey: framesKey) as? [String: String] ?? [:]
        frames[displayKey(for: screen)] = NSStringFromRect(frame)
        UserDefaults.standard.set(frames, forKey: framesKey)
        UserDefaults.standard.set(displayKey(for: screen), forKey: lastDisplayKey)
    }

    private func saveCurrentFrame() {
        guard let screen = currentScreen() else { return }
        storeFrame(panel.frame, for: screen)
    }

    /// A frame is usable if enough of it lands on the screen's visible area.
    private func isReasonable(_ frame: NSRect, on screen: NSScreen) -> Bool {
        let vis = screen.visibleFrame.intersection(frame)
        guard !vis.isNull else { return false }
        return vis.width * vis.height >= 0.5 * frame.width * frame.height
    }

    /// Move/resize without tripping the save-on-move/resize delegate callbacks.
    private func setPanelFrame(_ frame: NSRect) {
        isRestoring = true
        panel.setFrame(frame, display: true)
        isRestoring = false
    }

    // MARK: NSWindowDelegate — persist frame per display on user move/resize.

    func windowDidMove(_ notification: Notification) {
        guard !isRestoring else { return }
        saveCurrentFrame()
    }
    func windowDidResize(_ notification: Notification) {
        guard !isRestoring else { return }
        saveCurrentFrame()
    }
}
