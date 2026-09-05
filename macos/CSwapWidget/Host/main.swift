import AppKit
import WidgetKit

/// Accessory host so WidgetKit has an app to attach to, and so snapshot
/// writes from the Python extra can reload timelines immediately.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        DistributedNotificationCenter.default().addObserver(
            self,
            selector: #selector(reloadWidgets(_:)),
            name: Notification.Name("com.cswap.widget.reload"),
            object: nil
        )
        WidgetCenter.shared.reloadAllTimelines()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    @objc private func reloadWidgets(_ notification: Notification) {
        WidgetCenter.shared.reloadAllTimelines()
    }
}

private let appDelegate = AppDelegate()

autoreleasepool {
    let app = NSApplication.shared
    app.delegate = appDelegate
    app.setActivationPolicy(.accessory)
    app.run()
}
