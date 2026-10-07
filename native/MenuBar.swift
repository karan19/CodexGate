import AppKit
import Foundation
import SwiftUI

@_silgen_name("proc_listallpids")
func listPIDs(_ buffer: UnsafeMutableRawPointer?, _ size: Int32) -> Int32
@_silgen_name("proc_pidpath")
func processPath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer, _ size: UInt32) -> Int32
@_silgen_name("sandbox_check")
func sandboxPresence(_ pid: Int32, _ operation: UnsafePointer<CChar>?, _ filter: Int32) -> Int32
@_silgen_name("proc_pidinfo")
func pidInfo(_ pid: Int32, _ flavor: Int32, _ argument: UInt64, _ buffer: UnsafeMutableRawPointer, _ size: Int32) -> Int32

struct AgentProcess {
    let pid: Int32
    let path: String
    let sandbox: Int32
    let desktopChild: Bool
    let parentPID: Int32?
    var label: String { !path.hasSuffix("/codex") ? "Codex desktop" : desktopChild ? "Desktop backend" : "Codex CLI / ancestry unknown" }
}

func inventory() -> [AgentProcess]? {
    let count = listPIDs(nil, 0)
    guard count > 0 else { return nil }
    var pids = [Int32](repeating: 0, count: Int(count) + 1024)
    let used = pids.withUnsafeMutableBytes { listPIDs($0.baseAddress, Int32($0.count)) }
    guard used > 0 else { return nil }
    var results = [AgentProcess]()
    for pid in pids.prefix(min(Int(used), pids.count)) where pid > 0 {
        var buffer = [CChar](repeating: 0, count: 4096)
        let length = buffer.withUnsafeMutableBytes { processPath(pid, $0.baseAddress!, UInt32($0.count)) }
        guard length > 0 else { continue }
        let path = buffer.withUnsafeBufferPointer { String(cString: $0.baseAddress!) }
        let desktop = path == "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT" || path == "/Applications/Codex.app/Contents/MacOS/Codex"
        let backend = path.hasSuffix("/codex")
        if desktop || backend {
            var info = [UInt32](repeating: 0, count: 34)
            let size = info.withUnsafeMutableBytes { pidInfo(pid, 3, 0, $0.baseAddress!, Int32($0.count)) }
            var parentBuffer = [CChar](repeating: 0, count: 4096)
            var parentPath = ""
            if size == 136 {
                let parent = Int32(bitPattern: info[4])
                if parentBuffer.withUnsafeMutableBytes({ processPath(parent, $0.baseAddress!, UInt32($0.count)) }) > 0 {
                    parentPath = parentBuffer.withUnsafeBufferPointer { String(cString: $0.baseAddress!) }
                }
            }
            results.append(AgentProcess(pid: pid, path: path, sandbox: sandboxPresence(pid, nil, 0), desktopChild: parentPath == "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT" || parentPath == "/Applications/Codex.app/Contents/MacOS/Codex", parentPID: size == 136 ? Int32(bitPattern: info[4]) : nil))
        }
    }
    return results.sorted { $0.pid < $1.pid }
}

