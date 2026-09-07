import AppIntents
import Foundation

enum WidgetLayout: String, AppEnum, CaseIterable {
    case all
    case combined
    case one

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Layout"
    static var caseDisplayRepresentations: [WidgetLayout: DisplayRepresentation] = [
        .all: "All accounts",
        .combined: "Combined remaining",
        .one: "One account",
    ]
}

enum WidgetWindows: String, AppEnum, CaseIterable {
    case fiveHour = "5h"
    case sevenDay = "7d"
    case both

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Windows"
    static var caseDisplayRepresentations: [WidgetWindows: DisplayRepresentation] = [
        .fiveHour: "5-hour",
        .sevenDay: "7-day",
        .both: "5-hour and 7-day",
    ]
}

struct AccountEntity: AppEntity, Hashable {
    var id: String
    var title: String
    var subtitle: String

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Account"
    static var defaultQuery = AccountEntityQuery()

    var displayRepresentation: DisplayRepresentation {
        if subtitle.isEmpty {
            return DisplayRepresentation(title: "\(title)")
        }
        return DisplayRepresentation(title: "\(title)", subtitle: "\(subtitle)")
    }
}

struct AccountEntityQuery: EntityQuery {
    func entities(for identifiers: [AccountEntity.ID]) async throws -> [AccountEntity] {
        let wanted = Set(identifiers)
        return Self.load().filter { wanted.contains($0.id) }
    }

    func suggestedEntities() async throws -> [AccountEntity] {
        Self.load()
    }

    func defaultResult() async -> AccountEntity? {
        Self.load().first
    }

    private static func load() -> [AccountEntity] {
        (SnapshotStore.load()?.accounts ?? []).map {
            AccountEntity(id: $0.num, title: $0.title, subtitle: $0.subtitle)
        }
    }
}

struct OpenSwapWidgetIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "openswap"
    static var description = IntentDescription(
        "Choose all accounts, combined remaining, or one account."
    )

    @Parameter(title: "Layout", default: .all)
    var layout: WidgetLayout

    @Parameter(title: "Windows", default: .both)
    var windows: WidgetWindows

    @Parameter(
        title: "Account",
        description: "Used when layout is One account."
    )
    var account: AccountEntity?

    init() {
        layout = .all
        windows = .both
        account = nil
    }

    init(layout: WidgetLayout, windows: WidgetWindows, account: AccountEntity? = nil) {
        self.layout = layout
        self.windows = windows
        self.account = account
    }

    static var parameterSummary: some ParameterSummary {
        When(\OpenSwapWidgetIntent.$layout, .equalTo, WidgetLayout.one) {
            Summary("\(\.$layout) · \(\.$windows) · \(\.$account)")
        } otherwise: {
            Summary("\(\.$layout) · \(\.$windows)")
        }
    }
}
