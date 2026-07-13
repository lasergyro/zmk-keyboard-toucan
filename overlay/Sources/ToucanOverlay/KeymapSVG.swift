import Foundation

/// Loads the generated keymap SVG and post-processes it for the overlay:
///   * drops the bottom watermark/footer label ("zmk-keyboard-toucan")
///   * makes the SVG page background transparent so the window's frosted
///     "liquid glass" material shows through
///   * gives the key rects a touch of translucency so the haze reads through
///     the whole panel while keeping the legends readable
enum KeymapSVG {

    /// Aspect ratio of the source drawing (used to lock the window aspect).
    static let aspect = CGSize(width: 844, height: 693)

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

    /// Wraps the processed SVG in a transparent, edge-to-edge HTML page.
    static func html(svg: String) -> String {
        """
        <!doctype html><html><head><meta charset="utf-8">
        <style>
          html, body { margin: 0; height: 100%; background: transparent; overflow: hidden; }
          * {
            -webkit-user-select: none; user-select: none;
            -webkit-touch-callout: none; cursor: default;
          }
          svg.keymap { display: block; width: 100% !important; height: 100% !important;
                       pointer-events: none; }
        </style></head>
        <body>\(svg)</body></html>
        """
    }
}

/// Resolves the source keymap.svg. Prefers a live file (so the overlay reflects
/// re-generated keymaps automatically), falling back to the bundled copy.
enum KeymapSource {

    static let defaultsKey = "keymapSVGPath"

    static func resolvedPath() -> String? {
        let fm = FileManager.default
        if let p = ProcessInfo.processInfo.environment["TOUCAN_KEYMAP_SVG"],
           fm.fileExists(atPath: p) { return p }
        if let p = UserDefaults.standard.string(forKey: defaultsKey),
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
        if let u = Bundle.module.url(forResource: "keymap", withExtension: "svg"),
           let s = try? String(contentsOf: u, encoding: .utf8) {
            return s
        }
        return "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"keymap\" viewBox=\"0 0 844 693\"><text x=\"30\" y=\"40\" fill=\"#eadbb0\" font-family=\"monospace\">keymap.svg not found</text></svg>"
    }
}
