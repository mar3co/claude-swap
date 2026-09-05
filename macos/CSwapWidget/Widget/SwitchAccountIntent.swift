import AppIntents
import Foundation

struct SwitchAccountIntent: AppIntent {
    static var title: LocalizedStringResource = "Switch cswap account"
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Account")
    var num: String

    init() {
        self.num = ""
    }

    init(num: String) {
        self.num = num
    }

    func perform() async throws -> some IntentResult {
        try writeSwitchCommand(num: num)
        return .result()
    }
}

private func writeSwitchCommand(num: String) throws {
    let dir = realHomeDirectory()
        .appendingPathComponent("Library/Application Support/cswap")
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    let dest = dir.appendingPathComponent("widget-command.json")
    let payload: [String: Any] = [
        "op": "switch",
        "num": num,
        "at": Date().timeIntervalSince1970,
    ]
    let data = try JSONSerialization.data(withJSONObject: payload)
    try data.write(to: dest, options: .atomic)
}
