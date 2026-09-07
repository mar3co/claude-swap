import AppIntents
import SwiftUI
import WidgetKit

struct CSwapEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot?
    let configuration: CSwapWidgetIntent
}

struct CSwapProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> CSwapEntry {
        CSwapEntry(date: Date(), snapshot: .sample, configuration: CSwapWidgetIntent())
    }

    func snapshot(for configuration: CSwapWidgetIntent, in context: Context) async -> CSwapEntry {
        CSwapEntry(
            date: Date(),
            snapshot: SnapshotStore.load() ?? .sample,
            configuration: configuration
        )
    }

    func timeline(
        for configuration: CSwapWidgetIntent,
        in context: Context
    ) async -> Timeline<CSwapEntry> {
        let snapshot = SnapshotStore.load()
        let now = Date()
        let entries = (0 ..< 30).map { offset in
            CSwapEntry(
                date: now.addingTimeInterval(Double(offset) * 60),
                snapshot: snapshot,
                configuration: configuration
            )
        }
        return Timeline(entries: entries, policy: .after(now.addingTimeInterval(30 * 60)))
    }
}

struct CSwapUsageWidget: Widget {
    let kind = "CSwapUsage"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: CSwapWidgetIntent.self,
            provider: CSwapProvider()
        ) { entry in
            CSwapWidgetView(entry: entry)
        }
        .configurationDisplayName("cswap")
        .description("Usage for your cswap accounts. Right-click to change the layout.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .systemLarge,
            .systemExtraLarge,
        ])
    }
}

@main
struct CSwapWidgetBundle: WidgetBundle {
    var body: some Widget {
        CSwapUsageWidget()
    }
}