final class MenuController: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private var status: NSStatusItem!
    private var timer: Timer?
    private var processes: [AgentProcess]?
    private let base = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/CodexGate")
    private var launchProcess: Process?
    private var humanToken: String?
    private var brokerState: [String: Any]?
    private var brokerMessage = "Broker disconnected"
    private var fetching = false
    private var policyPaths: [String] = []
    private var policyName: String?
    private let viewModel = AccessViewModel()
    private let popover = NSPopover()
    private var serviceProcess: Process?
    private var serviceInput: Pipe?
    private var agentToken: String?
    private var outputBuffer = Data()
    private var controllerIsSandboxed: Bool { sandboxPresence(getpid(), nil, 0) != 0 }

    private var packagedBackend: URL? {
        guard let resources = Bundle.main.resourceURL else { return nil }
        let url = resources.appendingPathComponent("backend/codexgate-service")
        return FileManager.default.isExecutableFile(atPath: url.path) ? url : nil
    }
    private var installedController: Bool {
        let path = Bundle.main.bundleURL.path
        return path.hasPrefix(base.appendingPathComponent("menu-bar/").path) || (packagedBackend != nil && (path.hasPrefix("/Applications/") || path.hasPrefix(FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications/").path)))
    }
    private func configureBackend(_ task: Process, mode: String, arguments: [String]) {
        if let executable = packagedBackend { task.executableURL = executable; task.arguments = [mode] + arguments }
        else {
            task.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/python3")
            task.arguments = [base.appendingPathComponent("menu-bar/" + (mode == "broker" ? "file_broker.py" : "managed_launch.py")).path] + arguments
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        status.button?.target = self; status.button?.action = #selector(togglePopover)
        let host = NSHostingController(rootView: AccessPopover(model: viewModel) { [weak self] command, id in self?.perform(command, id) })
        host.sizingOptions = [.preferredContentSize]
        popover.contentViewController = host; popover.behavior = .transient
        popover.animates = false // Disclosure animations stay inside a stable native surface.
        loadInstalledPolicy()
        refresh()
        fetchBroker()
        startAccessService()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.fetchBroker(); self?.refresh() }
    }

    @objc private func refresh() {
        processes = inventory()
        let rows = processes ?? []
        let summary: String
        if processes == nil { summary = "Access status unavailable" }
        else if rows.isEmpty { summary = "Codex not running" }
        else if rows.contains(where: { $0.sandbox == 0 }) { summary = "Unprotected process detected" }
        else if rows.contains(where: { $0.sandbox != 1 }) { summary = "Access status unverified" }
        else { summary = "Sandbox detected · rules unverified" }
        let requests = brokerState?["requests"] as? [[String: Any]] ?? []
        let pending = requests.filter { $0["status"] as? String == "pending" }.count
        let active = requests.filter { $0["status"] as? String == "active" }.count
        // A chat bubble plus a distinct padlock; monochrome for native menu-bar contrast.
        let icon = NSImage(size: NSSize(width: 24, height: 18))
        icon.lockFocus()
        let bubble = NSBezierPath(roundedRect: NSRect(x: 1, y: 5, width: 17, height: 12), xRadius: 4, yRadius: 4)
        bubble.lineWidth = 1.4
        NSColor.black.setStroke(); bubble.stroke()
        let tail = NSBezierPath()
        tail.move(to: NSPoint(x: 4, y: 5)); tail.line(to: NSPoint(x: 4, y: 2.5)); tail.line(to: NSPoint(x: 7.5, y: 5))
        tail.lineWidth = 1.4; tail.stroke()
        // Two small conversation dots identify chat without crowding the lock badge.
        NSColor.black.setFill()
        NSBezierPath(ovalIn: NSRect(x: 5, y: 10, width: 1.7, height: 1.7)).fill()
        NSBezierPath(ovalIn: NSRect(x: 9, y: 10, width: 1.7, height: 1.7)).fill()
        // Clear the bubble behind the badge so both outlines remain legible.
        NSRect(x: 13, y: 0, width: 11, height: 12).fill(using: .clear)
        let shackle = NSBezierPath(roundedRect: NSRect(x: 16, y: 5, width: 5.5, height: 6), xRadius: 2.7, yRadius: 2.7)
        shackle.lineWidth = 1.5; shackle.stroke()
        NSBezierPath(roundedRect: NSRect(x: 14.5, y: 1, width: 8.5, height: 6.5), xRadius: 1.5, yRadius: 1.5).fill()
        icon.unlockFocus()
        icon.isTemplate = true
        status.button?.image = icon
        status.button?.imagePosition = .imageOnly
        status.button?.title = ""
        status.button?.toolTip = "CodexGate — \(summary). \(pending) pending requests; \(active) active temporary grants. Click to manage folders."
        status.button?.setAccessibilityLabel("CodexGate")
        status.button?.setAccessibilityValue("\(summary); \(pending) pending requests; \(active) active grants")
        viewModel.summary = summary
        viewModel.processes = rows
        viewModel.service = brokerMessage
        viewModel.broker = brokerState
        viewModel.canLaunch = !controllerIsSandboxed && brokerState != nil
        viewModel.canRequest = agentToken != nil
        viewModel.canConfigure = !controllerIsSandboxed && installedController
        viewModel.referencePaths = policyPaths
    }

    @objc private func togglePopover() {
        if popover.isShown { popover.performClose(nil); return }
        refresh()
        if let button = status.button { popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY); NSApp.activate(ignoringOtherApps: true) }
    }
    private func perform(_ command: String, _ id: String?) {
        switch command {
        case "refresh": fetchBroker(); refresh()
        case "launch": startProtected()
        case "approve", "deny", "revoke", "extend":
            guard let id = id else { return }
            popover.performClose(nil)
            let sender = NSMenuItem(); sender.representedObject = ["action": command, "id": id]; brokerAction(sender)
        case "retry": startAccessService()
        case "grant-folders":
            guard let id = id, let data = id.data(using: .utf8), let paths = try? JSONDecoder().decode([String].self, from: data) else { return }
            popover.performClose(nil)
            grantFolders(paths)
        case "request":
            guard let token = humanToken else { return }
            brokerRequest("action", token: token, payload: id.map { ["action": "request", "id": "", "folder": $0] } ?? ["action": "request", "id": ""]) { data in
                guard self.humanToken == token else { return }
                if let data = data { self.brokerState = data; self.refresh() }
                else { self.alert("Request unavailable", "The access service could not create a request. Refresh and try again.") }
            }
        case "copy-request": popover.performClose(nil); copyAccessRequest()
        case "folder": popover.performClose(nil); chooseServiceFolder()
        case "policy": popover.performClose(nil); choosePolicy()
        case "reload": loadInstalledPolicy()
        case "copy-launch":
            let installed = base.appendingPathComponent("menu-bar")
            func quote(_ value: String) -> String { "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'" }
            let launcher = packagedBackend.map { quote($0.path) + " launch" } ?? ("/opt/homebrew/bin/python3 " + quote(installed.appendingPathComponent("managed_launch.py").path))
            let command = launcher + " --config " + quote(installed.appendingPathComponent("permissions.json").path)
            NSPasteboard.general.clearContents(); NSPasteboard.general.setString(command, forType: .string)
            viewModel.draftMessage = "Copied saved-rules launch command. Unsaved changes are not included."
        case "connect": popover.performClose(nil); connectBroker()
        case "disconnect": disconnectBroker()
        case "browser": popover.performClose(nil); openPanel()
        case "trial": popover.performClose(nil); launchTrial()
        case "quit": quit()
        default: break
        }
    }

    private func grantFolders(_ paths: [String]) {
        guard let path = paths.first, let token = humanToken else { return }
        brokerRequest("action", token: token, payload: ["action": "request", "id": "", "folder": path]) { data in
            guard self.humanToken == token else { return }
            guard let result = data?["result"] as? [String: Any], let key = result["id"] as? String else {
                self.alert("Folder unavailable", "This folder could not be added. Choose a specific readable folder outside controller storage."); return
            }
            self.brokerRequest("action", token: token, payload: ["action": "approve", "id": key]) { state in
                guard self.humanToken == token else { return }
                guard let state = state else { self.alert("Grant unavailable", "Approval failed or the service ended."); self.fetchBroker(); return }
                self.brokerState = state; self.refresh()
                // Authentication cancellation stops the remaining group; approved folders retain their grants.
                if state["result"] as? String == "active" { self.grantFolders(Array(paths.dropFirst())) }
            }
        }
    }

    @objc private func launchOriginal() { launch("launch-codex.command") }
    @objc private func showInstances() { viewModel.showFolders = true }
    @objc private func startProtected() {
        if viewModel.draftDirty {
            viewModel.showFolders = true; viewModel.draftMessage = "Save your folder changes before launching."; return
        }
        guard !controllerIsSandboxed, brokerState != nil else { alert("Access service unavailable", "Start the installed CodexGate app normally. Protection will not be started while setup is incomplete."); return }
        guard let rows = inventory() else { alert("Cannot verify running instances", "Refresh and try again. Nothing was stopped."); return }
        if rows.contains(where: { !$0.path.hasSuffix("/codex") }) { alert("Restart required — active runs may be interrupted", "Codex is currently running. Quitting it will interrupt any active chats, tool calls, and runs. Finish your work first, then fully quit Codex and click Start protected Codex again. This launcher will not terminate the existing instance."); return }
        let installed = base.appendingPathComponent("menu-bar")
        guard FileManager.default.fileExists(atPath: installed.appendingPathComponent("permissions.json").path) else { viewModel.showFolders = true; return }
        let confirmation = NSAlert()
        confirmation.alertStyle = .warning
        confirmation.messageText = "Start Codex with saved folder rules?"
        confirmation.informativeText = "These rules apply to the new protected instance. Switching from an existing instance requires quitting Codex, which interrupts active runs. Continue only after your previous work has finished."
        confirmation.addButton(withTitle: "Start protected Codex")
        confirmation.addButton(withTitle: "Cancel")
        guard confirmation.runModal() == .alertFirstButtonReturn else { return }
        let task = Process()
        configureBackend(task, mode: "launch", arguments: ["--config", installed.appendingPathComponent("permissions.json").path])
        task.standardOutput = FileHandle.nullDevice; let errors = Pipe(); task.standardError = errors
        // Drain diagnostics so a running desktop cannot block on a full pipe. Never retain logs or credentials.
        errors.fileHandleForReading.readabilityHandler = { handle in _ = handle.availableData }
        task.terminationHandler = { process in
            errors.fileHandleForReading.readabilityHandler = nil
            try? errors.fileHandleForReading.close()
            DispatchQueue.main.async { if process.terminationStatus != 0 { self.alert("Protected launch failed", "Check your saved folder rules or use the copied Terminal command for diagnostics. No unprotected fallback was launched.") } }
        }
        do { try task.run(); launchProcess = task } catch { alert("Protected launch failed", error.localizedDescription) }
    }
    @objc private func startAccessService() {
        guard !controllerIsSandboxed, installedController else {
            brokerMessage = installedController ? "Open CodexGate normally outside the Codex sandbox" : "Move CodexGate to Applications, eject the disk image, then open the installed app"; refresh(); return
        }
        if serviceProcess?.isRunning == true { return }
        let installed = base.appendingPathComponent("menu-bar")
        let folder = UserDefaults.standard.string(forKey: "temporaryAccessFolder") ?? installed.appendingPathComponent("demo-folder").path
        let task = Process()
        do {
            let demo = installed.appendingPathComponent("demo-folder")
            try FileManager.default.createDirectory(at: demo, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let file = demo.appendingPathComponent("hello.txt")
            if !FileManager.default.fileExists(atPath: file.path) { try "CodexGate demo. No personal data.\n".write(to: file, atomically: true, encoding: .utf8) }
        } catch { brokerMessage = "Cannot prepare local app data"; refresh(); return }
        configureBackend(task, mode: "broker", arguments: ["--root", folder, "--controller"])
        let output = Pipe(); let input = Pipe(); task.standardOutput = output; task.standardInput = input; task.standardError = FileHandle.nullDevice
        outputBuffer = Data(); humanToken = nil; agentToken = nil; brokerState = nil; brokerMessage = "Starting access service…"
        output.fileHandleForReading.readabilityHandler = { handle in
            let bytes = handle.availableData
            DispatchQueue.main.async {
                guard self.serviceProcess === task, !bytes.isEmpty else { return }
                self.outputBuffer.append(bytes)
                guard self.outputBuffer.count <= 8192 else { task.terminate(); return }
                if let end = self.outputBuffer.firstIndex(of: 10) {
                    let line = self.outputBuffer.prefix(upTo: end); self.outputBuffer.removeAll()
                    guard let ready = try? JSONSerialization.jsonObject(with: line) as? [String: Any], ready["ready"] as? Bool == true,
                          let human = ready["human_token"] as? String, let agent = ready["agent_token"] as? String else { task.terminate(); return }
                    self.humanToken = human; self.agentToken = agent; self.fetchBroker()
                }
            }
        }
        task.terminationHandler = { process in
            output.fileHandleForReading.readabilityHandler = nil
            try? output.fileHandleForReading.close()
            DispatchQueue.main.async {
                guard self.serviceProcess === process else { return }
                self.serviceProcess = nil; self.serviceInput = nil; self.humanToken = nil; self.agentToken = nil; self.brokerState = nil
                self.brokerMessage = "Access service stopped · check folder or port conflict in Advanced"; self.refresh()
            }
        }
        do { serviceProcess = task; serviceInput = input; try task.run() }
        catch { serviceProcess = nil; serviceInput = nil; brokerMessage = "Access service could not start" }
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
            if self.serviceProcess === task, self.humanToken == nil {
                self.stopAccessService(); self.brokerMessage = "Access service did not become ready · retry setup"; self.refresh()
            }
        }
        refresh()
    }
    private func stopAccessService() {
        let task = serviceProcess; serviceProcess = nil
        try? serviceInput?.fileHandleForWriting.close(); serviceInput = nil
        if task?.isRunning == true { task?.terminate(); task?.waitUntilExit() }
        humanToken = nil; agentToken = nil; brokerState = nil
    }
    @objc private func chooseServiceFolder() {
        let picker = NSOpenPanel(); picker.canChooseDirectories = true; picker.canChooseFiles = false; picker.allowsMultipleSelection = false
        picker.message = "Choose one folder for temporary read/list requests. Choosing does not approve access. Changing folders ends existing grants."
        guard picker.runModal() == .OK, let url = picker.url else { return }
        let path = url.resolvingSymlinksInPath()
        guard path.path != "/", path.path != FileManager.default.homeDirectoryForCurrentUser.path,
              !base.path.hasPrefix(path.path + "/"), !path.path.hasPrefix(base.path + "/"), path.path != base.path else { alert("Choose a specific private folder", "Root, home and controller folders cannot be broker roots."); return }
        stopAccessService(); UserDefaults.standard.set(path.path, forKey: "temporaryAccessFolder"); startAccessService()
    }
    @objc private func copyAccessRequest() {
        guard let token = agentToken else { return }
        let command = "curl --silent --show-error http://127.0.0.1:8772/request -H 'Authorization: Bearer " + token + "' -H 'Content-Type: application/json' -d '{}'"
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(command, forType: .string)
        alert("Access-request command copied", "Run it in Terminal or give it to the agent to create a pending read/list request. It cannot approve access. It expires when the service restarts. Human approval credentials are not included.")
    }
    @objc private func choosePolicy() {
        let panel = NSOpenPanel(); panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
        panel.showsHiddenFiles = true
        panel.directoryURL = base.appendingPathComponent("releases")
        panel.message = "Select the installed desktop-policy.sb. This displays configuration, not proof of a running process's policy."
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { try readPolicy(url); refresh() }
        catch { alert("Policy unavailable", error.localizedDescription) }
    }
    @objc private func loadInstalledPolicy() {
        do {
            // Read the wrapper as text; never execute it to discover configuration.
            let wrapper = try String(contentsOf: base.appendingPathComponent("launch-codex.command"), encoding: .utf8)
            let regex = try NSRegularExpression(pattern: #"/releases/(release-[A-Za-z0-9]+)/launch_desktop[.]py"#)
            guard let match = regex.firstMatch(in: wrapper, range: NSRange(wrapper.startIndex..., in: wrapper)),
                  let range = Range(match.range(at: 1), in: wrapper) else { throw NSError(domain: "Installed launcher not recognized", code: 1) }
            let release = String(wrapper[range])
            try readPolicy(base.appendingPathComponent("releases/" + release + "/.local/desktop-policy.sb"))
            refresh()
        } catch {
            policyName = nil; policyPaths = []; refresh()
        }
    }
    private func readPolicy(_ url: URL) throws {
            let text = try String(contentsOf: url, encoding: .utf8)
            guard text.contains("(deny file-read-data"), text.contains("(deny file-write*") else { throw NSError(domain: "Unsupported policy", code: 1) }
            let regex = try NSRegularExpression(pattern: #"\((?:subpath|literal) \"([^\"]+)\"\)"#)
            policyPaths = Array(Set(regex.matches(in: text, range: NSRange(text.startIndex..., in: text)).compactMap {
                Range($0.range(at: 1), in: text).map { String(text[$0]) }
            })).sorted()
            // Exclude deny roots: this list is limited to paths inside the require-not exception blocks.
            policyPaths.removeAll { ["/Users", "/Volumes", "/private/tmp", "/private/var/folders", "/dev/null"].contains($0) }
            policyName = url.lastPathComponent
    }
    @objc private func connectBroker() {
        guard !controllerIsSandboxed else { alert("Use a normal Terminal", "Launch the installed menu-bar app outside Codex's sandbox before connecting human approvals."); return }
        guard installedController else {
            alert("Install the approval controller first", "Run scripts/install_menu_bar.py in your normal Terminal, then open the installed app. Workspace builds are for inspection only."); return
        }
        let dialog = NSAlert(); dialog.messageText = "Connect your approval broker"
        dialog.informativeText = "Paste the private Human approval URL from your broker Terminal. It stays in memory until disconnect or quit. Approving still requires macOS authentication."
        let field = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 360, height: 24))
        dialog.accessoryView = field; dialog.addButton(withTitle: "Connect"); dialog.addButton(withTitle: "Cancel")
        guard dialog.runModal() == .alertFirstButtonReturn else { return }
        guard let url = URL(string: field.stringValue), url.scheme == "http", url.host == "127.0.0.1", url.port == 8773,
              let token = url.fragment, !token.isEmpty else { alert("Invalid link", "Use the Human approval URL on 127.0.0.1:8773."); return }
        stopAccessService(); humanToken = token; brokerState = nil; fetchBroker()
    }
    @objc private func disconnectBroker() { stopAccessService(); brokerMessage = "Access service disconnected"; refresh() }
    private func fetchBroker() {
        guard let token = humanToken, !fetching else { return }
        fetching = true
        brokerRequest("state", token: token, payload: nil) { data in
            self.fetching = false
            guard self.humanToken == token else { return }
            self.brokerState = data
            self.brokerMessage = data == nil ? "Access service unavailable · grants unverified" : "Access service ready"
            self.refresh()
        }
    }
    private func brokerRequest(_ route: String, token: String, payload: [String: String]?, done: @escaping ([String: Any]?) -> Void) {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:8773/" + route)!)
        request.timeoutInterval = payload == nil ? 3 : 100
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        if let payload = payload {
            request.httpMethod = "POST"; request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8773", forHTTPHeaderField: "Origin")
        }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpShouldSetCookies = false
        let session = URLSession(configuration: configuration)
        session.dataTask(with: request) { data, response, _ in
            let value = (response as? HTTPURLResponse)?.statusCode == 200 ? data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } : nil
            session.finishTasksAndInvalidate()
            DispatchQueue.main.async { done(value) }
        }.resume()
    }
    @objc private func brokerAction(_ sender: NSMenuItem) {
        guard let payload = sender.representedObject as? [String: String], let token = humanToken else { return }
        brokerRequest("action", token: token, payload: payload) { data in
            guard self.humanToken == token else { return }
            if let data = data { self.brokerState = data; self.refresh() }
            else { self.alert("Action unavailable", "The broker rejected the action, authentication failed, or the connection ended. Refresh to check the grant."); self.fetchBroker() }
        }
    }
    @objc private func launchTrial() { launch("launch-computer-use-trial.command") }
    private func launch(_ name: String) {
        guard !controllerIsSandboxed, let rows = inventory(), rows.isEmpty else {
            alert("Quit Codex first", "Existing chats are never stopped by this app. Wait until tasks finish and quit Codex yourself.")
            return
        }
        let launcher = base.appendingPathComponent(name)
        let log = base.appendingPathComponent("menu-bar-launch.log")
        do {
            if !FileManager.default.fileExists(atPath: log.path) { FileManager.default.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600]) }
            let handle = try FileHandle(forWritingTo: log); try handle.seekToEnd()
            let task = Process(); task.executableURL = URL(fileURLWithPath: "/bin/bash"); task.arguments = [launcher.path]
            task.standardOutput = handle; task.standardError = handle
            task.terminationHandler = { process in
                try? handle.close()
                if process.terminationStatus != 0 { DispatchQueue.main.async { self.alert("Launch failed", "The launcher exited with code \(process.terminationStatus). Details are in \(log.path).") } }
            }
            try task.run(); launchProcess = task
        } catch { alert("Launch unavailable", error.localizedDescription) }
    }

    @objc private func openPanel() {
        NSWorkspace.shared.open(URL(string: "http://127.0.0.1:8773/")!)
        alert("Optional browser panel", "Use the private Human approval URL from the broker Terminal if this browser is not authenticated. Native approvals are also available through Connect approval broker in the menu.")
    }
    private func alert(_ title: String, _ message: String) {
        let dialog = NSAlert(); dialog.messageText = title; dialog.informativeText = message
        NSApp.activate(ignoringOtherApps: true); dialog.runModal()
    }
    func applicationWillTerminate(_ notification: Notification) { stopAccessService() }
    @objc private func quit() { NSApp.terminate(nil) }
}

