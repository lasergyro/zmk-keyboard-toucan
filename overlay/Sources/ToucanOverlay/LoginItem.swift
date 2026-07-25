import Foundation
import ServiceManagement

/// "Start at Login", backed by `SMAppService.mainApp` — the modern (macOS 13+)
/// replacement for login-item helpers and `LSSharedFileList`.
///
/// The state lives with the system, not in `UserDefaults`: it survives a reset
/// of the app's preferences and stays in sync with System Settings › General ›
/// Login Items, where the user can flip it independently of our menu.
enum LoginItem {

    /// Only a real `.app` bundle can register — a bare `swift run` binary has
    /// nothing for `launchd` to point at.
    static var isSupported: Bool {
        Bundle.main.bundleIdentifier != nil && Bundle.main.bundleURL.pathExtension == "app"
    }

    static var status: SMAppService.Status {
        isSupported ? SMAppService.mainApp.status : .notFound
    }

    static var isEnabled: Bool { status == .enabled }

    /// The user switched it off in System Settings; `register()` can't override
    /// that — they have to re-approve it there.
    static var requiresApproval: Bool { status == .requiresApproval }

    /// Registers/unregisters the app. Returns `nil` on success, else the error.
    @discardableResult
    static func setEnabled(_ enabled: Bool) -> Error? {
        guard isSupported else {
            return error("Launching at login needs the app bundle — run ToucanOverlay.app "
                         + "(build it with ./build.sh) rather than the bare binary.")
        }
        do {
            if enabled {
                // Registering while already registered throws, so clear any
                // stale registration first (e.g. the bundle was moved since).
                if SMAppService.mainApp.status == .enabled {
                    try? SMAppService.mainApp.unregister()
                }
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
            return nil
        } catch {
            return error
        }
    }

    /// Opens the System Settings pane where a denied registration is approved.
    static func openSystemSettings() {
        SMAppService.openSystemSettingsLoginItems()
    }

    private static func error(_ message: String) -> Error {
        NSError(domain: "dev.toucan.overlay", code: 1,
                userInfo: [NSLocalizedDescriptionKey: message])
    }
}
