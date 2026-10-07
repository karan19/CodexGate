import AppKit
import SwiftUI

final class AccessViewModel: ObservableObject {
    @Published var summary = "Checking access…"
    @Published var processes: [AgentProcess] = []
    @Published var service = "Access service disconnected"
    @Published var broker: [String: Any]?
    @Published var canLaunch = false
    @Published var canRequest = false
    @Published var canConfigure = false
    @Published var referencePaths: [String] = []
    @Published var showFolders = false
    @Published var draftWorkspace = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("workspace").path
    @Published var draftFolders: [FolderRule] = []
    @Published var draftLoaded = false
    @Published var draftDirty = false
    @Published var draftMessage = "Saved folders take effect only after restarting Codex through the protected launcher."
}

struct AccessPopover: View {
    @ObservedObject var model: AccessViewModel
    let action: (String, String?) -> Void
    @State private var instancesOpen = false
    @State private var requestsOpen = false
    @State private var activityOpen = false
    @State private var advancedOpen = false
    @State private var browserOpen = false
    @State private var browserMode = "grant"
    init(model: AccessViewModel, expandedPreview: Bool = false, action: @escaping (String, String?) -> Void) {
        self.model = model; self.action = action
        _instancesOpen = State(initialValue: expandedPreview)
        _requestsOpen = State(initialValue: expandedPreview)
        _activityOpen = State(initialValue: expandedPreview)
    }
    private var desktops: [AgentProcess] { model.processes.filter { !$0.path.hasSuffix("/codex") } }
    private var independent: [AgentProcess] { model.processes.filter { row in row.path.hasSuffix("/codex") && !desktops.contains(where: { $0.pid == row.parentPID }) } }
    private var requests: [[String: Any]] { model.broker?["requests"] as? [[String: Any]] ?? [] }
    private var pending: Int { requests.filter { $0["status"] as? String == "pending" }.count }
    private var active: [[String: Any]] { requests.filter { $0["status"] as? String == "active" } }
    private var events: [[String: Any]] { model.broker?["events"] as? [[String: Any]] ?? [] }
    private var folder: String { model.broker?["folder"] as? String ?? "No folder connected" }
    private func countdown(_ seconds: Int) -> String { "\(seconds / 60)m \(seconds % 60)s" }

