# Native menu-bar prototype

## Instance panel and launch rules

Click **Access** to open a compact popover beside the menu bar. **Codex instances**, **Folders for next protected launch**, **Access requests**, and **Recent activity** expand and collapse in place. Desktop backends are nested under their detected parent desktop process. Protection status, counts and active countdown summaries remain visible when collapsed; process IDs and executable paths appear only in expanded details. There is no separate permissions window in the normal flow. Unsaved folder edits and section state survive refresh and collapse/reopen while the controller remains running.

Exact live folder permissions remain unknown; neither the installed reference policy nor a saved draft establishes what an existing process can access. No chat-level isolation is claimed.

The inline **Folders for next protected launch** editor sets a read/write workspace plus additional read-only or read/write folders for the next protected desktop launch. New additional folders default to read-only and can be changed using their permission selector. Save rules, then use **Start protected Codex**. Unsaved edits block launch until saved. If desktop is already running, it explains that active tasks must finish and the user must quit it first; it never stops existing work. Independent CLI instances remain unchanged. **Advanced** offers a saved-rules Terminal command as a diagnostic fallback. Folder permissions are cumulative: read-only entries do not subtract write permission from an overlapping workspace or runtime exception.

Saved configuration lives outside workspace in the installed menu-bar directory. The launcher validates paths and rejects root, home, and rules exposing its own controller directory. Existing Codex profile/system runtime exceptions remain; this policy restricts personal/storage reads and outside writes, rather than implementing a complete system-read allowlist. Exact policy association with running processes, CLI rule application, and automatic interception remain future work. Use dummy boundary checks after launching.

Build from a normal Terminal:

```sh
cd /Users/example/workspace/CodexGate
/bin/bash scripts/build_menu_bar.sh
open '/Users/example/workspace/CodexGate/.build/CodexGate.app'
```

An Access item appears in the macOS menu bar. It refreshes every five seconds and lists Codex desktop and CLI/backend processes, including instances started outside our launcher. Detection uses executable paths and macOS sandbox presence, without reading process arguments, environment variables, or mailbox data. A binary named `codex` is treated as a candidate; executable paths appear in row tooltips.

“Sandbox detected” means macOS reports a sandbox. It does not establish that the process uses our policy or that particular folders are blocked. Keep using dummy boundary checks to verify those rules. Process inventory can omit processes that macOS refuses to describe.

Protected launch requires an unsandboxed installed controller, a ready access service, saved rules, and no running Codex desktop process. Failed setup does not fall back to an unprotected launch. The experimental Computer Use launcher is under Advanced and uses the existing trial wrapper; its legacy diagnostic output is appended to `~/Library/Application Support/CodexGate/menu-bar-launch.log`.

For native approval controls, install from your normal Terminal:

```sh
/opt/homebrew/bin/python3 /Users/example/workspace/CodexGate/scripts/install_menu_bar.py
```

Quit the old CodexGate menu app (not Codex), then run the printed `open` command. Only the installed controller can connect to human approvals. This keeps its executable outside the agent-writable workspace under the intended desktop policy; it is not protection against other unrestricted programs running as your user.

The installed app automatically starts and connects a private access-service child, using pipes for the readiness handshake and credentials. No separate Terminal or pasted Human approval link is needed. Credentials stay in memory and are discarded when the service stops. Closing/crashing the controller closes the child's stdin and ends the service; requests and grants do not survive restart. Port conflicts or startup failures leave setup unavailable, with a Retry control.

The default demo folder remains available for agent-command trials. **Grant access…** opens a directory browser to the left of the main popover. Browse one level at a time, select multiple folders with checkboxes, and click **Grant access to selected folders**. It displays filenames and folder metadata only; file contents are never opened by the browser. Hidden entries and symlinks are omitted. Selecting folders does not grant authority. macOS authentication occurs once per folder, sequentially; cancellation stops the remaining approvals. Existing successful grants remain active.

Each folder has its own request ID, pinned directory descriptor, ten-minute countdown, **Extend 10 minutes**, and **Revoke now**. Extension authenticates again and resets expiry to ten minutes from approval; failed extension removes authority. Revoking one folder leaves other grants intact. Root, home, and controller directories are rejected. Grants disappear on service/controller restart.

**Copy access-request command** is retained under Advanced for agent integration. Requests through the agent endpoint use the configured demo/default root; selecting additional roots requires the separate human capability. These grants allow read/list through the broker API, not direct filesystem access or writes. There is no automatic interception of blocked desktop operations. Recent activity shows service events only, not all Codex filesystem activity.

Advanced retains manual external-service connection for diagnostics. Do not run a second broker on the same ports. Manual connections do not become automatically owned services.

The app reads the installed legacy launch-codex.command wrapper as text and loads its reference policy. **Reload saved access rules** refreshes that reference in Advanced; missing or unreadable configuration leaves it unknown. This legacy reference is separate from managed launch drafts. Discovery never executes the wrapper.

**Choose saved access rules** displays path exceptions from a selected desktop policy under Advanced. This is an informational configuration view, not a complete SBPL evaluator or proof that a running process uses that policy. Regex exceptions are not summarized as folders. Sandbox status and service state remain separate. On service disconnection, active access is shown as unverified; countdown expiry is enforced by the service, not the menu timer.

The browser-panel link remains optional; native grant controls no longer require opening it. Live authentication and native menu interaction still need a user trial outside the sandbox.

Read-only diagnostic, without opening the menu UI:

```sh
'/Users/example/workspace/CodexGate/.build/CodexGate.app/Contents/MacOS/CodexGate' --inspect
```

Run the app from your normal Terminal. Starting it through a sandboxed coding agent can confine the controller and disable its launch controls. This development prototype displays status and delegates to existing controls; it does not add or change filesystem permissions.


Normal UI cleanup: Troubleshooting now contains only Copy protected-launch command. The access-request command is a developer/agent API feature, omitted from the normal menu. Reference-policy inspection, manual external-service connection, browser approval panel, and experimental Computer Use launcher are omitted from the popover. Existing internal diagnostic code remains available for development.


Developer request API: POST http://127.0.0.1:8772/request with the session's agent Bearer token, Content-Type application/json and body `{}` creates a pending read/list request for the service's configured default folder. The response describes that one request, not all accessible folders. It cannot approve authority. Session tokens expire on service restart; do not record them in documentation or logs. Normal users should use Grant access instead.
