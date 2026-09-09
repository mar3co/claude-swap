import WidgetKit

// Command-line helper that lives in OpenSwap.app/Contents/MacOS. `Bundle.main`
// for an executable inside Contents/MacOS resolves to the enclosing .app, so
// WidgetKit reloads that app's widgets.
WidgetCenter.shared.reloadAllTimelines()
