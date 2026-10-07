import AppKit

struct FolderRule: Codable {
    var path: String
    var access: String
}
struct PermissionDraft: Codable {
    var workspace: String
    var folders: [FolderRule]
}

final class PermissionsPanel: NSObject, NSTableViewDataSource, NSTableViewDelegate {
    private var window: NSWindow!
    private let instances = NSPopUpButton()
    private let details = NSTextField(wrappingLabelWithString: "")
    private let workspace = NSTextField()
    private let note = NSTextField(wrappingLabelWithString: "")
    private let table = NSTableView()
    private var rows: [AgentProcess] = []
    private var rules: [FolderRule] = []
    private let base = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/CodexGate/menu-bar")
    private var saved: PermissionDraft?

    func show() {
        if window == nil { build() }
        updateInstances()
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }
    private func label(_ text: String) -> NSTextField {
        let field = NSTextField(wrappingLabelWithString: text)
        field.preferredMaxLayoutWidth = 730
        return field
    }
    private func button(_ title: String, _ action: Selector) -> NSButton {
        NSButton(title: title, target: self, action: action)
    }
    private func build() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 780, height: 820), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Codex Folder Permissions"; window.isReleasedWhenClosed = false; window.center()
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 22), stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -22), stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 22)])
        let title = label("Running instances"); title.font = .boldSystemFont(ofSize: 19); stack.addArrangedSubview(title)
        instances.target = self; instances.action = #selector(selectionChanged)
        stack.addArrangedSubview(NSStackView(views: [instances, button("Refresh", #selector(refreshInstances))]))
        stack.addArrangedSubview(details); details.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        stack.addArrangedSubview(label("Rules for the next protected desktop launch"))
        stack.addArrangedSubview(label("These settings are a launch draft. They do not describe or change the selected running process. CLI/backend entries may belong to the same desktop app; chats are not separate permission boundaries."))
        workspace.stringValue = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("workspace").path
        workspace.placeholderString = "Workspace folder (read/write)"
        workspace.widthAnchor.constraint(equalToConstant: 700).isActive = true
        stack.addArrangedSubview(NSStackView(views: [label("Workspace · read/write"), button("Choose…", #selector(chooseWorkspace))]))
        stack.addArrangedSubview(workspace)
        let path = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("path")); path.title = "Additional folder"; path.width = 540
        let access = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("access")); access.title = "Permission"; access.width = 150
        table.addTableColumn(path); table.addTableColumn(access); table.delegate = self; table.dataSource = self
        let scroll = NSScrollView(); scroll.hasVerticalScroller = true; scroll.documentView = table
        scroll.widthAnchor.constraint(equalToConstant: 730).isActive = true; scroll.heightAnchor.constraint(equalToConstant: 140).isActive = true
        stack.addArrangedSubview(scroll)
        stack.addArrangedSubview(NSStackView(views: [button("Add read-only folder", #selector(addRead)), button("Add read/write folder", #selector(addWrite)), button("Remove selected", #selector(removeFolder))]))
        stack.addArrangedSubview(label("Outside workspace and added folders: personal/storage data reads restricted, writes denied. Required Codex profile and system runtime exceptions remain. This is not a complete system-read allowlist. Broker grants are separate."))
        stack.addArrangedSubview(NSStackView(views: [button("Save launch rules", #selector(save)), button("Copy Terminal launch command", #selector(copyCommand))]))
        stack.addArrangedSubview(note)
        if let data = try? Data(contentsOf: base.appendingPathComponent("permissions.json")), let draft = try? JSONDecoder().decode(PermissionDraft.self, from: data) {
            workspace.stringValue = draft.workspace; rules = draft.folders; saved = draft; table.reloadData()
            note.stringValue = "Saved launch rules loaded. Running permissions are unchanged."
        }
    }
    private func updateInstances() {
        let previous = instances.selectedItem?.representedObject as? Int32
        let found = inventory(); rows = found ?? []; instances.removeAllItems()
        for row in rows {
            instances.addItem(withTitle: "\(row.label) · PID \(row.pid)")
            instances.lastItem?.representedObject = row.pid
        }
        if rows.isEmpty { instances.addItem(withTitle: found == nil ? "Inventory unavailable" : "No Codex instances running") }
        if let previous = previous, let index = rows.firstIndex(where: { $0.pid == previous }) { instances.selectItem(at: index) }
        selectionChanged()
    }
    @objc private func refreshInstances() { updateInstances() }
    @objc private func selectionChanged() {
        guard rows.indices.contains(instances.indexOfSelectedItem) else { details.stringValue = "No running instance selected. You can prepare launch rules below."; return }
        let row = rows[instances.indexOfSelectedItem]
        let state = row.sandbox == 0 ? "No macOS sandbox detected. Our folder boundary is not enforced." : row.sandbox == 1 ? "Sandbox detected. Exact folder rules and workspace are unknown for this process." : "Sandbox status unavailable. Exact folder rules are unknown."
        details.stringValue = state + "\nExecutable: " + row.path + "\nInstalled policy configuration is not proof of this instance's permissions."
    }
    private func pickFolder() -> String? {
        let picker = NSOpenPanel(); picker.canChooseDirectories = true; picker.canChooseFiles = false; picker.allowsMultipleSelection = false
        guard picker.runModal() == .OK, let url = picker.url else { return nil }; return url.resolvingSymlinksInPath().path
    }
    @objc private func chooseWorkspace() { if let path = pickFolder() { workspace.stringValue = path; note.stringValue = "Unsaved changes · requires a new protected launch." } }
    @objc private func addRead() { add("read") }
    @objc private func addWrite() { add("read-write") }
    private func add(_ access: String) {
        guard let path = pickFolder() else { return }
        if let index = rules.firstIndex(where: { $0.path == path }) { rules[index].access = access }
        else { rules.append(FolderRule(path: path, access: access)) }
        table.reloadData(); note.stringValue = "Unsaved changes · existing instances are unchanged."
    }
    @objc private func removeFolder() {
        guard rules.indices.contains(table.selectedRow) else { return }
        rules.remove(at: table.selectedRow); table.reloadData(); note.stringValue = "Unsaved changes · existing instances are unchanged."
    }
    func numberOfRows(in tableView: NSTableView) -> Int { rules.count }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let field = label(tableColumn?.identifier.rawValue == "path" ? rules[row].path : rules[row].access == "read" ? "Read only" : "Read / write")
        field.lineBreakMode = .byTruncatingMiddle; field.toolTip = rules[row].path; return field
    }
    private func draft() throws -> PermissionDraft {
        let path = URL(fileURLWithPath: workspace.stringValue).resolvingSymlinksInPath().path
        var directory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &directory), directory.boolValue,
              path != "/", path != FileManager.default.homeDirectoryForCurrentUser.path else { throw NSError(domain: "Choose an existing workspace below root or home", code: 1) }
        return PermissionDraft(workspace: path, folders: rules)
    }
    @objc private func save() {
        do {
            let value = try draft()
            guard sandboxPresence(getpid(), nil, 0) == 0 else { throw NSError(domain: "Run the controller from normal Terminal", code: 1) }
            try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(value).write(to: base.appendingPathComponent("permissions.json"), options: .atomic)
            saved = value; note.stringValue = "Saved for the next protected desktop launch. No current instance was changed."
        } catch { note.stringValue = "Could not save: " + error.localizedDescription }
    }
    @objc private func copyCommand() {
        guard let saved = saved, let current = try? draft(), saved.workspace == current.workspace,
              saved.folders.map({ $0.path + $0.access }) == current.folders.map({ $0.path + $0.access }) else { note.stringValue = "Save these rules before copying a launch command."; return }
        func quote(_ value: String) -> String { "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'" }
        let command = "/opt/homebrew/bin/python3 " + quote(base.appendingPathComponent("managed_launch.py").path) + " --config " + quote(base.appendingPathComponent("permissions.json").path)
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(command, forType: .string)
        note.stringValue = "Command copied. Finish active desktop tasks, fully quit Codex, then run it in normal Terminal. CLI instances are not changed."
    }
}
