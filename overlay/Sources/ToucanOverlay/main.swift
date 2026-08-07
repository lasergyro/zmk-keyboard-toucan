import AppKit

// Build-time hook (see build.sh): render an SVG into the vector PDF that ships
// inside the .app, so the shipped app never has to start WebKit itself.
//
//   ToucanOverlay --render-pdf <keymap.svg> <keymap.pdf>
if CommandLine.arguments.count == 4, CommandLine.arguments[1] == "--render-pdf" {
    RenderPDFCommand.run(svgPath: CommandLine.arguments[2], outPath: CommandLine.arguments[3])
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