    var body: some View {
        HStack(spacing: 0) {
            if browserOpen {
                FolderGrantBrowser(mode: browserMode) { paths in
                    guard let data = paths.data(using: .utf8), let selected = try? JSONDecoder().decode([String].self, from: data) else { return }
                    if browserMode == "grant" { action("grant-folders", paths); requestsOpen = true }
                    else {
                        if browserMode == "workspace", let path = selected.first { model.draftWorkspace = path }
                        else { for path in selected where !model.draftFolders.contains(where: { $0.path == path }) { model.draftFolders.append(FolderRule(path: path, access: "read")) } }
                        model.draftDirty = true
                        model.draftMessage = "Unsaved changes · running instances are unchanged."
                        browserOpen = false
                    }
                } close: { browserOpen = false }
                .id(browserMode)
                    .frame(width: 240, height: 480)
                Divider()
            }
            mainPanel
        }.background(GlassBackground())
    }
    private var mainPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("CodexGate", systemImage: "folder.badge.gearshape").font(.system(size: 14, weight: .semibold))
                Spacer()
                Button { action("refresh", nil) } label: { Image(systemName: "arrow.clockwise") }.help("Refresh access status")
            }
            Text(model.summary).font(.system(size: 12)).foregroundStyle(model.processes.contains(where: { $0.sandbox == 0 }) ? Color.orange : Color.secondary)
            if model.service.hasPrefix("Move CodexGate") {
                Label("Drag CodexGate to Applications", systemImage: "arrow.right.circle")
                    .font(.system(size: 12, weight: .medium))
                Text("Eject the disk image, then open the copy in Applications to finish setup.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Button("Start protected Codex") { action("launch", nil) }.disabled(!model.canLaunch)
                .help("Uses saved folder rules. Finish tasks and quit Codex desktop first.")
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    instancesSection
                    Divider()
                    DisclosureGroup(isExpanded: $model.showFolders) {
                        InlineFolderEditor(canConfigure: model.canConfigure, workspace: $model.draftWorkspace, folders: $model.draftFolders, loaded: $model.draftLoaded, dirtyDraft: $model.draftDirty, message: $model.draftMessage, browse: { mode in browserMode = mode; browserOpen = true })
                    } label: { sectionLabel("Launch folders", model.draftDirty ? "Unsaved changes" : "Saved · restart needed") }
                    Divider()
                    requestsSection
                    Divider()
                    activitySection
                    Divider()
                    advancedSection
                }.padding(.trailing, 6)
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
            Divider()
            HStack {
                Text("Codex stays running when this app quits.").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Button("Quit") { action("quit", nil) }.help("Quit CodexGate; ends its access service and grants. Codex stays running.")
            }
        }.padding(12).frame(width: 340, height: 480)
        .font(.system(size: 13))
        .background(Color.clear)
        .disclosureGroupStyle(CompactDisclosureStyle())
        .buttonStyle(.bordered)
        .controlSize(.small)
    }
    private var instancesSection: some View {
                    DisclosureGroup(isExpanded: $instancesOpen) {
                        VStack(alignment: .leading, spacing: 10) {
                            if model.processes.isEmpty { Text("No detected instances").foregroundStyle(.secondary) }
                            ForEach(desktops, id: \.pid) { desktop in
                                DisclosureGroup {
                                    processDetails(desktop)
                                    let children = model.processes.filter { $0.desktopChild && $0.parentPID == desktop.pid }
                                    ForEach(children, id: \.pid) { child in
                                        DisclosureGroup("Desktop backend") { processDetails(child) }
                                    }
                                    Text("Backends are app helpers, not separate chats.").font(.caption).foregroundStyle(.secondary)
                                } label: {
                                    HStack { Text("Codex desktop"); Spacer(); Text(status(desktop)).font(.caption).foregroundStyle(.secondary) }
                                }
                            }
                            ForEach(independent, id: \.pid) { row in
                                DisclosureGroup(row.label) { processDetails(row) }
                            }
                        }.padding(.top, 8)
                    } label: { sectionLabel("Codex", "\(desktops.count) desktop · \(model.processes.count - desktops.count) helpers") }
    }

    private var requestsSection: some View {
                    DisclosureGroup(isExpanded: $requestsOpen) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(model.broker == nil ? model.service : "Approval service running · access requires your approval").font(.caption).foregroundStyle(.secondary)
                            Text("10-minute read/list grants. Direct folder permissions stay unchanged.").font(.caption).foregroundStyle(.secondary)
                            if requests.isEmpty { Text("No access requests yet").foregroundStyle(.secondary) }
                            ForEach(Array(requests.enumerated()), id: \.offset) { index, request in
                                if let id = request["id"] as? String, let phase = request["status"] as? String {
                                    VStack(alignment: .leading, spacing: 5) {
                                        HStack {
                                            Text((request["folder"] as? String).map { URL(fileURLWithPath: $0).lastPathComponent } ?? "Request \(index + 1)").fontWeight(.medium)
                                            Spacer()
                                            Text(phase == "active" ? countdown(request["remaining"] as? Int ?? 0) + " left" : phase.capitalized).font(.caption)
                                        }
                                        Text(request["folder"] as? String ?? folder).font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
                                        if phase == "pending" {
                                            HStack {
                                                Button("Grant 10 minutes") { action("approve", id) }
                                                Button("Deny") { action("deny", id) }
                                            }
                                        } else if phase == "active" || phase == "authenticating" {
                                            HStack {
                                                if phase == "active" { Button("Extend 10 minutes") { action("extend", id) }.help("Authenticate again; resets expiry to 10 minutes from approval.") }
                                                Button("Revoke now") { action("revoke", id) }
                                            }
                                        }
                                    }.padding(8).background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
                                }
                            }
                            Button("Grant access…") { browserMode = "grant"; browserOpen = true }.disabled(!model.canRequest)
                            Text("Choose folders in the side panel, then authenticate each grant.").font(.caption2).foregroundStyle(.secondary)
                            if model.broker == nil { Button("Retry access service") { action("retry", nil) }.disabled(!model.canConfigure) }
                        }.padding(.top, 8)
                    } label: {
                        sectionLabel("Temporary access", active.first.map { "\(active.count) active · " + countdown($0["remaining"] as? Int ?? 0) } ?? (pending > 0 ? "\(pending) awaiting approval" : model.broker == nil ? "Service offline" : "No active grants"))
                    }
    }

    private var activitySection: some View {
                    DisclosureGroup(isExpanded: $activityOpen) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Access-service events only; not all Codex file activity.").font(.caption).foregroundStyle(.secondary)
                            if events.isEmpty { Text("No recent activity").foregroundStyle(.secondary) }
                            ForEach(Array(events.prefix(12).enumerated()), id: \.offset) { _, event in
                                HStack { Text(event["action"] as? String ?? "Event"); Spacer(); Text(event["time"] as? String ?? "").foregroundStyle(.secondary) }.font(.caption)
                            }
                        }.padding(.top, 8)
                    } label: { sectionLabel("Recent activity", "\(events.count) event\(events.count == 1 ? "" : "s")") }
    }

    private var advancedSection: some View {
        DisclosureGroup("Troubleshooting", isExpanded: $advancedOpen) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Optional Terminal fallback for protected-launch troubleshooting.")
                    .font(.caption).foregroundStyle(.secondary)
                Button("Copy protected-launch command") { action("copy-launch", nil) }
                    .help("Launches Codex using saved folder rules after you fully quit the existing desktop.")
                Text("Saved folder rules apply to a new protected launch. Sandbox detection alone does not verify its exact rules.")
                    .font(.caption2).foregroundStyle(.secondary)
            }.padding(.top, 8)
        }
    }
    private func sectionLabel(_ title: String, _ summary: String) -> some View {
        HStack(spacing: 8) { Text(title).font(.system(size: 13, weight: .semibold)).fixedSize(); Spacer(minLength: 4); Text(summary).font(.system(size: 11)).foregroundStyle(.secondary).lineLimit(1) }
    }
    private func status(_ row: AgentProcess) -> String { row.sandbox == 0 ? "Unprotected" : row.sandbox == 1 ? "Sandbox detected" : "Unknown" }
    private func processDetails(_ row: AgentProcess) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("Process \(row.pid) · " + status(row)).font(.caption)
            Text(row.path).font(.caption2).textSelection(.enabled)
            Text(row.sandbox == 0 ? "Our folder boundary is not enforced on this process." : "Exact running folder rules are unknown.").font(.caption).foregroundStyle(.secondary)
        }.padding(.vertical, 6)
    }
}

