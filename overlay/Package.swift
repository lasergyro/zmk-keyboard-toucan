// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "ToucanOverlay",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "ToucanOverlay",
            resources: [
                .copy("Resources/keymap.svg"),
                .copy("Resources/toucan-menubar.pdf"),
            ]
        )
    ]
)
