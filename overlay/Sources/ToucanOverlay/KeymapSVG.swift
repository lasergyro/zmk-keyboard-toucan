import Foundation

/// Loads the generated keymap SVG and post-processes it for the overlay:
///   * drops the bottom watermark/footer label ("zmk-keyboard-toucan")
///   * makes the SVG page background transparent so the window's frosted
///     "liquid glass" material shows through
///   * gives the key rects a touch of translucency so the haze reads through
///     the whole panel while keeping the legends readable
enum KeymapSVG {

    /// Natural size of the source drawing — the render size for the PDF, and
    /// the ratio the window's aspect is locked to.
    static let size = CGSize(width: 844, height: 693)

    static func process(_ raw: String) -> String {
        var s = raw

        // Drop the footer watermark label at the bottom of the drawing.
        if let re = try? NSRegularExpression(
            pattern: "<text[^>]*class=\"footer\"[^>]*>.*?</text>",
            options: [.dotMatchesLineSeparators]
        ) {
            let range = NSRange(s.startIndex..., in: s)
            s = re.stringByReplacingMatches(in: s, range: range, withTemplate: "")
        }

        // Liquid-glass tweaks: transparent page background + slightly
        // translucent keys, injected just before the closing </style>.
        let inject = """

        /* --- toucan overlay: liquid-glass post-processing --- */
        svg.keymap { background: transparent !important; }
        rect.key { fill-opacity: 0.82; }
        rect.combo, rect.combo-separate { fill-opacity: 0.85; }

        """
        if let r = s.range(of: "</style>") {
            s.replaceSubrange(r, with: inject + "</style>")
        }
        return s
    }

    /// Wraps the processed SVG in a transparent, edge-to-edge HTML page — the
    /// input to the one-off PDF render in `KeymapRenderer`.
    static func html(svg: String) -> String {
        """
        <!doctype html><html><head><meta charset="utf-8">
        <style>
          html, body { margin: 0; height: 100%; background: transparent; overflow: hidden; }
          svg.keymap { display: block; width: 100% !important; height: 100% !important; }
        </style></head>
        <body>\(svg)</body></html>
        """
    }
}

/// Resolves the source keymap.svg. Prefers the repo's live file (so the overlay
/// reflects re-generated keymaps automatically), falling back to the bundled
/// copy.
enum KeymapSource {

    static func resolvedPath() -> String? {
        let fm = FileManager.default
        if let p = ProcessInfo.processInfo.environment["TOUCAN_KEYMAP_SVG"],
           fm.fileExists(atPath: p) { return p }
        if let p = discoverRepoSVG() { return p }
        return nil
    }

    /// Walk up from the .app location looking for `draw/keymap.svg` — when the
    /// app lives inside the repo (overlay/), this finds the live drawing.
    static func discoverRepoSVG() -> String? {
        let fm = FileManager.default
        var url = Bundle.main.bundleURL
        for _ in 0..<8 {
            url = url.deletingLastPathComponent()
            let candidate = url.appendingPathComponent("draw/keymap.svg")
            if fm.fileExists(atPath: candidate.path) { return candidate.path }
        }
        return nil
    }

    static func load() -> String {
        if let p = resolvedPath(), let s = try? String(contentsOfFile: p, encoding: .utf8) {
            return s
        }
        if let s = bundledSVG() { return s }
        return "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"keymap\" viewBox=\"0 0 844 693\"><text x=\"30\" y=\"40\" fill=\"#eadbb0\" font-family=\"monospace\">keymap.svg not found</text></svg>"
    }

    /// The copy shipped inside the app — also what the build-time PDF was
    /// rendered from, so matching it means that PDF can be used as-is.
    static func bundledSVG() -> String? {
        guard let u = bundledURL("keymap", "svg") else { return nil }
        return try? String(contentsOf: u, encoding: .utf8)
    }

    /// Bundled-resource lookup, `.app` first. `Bundle.module` can resolve to a
    /// leftover SwiftPM bundle under `.build/` — fine when running straight out
    /// of the build directory, but stale for an assembled app, which carries
    /// the matched keymap.svg/keymap.pdf pair in `Contents/Resources`.
    static func bundledURL(_ name: String, _ ext: String) -> URL? {
        Bundle.main.url(forResource: name, withExtension: ext)
            ?? Bundle.module.url(forResource: name, withExtension: ext)
    }
}
