import AppKit
import CryptoKit
import WebKit

/// Turns the keymap SVG into a vector PDF image.
///
/// WebKit is the only renderer that draws the generated SVG correctly (the SVG
/// support in `NSImage` ignores most of keymap-drawer's stylesheet), but a live
/// `WKWebView` costs three resident XPC processes (~70 MB) for a drawing that
/// never changes. So WebKit runs at most once per keymap — off-screen, into a
/// PDF — and is then torn down. What stays resident is a ~60 KB vector image
/// that rasterizes at whatever size the panel happens to be, at any display
/// scale, instead of a bitmap sized for the largest monitor imaginable.
///
/// Sources, in order: the PDF pre-rendered at build time into the app bundle →
/// an on-disk cache keyed by SVG content → a fresh render, for a keymap this
/// machine hasn't drawn before.
///
/// That last one runs `--render-pdf` in a child process rather than in-process:
/// WebKit's GPU and Networking helpers outlive the web view that started them,
/// so a render here would leave ~40 MB attached to a long-lived menu-bar app.
/// A child takes it all with it when it exits.
enum KeymapRenderer {

    /// Resolves `svg` to a drawable image, calling back on the main queue.
    static func image(for svg: String, completion: @escaping (NSImage?) -> Void) {
        if let image = bundledImage(for: svg) {
            completion(image)
            return
        }
        let key = digest(KeymapSVG.html(svg: KeymapSVG.process(svg)))
        if let image = NSImage(contentsOf: cacheURL(for: key)) {
            completion(image)
            return
        }
        renderInChildProcess(svg: svg, key: key, completion: completion)
    }

    /// Renders an SVG to PDF data through an off-screen WebKit view — the
    /// `--render-pdf` implementation, in the child process and at build time.
    static func renderPDF(svg: String, completion: @escaping (Data?) -> Void) {
        _ = PDFRenderJob(html: KeymapSVG.html(svg: KeymapSVG.process(svg)), completion: completion)
    }

    private static func renderInChildProcess(svg: String, key: String,
                                             completion: @escaping (NSImage?) -> Void) {
        guard let executable = Bundle.main.executableURL else { completion(nil); return }
        let pdf = cacheURL(for: key)
        DispatchQueue.global(qos: .userInitiated).async {
            let svgFile = FileManager.default.temporaryDirectory
                .appendingPathComponent("toucan-keymap-\(key).svg")
            defer { try? FileManager.default.removeItem(at: svgFile) }

            var image: NSImage?
            if (try? svg.write(to: svgFile, atomically: true, encoding: .utf8)) != nil {
                let render = Process()
                render.executableURL = executable
                render.arguments = ["--render-pdf", svgFile.path, pdf.path]
                if (try? render.run()) != nil {
                    render.waitUntilExit()
                    if render.terminationStatus == 0 {
                        image = NSImage(contentsOf: pdf)
                        pruneCache(keeping: pdf)
                    }
                }
            }
            DispatchQueue.main.async { completion(image) }
        }
    }

    // MARK: Pre-rendered sources

    /// The build-time render, usable only when it matches the SVG we were asked
    /// for — the live `draw/keymap.svg` normally *is* the bundled one, so this
    /// is the everyday path and it never touches WebKit.
    private static func bundledImage(for svg: String) -> NSImage? {
        guard svg == KeymapSource.bundledSVG(),
              let url = KeymapSource.bundledURL("keymap", "pdf")
        else { return nil }
        return NSImage(contentsOf: url)
    }

    private static func digest(_ s: String) -> String {
        SHA256.hash(data: Data(s.utf8)).prefix(8).map { String(format: "%02x", $0) }.joined()
    }

    private static func cacheURL(for key: String) -> URL {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("dev.toucan.overlay", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("keymap-\(key).pdf")
    }

    /// Renders of older keymaps are never read back — drop them.
    private static func pruneCache(keeping url: URL) {
        let siblings = (try? FileManager.default.contentsOfDirectory(
            at: url.deletingLastPathComponent(), includingPropertiesForKeys: nil)) ?? []
        for f in siblings where f.lastPathComponent.hasPrefix("keymap-") && f != url {
            try? FileManager.default.removeItem(at: f)
        }
    }
}

/// `--render-pdf`: the build-time entry point that produces the PDF shipped in
/// the app bundle. Same renderer, run once on the build machine.
enum RenderPDFCommand {

    static func run(svgPath: String, outPath: String) -> Never {
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)      // WebKit needs a GUI session, not a UI

        guard let svg = try? String(contentsOfFile: svgPath, encoding: .utf8) else {
            fail("cannot read \(svgPath)")
        }
        DispatchQueue.main.async {
            KeymapRenderer.renderPDF(svg: svg) { data in
                guard let data else { fail("render failed") }
                do { try data.write(to: URL(fileURLWithPath: outPath), options: .atomic) }
                catch { fail("cannot write \(outPath): \(error.localizedDescription)") }
                exit(0)
            }
        }
        app.run()
        exit(0)
    }

    private static func fail(_ message: String) -> Never {
        FileHandle.standardError.write(Data("render-pdf: \(message)\n".utf8))
        exit(1)
    }
}

/// One off-screen WebKit render, self-retained until it produces a PDF (or
/// gives up), then fully released so WebKit's helper processes exit.
private final class PDFRenderJob: NSObject, WKNavigationDelegate {

    /// Keeps jobs alive for the duration of their render.
    private static var running: [PDFRenderJob] = []

    private let size = KeymapSVG.size
    private var window: NSWindow?
    private var webView: WKWebView?
    private var completion: ((Data?) -> Void)?
    private var timeout: DispatchWorkItem?

    init(html: String, completion: @escaping (Data?) -> Void) {
        super.init()
        self.completion = completion

        let rect = NSRect(origin: .zero, size: size)
        let web = WKWebView(frame: rect, configuration: WKWebViewConfiguration())
        web.setValue(false, forKey: "drawsBackground")   // keep the page transparent in the PDF
        if #available(macOS 12.0, *) { web.underPageBackgroundColor = .clear }
        web.navigationDelegate = self

        // WebKit only paints content that belongs to a window; this one is
        // transparent and parked off-screen, so it is never seen.
        let win = NSWindow(contentRect: rect, styleMask: [.borderless],
                           backing: .buffered, defer: false)
        win.isOpaque = false
        win.backgroundColor = .clear
        win.alphaValue = 0
        win.contentView = web
        win.setFrameOrigin(NSPoint(x: -30_000, y: -30_000))
        win.orderBack(nil)

        webView = web
        window = win
        Self.running.append(self)

        let bail = DispatchWorkItem { [weak self] in self?.finish(nil) }
        timeout = bail
        DispatchQueue.main.asyncAfter(deadline: .now() + 10, execute: bail)

        web.loadHTMLString(html, baseURL: nil)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let config = WKPDFConfiguration()
        config.rect = CGRect(origin: .zero, size: size)
        webView.createPDF(configuration: config) { [weak self] result in
            self?.finish(try? result.get())
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        finish(nil)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        finish(nil)
    }

    private func finish(_ data: Data?) {
        guard let completion else { return }   // already finished (or timed out)
        self.completion = nil
        timeout?.cancel()
        webView?.navigationDelegate = nil
        window?.orderOut(nil)
        window?.contentView = nil
        webView = nil
        window = nil                            // last reference → WebKit's XPC processes exit
        completion(data)
        Self.running.removeAll { $0 === self }
    }
}