/// Native vibrancy follows wallpaper and light/dark appearance without custom blur snapshots.
private struct GlassBackground: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = .popover
        view.blendingMode = .behindWindow
        view.state = .active
        view.wantsLayer = true
        view.layer?.cornerRadius = 12
        view.layer?.masksToBounds = true
        return view
    }
    func updateNSView(_ view: NSVisualEffectView, context: Context) {}
}

/// Animate only the disclosure content; the native popover keeps a stable size.
private struct CompactDisclosureStyle: DisclosureGroupStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    configuration.isExpanded.toggle()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .semibold))
                        .rotationEffect(.degrees(configuration.isExpanded ? 90 : 0))
                        .foregroundStyle(.secondary)
                        .frame(width: 12)
                    configuration.label
                        .foregroundStyle(.primary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 7)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityValue(configuration.isExpanded ? "Expanded" : "Collapsed")
            if configuration.isExpanded {
                configuration.content
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 14)
                    .padding(.bottom, 9)
                    .transition(.opacity)
            }
        }
    }
}

struct InlineFolderEditor: View {
    let canConfigure: Bool
    @Binding var workspace: String
    @Binding var folders: [FolderRule]
    @Binding var loaded: Bool
    @Binding var dirtyDraft: Bool
    @Binding var message: String
    let browse: (String) -> Void
    private let base = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/CodexGate/menu-bar")
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("Workspace · read/write").font(.caption).fontWeight(.medium)
            HStack {
                Text(URL(fileURLWithPath: workspace).lastPathComponent).font(.caption).lineLimit(1).help(workspace)
                Spacer()
                Button("Choose…") { browse("workspace") }.disabled(!canConfigure)
            }
            ForEach(folders, id: \.path) { rule in
                HStack {
                    Text(URL(fileURLWithPath: rule.path).lastPathComponent).font(.caption).lineLimit(1).truncationMode(.middle).help(rule.path)
                    Picker("Access", selection: Binding(get: { folders.first(where: { $0.path == rule.path })?.access ?? "read" }, set: { value in
                        if let index = folders.firstIndex(where: { $0.path == rule.path }) { folders[index].access = value; dirty() }
                    })) {
                        Text("Read").tag("read"); Text("Read/write").tag("read-write")
                    }.labelsHidden().frame(width: 112)
                    Button { folders.removeAll(where: { $0.path == rule.path }); dirty() } label: { Image(systemName: "minus.circle") }.help("Remove folder from next-launch rules")
                }
            }
            HStack {
                Button("Add folder…") { browse("launch") }
                Button("Save rules") { save() }
            }.disabled(!canConfigure)
            Text(message).font(.caption).foregroundStyle(.secondary)
            DisclosureGroup("About these rules") {
                Text("Codex still needs its app data and system tools. A read-only folder inside a read/write workspace remains writable.").font(.caption2).foregroundStyle(.secondary)
            }
        }.padding(.top, 8).onAppear {
            guard !loaded else { return }; loaded = true
            if let data = try? Data(contentsOf: base.appendingPathComponent("permissions.json")), let value = try? JSONDecoder().decode(PermissionDraft.self, from: data) { workspace = value.workspace; folders = value.folders }
        }
    }
    private func dirty() { dirtyDraft = true; message = "Unsaved changes · running instances are unchanged." }
    private func save() {
        do {
            guard canConfigure, sandboxPresence(getpid(), nil, 0) == 0 else { throw NSError(domain: "Use the installed controller outside Codex", code: 1) }
            for path in [workspace] + folders.map(\.path) {
                var directory: ObjCBool = false
                let resolved = URL(fileURLWithPath: path).resolvingSymlinksInPath().path
                guard FileManager.default.fileExists(atPath: resolved, isDirectory: &directory), directory.boolValue,
                      resolved != "/", resolved != FileManager.default.homeDirectoryForCurrentUser.path,
                      resolved != base.path, !base.path.hasPrefix(resolved + "/"), !resolved.hasPrefix(base.path + "/") else { throw NSError(domain: "Choose an existing folder that does not expose the controller, root or home", code: 1) }
            }
            try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(PermissionDraft(workspace: workspace, folders: folders)).write(to: base.appendingPathComponent("permissions.json"), options: .atomic)
            dirtyDraft = false
            message = "Saved · applies to the next protected desktop launch."
        } catch { message = "Could not save: " + error.localizedDescription }
    }
}