if CommandLine.arguments.contains("--inspect") {
    let rows = inventory()
    let report: [String: Any] = [
        "inventory_available": rows != nil,
        "controller_sandbox_raw": sandboxPresence(getpid(), nil, 0),
        "processes": (rows ?? []).map { ["pid": $0.pid, "executable": $0.path, "sandbox_raw": $0.sandbox, "role": $0.label] as [String: Any] },
        "scope": "Sandbox presence only; folder rules remain unverified."
    ]
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    print(String(decoding: data, as: UTF8.self))
    exit(0)
}

if let previewIndex = CommandLine.arguments.firstIndex(of: "--render-preview"), CommandLine.arguments.count > previewIndex + 1 {
    let previewApp = NSApplication.shared
    previewApp.setActivationPolicy(.prohibited)
    let model = AccessViewModel()
    model.summary = "Sandbox detected · exact folder rules unverified"
    model.service = "Access service ready"
    model.processes = [AgentProcess(pid: 120, path: "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT", sandbox: 1, desktopChild: false, parentPID: nil), AgentProcess(pid: 121, path: "/Applications/ChatGPT.app/Contents/Resources/codex-cli/codex", sandbox: 1, desktopChild: true, parentPID: 120)]
    model.broker = ["folder": "/Example/demo-folder", "requests": [["id": "example", "status": "active", "remaining": 590]], "events": [["time": "10:42", "action": "approved"]]]
    let expanded = CommandLine.arguments.contains("--expanded")
    let size = NSSize(width: 340, height: 480)
    let host = NSHostingView(rootView: AccessPopover(model: model, expandedPreview: expanded) { _, _ in })
    let window = NSWindow(contentRect: NSRect(origin: .zero, size: size), styleMask: .borderless, backing: .buffered, defer: false)
    window.appearance = NSAppearance(named: .aqua)
    host.appearance = NSAppearance(named: .aqua)
    window.contentView = host; host.frame = NSRect(origin: .zero, size: size)
    host.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.15))
    guard let bitmap = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { exit(2) }
    host.cacheDisplay(in: host.bounds, to: bitmap)
    guard let data = bitmap.representation(using: .png, properties: [:]) else { exit(2) }
    try data.write(to: URL(fileURLWithPath: CommandLine.arguments[previewIndex + 1]))
    print("Preview rendered using synthetic data. No running instance, policy or grant was changed.")
    exit(0)
}

let app = NSApplication.shared
let controller = MenuController()
app.delegate = controller
app.run()
