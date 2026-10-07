import AppKit
import LocalAuthentication

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let context = LAContext()
context.localizedCancelTitle = "Deny access"
var error: NSError?
if !context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) {
    fputs("Native authentication unavailable\n", stderr)
    exit(2)
}
if CommandLine.arguments.contains("--check") { print("available"); exit(0) }
let reason: String
if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--file-access" {
    reason = CommandLine.arguments[2]
} else if CommandLine.arguments.count == 2 {
    reason = "Allow the requested demo agent session to read and list Demo / Contracts for 10 minutes. Request \(CommandLine.arguments[1]). No real files are exposed."
} else { exit(2) }
app.activate(ignoringOtherApps: true)
context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) { success, _ in
    DispatchQueue.main.async { exit(success ? 0 : 1) }
}
DispatchQueue.main.asyncAfter(deadline: .now() + 90) {
    context.invalidate()
    exit(3)
}
app.run()