/// Browse names only, one directory level at a time. Never opens file contents.
private struct FolderGrantBrowser: View {
    let mode: String
    let select: (String) -> Void
    let close: () -> Void
    @State private var current = FileManager.default.homeDirectoryForCurrentUser.path
    @State private var entries: [URL] = []
    @State private var selected: Set<String> = []
    @State private var error = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(mode == "grant" ? "Grant folder access" : mode == "workspace" ? "Choose workspace" : "Add launch folders").font(.headline)
                Spacer()
                Button(action: close) { Image(systemName: "xmark") }.buttonStyle(.plain)
            }
            Text(mode == "grant" ? "Read/list · 10 minutes per folder" : "Saved rules for next protected launch").font(.caption).foregroundStyle(.secondary)
            HStack {
                Button { current = URL(fileURLWithPath: current).deletingLastPathComponent().path; load() } label: { Image(systemName: "arrow.up") }
                Text(current).font(.caption).lineLimit(2).truncationMode(.middle).textSelection(.enabled)
            }
            Divider()
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 3) {
                    ForEach(entries, id: \.path) { entry in
                        let directory = (try? entry.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
                        HStack(spacing: 6) {
                            if directory {
                                Button {
                                    if selected.contains(entry.path) { selected.remove(entry.path) } else { if mode == "workspace" { selected.removeAll() }; selected.insert(entry.path) }
                                } label: { Image(systemName: selected.contains(entry.path) ? "checkmark.square.fill" : "square") }.buttonStyle(.plain)
                            } else { Image(systemName: "doc").foregroundStyle(.secondary) }
                            Text(entry.lastPathComponent).font(.caption).lineLimit(1).truncationMode(.middle)
                            Spacer()
                            if directory {
                                Button { current = entry.path; load() } label: { Image(systemName: "chevron.right") }.buttonStyle(.plain).help("Browse folder")
                            }
                        }.padding(.vertical, 5)
                    }
                }
            }
            if !error.isEmpty { Text(error).font(.caption).foregroundStyle(.orange) }
            Divider()
            Text("\(selected.count) folders selected").font(.caption).foregroundStyle(.secondary)
            Button(mode == "grant" ? "Grant access to selected folders" : mode == "workspace" ? "Use selected workspace" : "Add selected folders") {
                let paths = selected.sorted()
                if let data = try? JSONSerialization.data(withJSONObject: paths), let value = String(data: data, encoding: .utf8) { select(value); selected.removeAll() }
            }.disabled(selected.isEmpty)
            Text(mode == "grant" ? "macOS authentication is required for each folder. Files are shown by name only." : "Selection updates your draft. Save rules to use them on the next protected launch.").font(.caption2).foregroundStyle(.secondary)
        }.padding(14).onAppear { load() }
    }
    private func load() {
        do {
            entries = try FileManager.default.contentsOfDirectory(at: URL(fileURLWithPath: current), includingPropertiesForKeys: [.isDirectoryKey, .isSymbolicLinkKey], options: [.skipsHiddenFiles]).filter {
                (try? $0.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) != true
            }.sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
            error = ""
        } catch { entries = []; self.error = "This folder cannot be listed." }
    }
}
