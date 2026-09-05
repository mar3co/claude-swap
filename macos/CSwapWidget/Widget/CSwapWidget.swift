import SwiftUI
import WidgetKit

struct CSwapEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot?
}

struct CSwapProvider: TimelineProvider {
    func placeholder(in context: Context) -> CSwapEntry {
        CSwapEntry(date: Date(), snapshot: .sample)
    }

    func getSnapshot(in context: Context, completion: @escaping (CSwapEntry) -> Void) {
        completion(CSwapEntry(date: Date(), snapshot: SnapshotStore.load() ?? .sample))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<CSwapEntry>) -> Void) {
        let snapshot = SnapshotStore.load()
        let now = Date()
        let entries = (0 ..< 30).map { offset in
            CSwapEntry(date: now.addingTimeInterval(Double(offset) * 60), snapshot: snapshot)
        }
        let refresh = now.addingTimeInterval(30 * 60)
        completion(Timeline(entries: entries, policy: .after(refresh)))
    }
}

struct CSwapUsageWidget: Widget {
    let kind = "CSwapUsage"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: CSwapProvider()) { entry in
            CSwapWidgetView(entry: entry)
        }
        .configurationDisplayName("cswap")
        .description("Claude Code usage for your cswap accounts.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

@main
struct CSwapWidgetBundle: WidgetBundle {
    var body: some Widget {
        CSwapUsageWidget()
    }
}
