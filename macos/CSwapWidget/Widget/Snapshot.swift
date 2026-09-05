import Darwin
import Foundation

struct WidgetSnapshot: Codable {
    var schema: Int
    var updatedAt: Double
    var accounts: [AccountCard]
}

struct AccountCard: Codable, Identifiable {
    var num: String
    var title: String
    var subtitle: String
    var active: Bool
    var disabled: Bool
    var note: String?
    var windows: [UsageWindow]
    var id: String { num }
}

struct UsageWindow: Codable, Identifiable {
    var label: String
    var pct: Double
    var countdown: String?
    var resetsAtTs: Double?
    var ahead: Bool
    var maxed: Bool
    var id: String { label }
}

enum SnapshotStore {
    static var fileURL: URL {
        realHomeDirectory()
            .appendingPathComponent("Library/Application Support/cswap/widget-snapshot.json")
    }

    static func load() -> WidgetSnapshot? {
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(WidgetSnapshot.self, from: data)
    }
}

func realHomeDirectory() -> URL {
    if let pw = getpwuid(getuid()), let dir = pw.pointee.pw_dir {
        return URL(fileURLWithPath: String(cString: dir))
    }
    return FileManager.default.homeDirectoryForCurrentUser
}

func liveCountdown(resetsAtTs: Double?, now: Date, fallback: String?) -> String? {
    guard let ts = resetsAtTs else { return fallback }
    let remaining = Int(ts - now.timeIntervalSince1970)
    if remaining <= 0 { return nil }
    let days = remaining / 86_400
    let hours = (remaining % 86_400) / 3_600
    let minutes = (remaining % 3_600) / 60
    if days > 0 { return "\(days)d \(hours)h" }
    if hours > 0 { return "\(hours)h \(minutes)m" }
    return "\(minutes)m"
}

extension WidgetSnapshot {
    static var sample: WidgetSnapshot {
        let now = Date().timeIntervalSince1970
        return WidgetSnapshot(
            schema: 1,
            updatedAt: now,
            accounts: [
                AccountCard(
                    num: "1",
                    title: "personal",
                    subtitle: "you@example.com",
                    active: true,
                    disabled: false,
                    note: nil,
                    windows: [
                        UsageWindow(
                            label: "5h", pct: 42, countdown: "2h 10m",
                            resetsAtTs: now + 7_800, ahead: false, maxed: false
                        ),
                        UsageWindow(
                            label: "7d", pct: 18, countdown: "3d 21h",
                            resetsAtTs: now + 334_800, ahead: false, maxed: false
                        ),
                    ]
                )
            ]
        )
    }
}
