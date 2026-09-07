import AppIntents
import AppKit
import SwiftUI
import WidgetKit

/// TUI tokens that resolve against the widget's drawing appearance.
/// WidgetKit renders light and dark snapshots; NSColor providers also
/// flip if the desktop widget sits on a light vs dark wallpaper region.
enum Palette {
    static let fg = Color.cswap(light: 0x2B2723, dark: 0xE8E4DE)
    static let muted = Color.cswap(light: 0x635D55, dark: 0x8A8A8A)
    static let accent = Color.cswap(light: 0x954C2A, dark: 0xD7875F)
    static let ok = Color.cswap(light: 0x3D6B3D, dark: 0x87AF87)
    static let warn = Color.cswap(light: 0x795911, dark: 0xD7AF5F)
    static let crit = Color.cswap(light: 0xAD3128, dark: 0xD75F5F)
    static let track = Color.cswap(light: 0xCEC7BA, dark: 0x3A3A3A)

    static func severity(_ pct: Double) -> Color {
        if pct >= 90 { return crit }
        if pct >= 70 { return warn }
        return ok
    }
}

extension Color {
    static func cswap(
        light: UInt32,
        dark: UInt32,
        lightOpacity: Double = 1,
        darkOpacity: Double = 1
    ) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            let hex = isDark ? dark : light
            let opacity = isDark ? darkOpacity : lightOpacity
            return NSColor(
                srgbRed: Double((hex >> 16) & 0xFF) / 255,
                green: Double((hex >> 8) & 0xFF) / 255,
                blue: Double(hex & 0xFF) / 255,
                alpha: opacity
            )
        })
    }
}

struct CSwapWidgetView: View {
    var entry: CSwapEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        let accounts = visibleAccounts
        Group {
            if accounts.isEmpty {
                emptyState()
            } else {
                VStack(alignment: .leading, spacing: family == .systemSmall ? 6 : 8) {
                    ForEach(Array(accounts.enumerated()), id: \.element.id) { index, account in
                        if index > 0 {
                            Divider().opacity(0.35)
                        }
                        accountBlock(for: account)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .containerBackground(.background, for: .widget)
    }

    @ViewBuilder
    private func accountBlock(for account: AccountCard) -> some View {
        let block = AccountBlock(
            account: account,
            now: entry.date,
            compact: family == .systemSmall,
            maxWindows: family == .systemSmall ? 3 : (family == .systemMedium ? 3 : 6)
        )
        if account.disabled {
            block
        } else {
            Button(intent: SwitchAccountIntent(num: account.num)) {
                block
            }
            .buttonStyle(.plain)
        }
    }

    private var visibleAccounts: [AccountCard] {
        let all = entry.snapshot?.accounts ?? []
        if family == .systemSmall {
            if let active = all.first(where: { $0.active }) { return [active] }
            return Array(all.prefix(1))
        }
        let cap = family == .systemLarge ? 6 : 3
        return Array(all.prefix(cap))
    }

    private func emptyState() -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("cswap")
                .font(.headline)
                .foregroundStyle(Palette.fg)
            Text("Waiting for the menu bar extra. Run cswap menubar, then this fills in.")
                .font(.caption)
                .foregroundStyle(Palette.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct AccountBlock: View {
    var account: AccountCard
    var now: Date
    var compact: Bool
    var maxWindows: Int

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 3 : 4) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                if account.active {
                    RoundedRectangle(cornerRadius: 1, style: .continuous)
                        .fill(Palette.accent)
                        .frame(width: 3, height: 12)
                }
                Text(account.title)
                    .font(.system(size: compact ? 12 : 13, weight: .semibold))
                    .foregroundStyle(Palette.fg)
                    .lineLimit(1)
                Spacer(minLength: 4)
                if account.active {
                    Text("active")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(Palette.accent)
                } else if account.disabled {
                    Text("disabled")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(Palette.muted)
                }
            }
            if !account.subtitle.isEmpty {
                Text(account.subtitle)
                    .font(.caption)
                    .foregroundStyle(Palette.muted)
                    .lineLimit(1)
            }
            ForEach(Array(account.windows.prefix(maxWindows))) { window in
                WindowRow(
                    window: window,
                    now: now,
                    compact: compact,
                    stale: account.needsRelogin == true
                )
            }
            if let note = account.note {
                Text(note)
                    .font(.caption)
                    .foregroundStyle(Palette.muted)
                    .lineLimit(1)
            }
        }
        .opacity(account.disabled ? 0.45 : 1)
    }
}

private struct WindowRow: View {
    var window: UsageWindow
    var now: Date
    var compact: Bool
    var stale: Bool = false

    var body: some View {
        let color = stale ? Palette.muted : Palette.severity(window.pct)
        let suffix: String = {
            if stale {
                if let text = liveCountdown(resetsAtTs: window.resetsAtTs, now: now, fallback: window.countdown) {
                    return text
                }
                return ""
            }
            if window.maxed { return "max" }
            if let text = liveCountdown(resetsAtTs: window.resetsAtTs, now: now, fallback: window.countdown) {
                return text
            }
            if window.ahead { return "ahead" }
            return ""
        }()
        HStack(spacing: 6) {
            Text(window.label)
                .font(.system(size: compact ? 10 : 11, weight: .medium).monospacedDigit())
                .foregroundStyle(Palette.muted)
                .frame(width: compact ? 32 : 40, alignment: .leading)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            UsageBar(pct: window.pct, fill: color, track: Palette.track)
                .frame(height: 5)
            Text("\(Int(window.pct.rounded()))%")
                .font(.system(size: compact ? 10 : 11, weight: .medium).monospacedDigit())
                .foregroundStyle(color)
                .frame(width: compact ? 32 : 36, alignment: .trailing)
            Text(suffix)
                .font(.system(size: compact ? 10 : 11).monospacedDigit())
                .foregroundStyle(Palette.muted)
                .frame(width: compact ? 44 : 52, alignment: .trailing)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
    }
}

private struct UsageBar: View {
    var pct: Double
    var fill: Color
    var track: Color

    var body: some View {
        GeometryReader { geo in
            let fraction = min(max(pct, 0), 100) / 100
            ZStack(alignment: .leading) {
                Capsule().fill(track)
                Capsule()
                    .fill(fill)
                    .frame(width: geo.size.width * fraction)
            }
        }
    }
}
