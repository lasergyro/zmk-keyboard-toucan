import AppKit
import WebKit

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
    private let frameAutosave = "ToucanOverlayFrame.v2"   // bumped: reset to new default size
    private let corner: CGFloat = 20
    private let resizeMargin: CGFloat = 8                 // outer ring reserved for edge-resize

    /// Default footprint: a quarter of the screen in each dimension, aspect-fit.
    private let defaultScreenFraction: CGFloat = 0.25

    override init() {
        let cfg = WKWebViewConfiguration()
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 400, height: 400),
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
    }

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
        panel.setFrameAutosaveName(frameAutosave)
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

    /// Restore the saved frame, or size/position to the default (top-right).
    func restoreOrPosition() {
        if panel.setFrameUsingName(frameAutosave) { return }
        resetPosition()
    }

    func resetPosition() {
        guard let vf = (panel.screen ?? NSScreen.main)?.visibleFrame else { return }
        let boxW = vf.width * defaultScreenFraction
        let boxH = vf.height * defaultScreenFraction
        let scale = min(boxW / aspect.width, boxH / aspect.height)
        let w = aspect.width * scale
        let h = aspect.height * scale
        let margin: CGFloat = 16
        panel.setFrame(
            NSRect(x: vf.maxX - w - margin, y: vf.maxY - h - margin, width: w, height: h),
            display: true
        )
    }

    // MARK: NSWindowDelegate — persist frame on move/resize.

    func windowDidMove(_ notification: Notification) { panel.saveFrame(usingName: frameAutosave) }
    func windowDidResize(_ notification: Notification) { panel.saveFrame(usingName: frameAutosave) }
}
