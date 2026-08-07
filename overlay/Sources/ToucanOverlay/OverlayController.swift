import AppKit

/// Transparent overlay that sits above the keymap and turns any click-drag into
/// a window move. Because it covers the image, nothing underneath ever receives
/// mouse events.
private final class DragView: NSView {
    override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) }
    override var mouseDownCanMoveWindow: Bool { true }
    override var acceptsFirstResponder: Bool { false }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
    /// The panel has no menu of its own; suppress the inherited one.
    override func menu(for event: NSEvent) -> NSMenu? { nil }
}

/// Borderless, floating, non-activating glass panel that renders the keymap.
/// Drag anywhere to move; resize from the edges with a locked aspect ratio.
///
/// The panel is built the first time the overlay is shown, and the keymap it
/// displays is a vector PDF image (see `KeymapRenderer`) — an app that has been
/// launched but never asked for the overlay holds neither a window nor a
/// renderer.
final class OverlayController: NSObject, NSWindowDelegate {

    private var panel: NSPanel?
    private var imageView: NSImageView?

    /// The rendered keymap, kept across hides so showing again is instant.
    private var keymap: NSImage?

    private let aspect = KeymapSVG.size
    private let corner: CGFloat = 20
    private let resizeMargin: CGFloat = 8                 // outer ring reserved for edge-resize

    /// Default footprint: aspect-fit into 4/5 of the visible screen, so the
    /// overlay fills 4/5 of whichever axis constrains it first, and centred.
    private let defaultScreenFraction: CGFloat = 0.8

    // Per-display geometry: each physical display remembers its own size and
    // position, so switching/reconnecting monitors restores the right layout
    // instead of clobbering a single shared frame.
    private let framesKey = "ToucanOverlayFramesByDisplay.v1"
    private let lastDisplayKey = "ToucanOverlayLastDisplay.v1"
    /// Where the panel is (or will be, before it exists).
    private var frame: NSRect = .zero
    /// Suppresses save-on-move/resize while we reposition programmatically.
    private var isRestoring = false

    override init() {
        super.init()
        // Re-apply the per-display layout when monitors are added/removed or
        // rearranged, so the overlay stays valid on whatever screen it's on.
        NotificationCenter.default.addObserver(
            self, selector: #selector(screensChanged),
            name: NSApplication.didChangeScreenParametersNotification, object: nil)
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    // MARK: Panel construction (on first show)

    private func makePanelIfNeeded() {
        guard panel == nil else { return }
        if frame == .zero { restoreOrPosition() }

        let p = NSPanel(contentRect: frame,
                        styleMask: [.borderless, .resizable, .nonactivatingPanel],
                        backing: .buffered, defer: false)
        p.level = .floating
        p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        p.isFloatingPanel = true
        p.hidesOnDeactivate = false
        p.isMovableByWindowBackground = true
        p.isOpaque = false
        p.backgroundColor = .clear
        p.hasShadow = true
        // Dark glass reads better under the dark (gruvbox) keymap.
        p.appearance = NSAppearance(named: .darkAqua)
        p.aspectRatio = aspect
        p.minSize = NSSize(width: 240, height: 240 * aspect.height / aspect.width)
        p.delegate = self
        p.contentView = buildContent(size: frame.size)
        panel = p
        setPanelFrame(frame)
    }

    /// Builds: [ glass ] → contentView( imageView, dragView-on-top ).
    private func buildContent(size: NSSize) -> NSView {
        let content = NSView(frame: NSRect(origin: .zero, size: size))
        content.wantsLayer = true
        content.layer?.cornerRadius = corner
        content.layer?.masksToBounds = true
        content.autoresizingMask = [.width, .height]

        let image = NSImageView(frame: content.bounds)
        image.imageScaling = .scaleAxesIndependently   // the panel's aspect is locked to the drawing's
        image.image = keymap
        image.autoresizingMask = [.width, .height]
        content.addSubview(image)
        imageView = image

        // Drag layer covers everything except the outer resize ring.
        let drag = DragView(frame: content.bounds.insetBy(dx: resizeMargin, dy: resizeMargin))
        drag.autoresizingMask = [.width, .height]
        content.addSubview(drag)

        if #available(macOS 26.0, *) {
            let glass = NSGlassEffectView()
            glass.style = .regular
            glass.cornerRadius = corner
            glass.contentView = content
            return glass
        }
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
        return host
    }

    // MARK: Actions

    /// Re-reads the keymap SVG and re-renders it if its content changed.
    func reload() {
        KeymapRenderer.image(for: KeymapSource.load()) { [weak self] image in
            guard let self, let image else { return }
            self.keymap = image
            self.imageView?.image = image
        }
    }

    var isVisible: Bool { panel?.isVisible ?? false }

    func toggle() {
        if isVisible { hide() } else { show() }
    }

    func show() {
        makePanelIfNeeded()
        panel?.orderFrontRegardless()
    }

    func hide() { panel?.orderOut(nil) }

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
        let f = NSRect(x: vf.midX - w / 2, y: vf.midY - h / 2, width: w, height: h)
        setPanelFrame(f)
        storeFrame(f, for: screen)
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
        guard isVisible else { return }
        restore(on: preferredScreen())
    }

    /// The display last used if it's still connected, else the current one.
    private func preferredScreen() -> NSScreen? {
        let last = UserDefaults.standard.string(forKey: lastDisplayKey)
        return NSScreen.screens.first { displayKey(for: $0) == last } ?? currentScreen()
    }

    /// The screen the overlay most overlaps, else main.
    private func currentScreen() -> NSScreen? {
        NSScreen.screens.max { overlapArea($0) < overlapArea($1) }
            .flatMap { overlapArea($0) > 0 ? $0 : nil } ?? NSScreen.main
    }

    private func overlapArea(_ screen: NSScreen) -> CGFloat {
        let r = screen.frame.intersection(frame)
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
        guard let panel, let screen = currentScreen() else { return }
        frame = panel.frame
        storeFrame(frame, for: screen)
    }

    /// A frame is usable if enough of it lands on the screen's visible area.
    private func isReasonable(_ frame: NSRect, on screen: NSScreen) -> Bool {
        let vis = screen.visibleFrame.intersection(frame)
        guard !vis.isNull else { return false }
        return vis.width * vis.height >= 0.5 * frame.width * frame.height
    }

    /// Move/resize without tripping the save-on-move/resize delegate callbacks.
    /// Before the panel exists this just records where it will open.
    private func setPanelFrame(_ frame: NSRect) {
        self.frame = frame
        guard let panel else { return }
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
