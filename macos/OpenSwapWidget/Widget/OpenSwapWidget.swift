import AppIntents
import SwiftUI
import WidgetKit

struct OpenSwapEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot?
    let configuration: OpenSwapWidgetIntent
}

struct OpenSwapProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> OpenSwapEntry {
        OpenSwapEntry(date: Date(), snapshot: .sample, configuration: OpenSwapWidgetIntent())
    }

    func snapshot(for configuration: OpenSwapWidgetIntent, in context: Context) async -> OpenSwapEntry {
        OpenSwapEntry(
            date: Date(),
            snapshot: SnapshotStore.load() ?? .sample,
            configuration: configuration
        )
    }

    func timeline(
        for configuration: OpenSwapWidgetIntent,
        in context: Context
    ) async -> Timeline<OpenSwapEntry> {
        let snapshot = SnapshotStore.load()
        let now = Date()
        let entries = (0 ..< 30).map { offset in
            OpenSwapEntry(
                date: now.addingTimeInterval(Double(offset) * 60),
                snapshot: snapshot,
                configuration: configuration
            )
        }
        return Timeline(entries: entries, policy: .after(now.addingTimeInterval(30 * 60)))
    }
}

struct OpenSwapUsageWidget: Widget {
    let kind = "OpenSwapUsage"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: OpenSwapWidgetIntent.self,
            provider: OpenSwapProvider()
        ) { entry in
            OpenSwapWidgetView(entry: entry)
        }
        .configurationDisplayName("OpenSwap")
        .description("Usage for your OpenSwap accounts. Right-click to change the layout.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .systemLarge,
            .systemExtraLarge,
        ])
    }
}

@main
struct OpenSwapWidgetBundle: WidgetBundle {
    var body: some Widget {
        OpenSwapUsageWidget()
    }
}
