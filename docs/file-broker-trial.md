# Read/list broker trial

The confined agent calls a separate loopback service on port 8772. Its token cannot approve requests. A separate human approval UI runs on port 8773 and requires a different capability. The user reviews the folder, session, and read/list scope, clicks **Approve for 10 minutes**, and authenticates with Touch ID or macOS password. Approval lasts 600 seconds from successful authentication, is checked on every operation, and can be revoked immediately. Restart discards all sessions, UI credentials, and grants. Direct filesystem access stays blocked. Terminal `approve ID` and `revoke ID` remain available as a fallback.

Run from normal Terminal:

```sh
/opt/homebrew/bin/python3 /Users/example/workspace/CodexGate/scripts/prepare_file_broker.py
```

This runs the filesystem and HTTP approval tests, builds the native authentication helper, copies the service and UI to a new trial directory outside workspace, creates only dummy data, and prints the launch command. Run that command in normal Terminal and leave it open. Stop the previous broker first with Ctrl+C to free ports 8772 and 8773. No Codex restart is needed. It does not change the desktop launcher or install the pending process-monitoring update.

Open the printed **Human approval URL** in your own browser, outside the agent-controlled browser. Do not paste that URL into chat. Its fragment carries the human capability; the page removes the fragment and keeps the credential in sessionStorage for that tab. HTTP responses expose neither capability. Browser actions require the human capability and the exact local Origin. Every approval additionally requires native authentication; denied/cancelled authentication grants nothing. No password field exists in the web UI. Deny and Revoke do not require authentication, so they can always remove access quickly.

Give the agent only the printed **Session token**. The token is an ephemeral capability for this one trial, not a Gmail credential. The agent sends POST requests to `http://127.0.0.1:8772/request`, `/status`, `/list`, or `/read`, with `Authorization: Bearer TOKEN` and JSON bodies. `/request` takes `{}` and returns an ID. Other endpoints take `{"id":"ID"}`; read/list also accept a relative `path`. No approval endpoint exists on the agent API.

Verify the sequence: read before approval denied; approve in the new UI and authenticate; list and read dummy file allowed through API; direct agent file read still denied; revoke in UI and confirm API denied. Then create a fresh request, approve, and leave it active for ten minutes without revoking. The countdown reaches expiry and the next broker operation must fail. Keep the Codex launch Terminal open and check sandbox presence with every direct-access probe. The new UI shows the latest 100 events, without file contents. Automatic desktop notifications and the existing synthetic 8771 UI are not connected.

Limits: one session per service, one root folder, UTF-8 text reads up to 256 KiB, listings up to 1000 entries, no writes/deletes/commands. Symlink traversal, parent traversal, special files, and multiply linked files are rejected. Existing data already returned cannot be recalled at expiry. A root directory descriptor anchors access across path replacement; subdirectory renames by other processes during an operation are not prevented. Use a stable dummy folder for this trial. Concurrent hostile modifications and OS-authenticated caller identity are not production-ready.

The installed copy is protected only if the agent's existing outer sandbox denies its location. It is not protected from an unrestricted process running as the same user. A browser/profile accessible to agent tools is not an isolated approver; native authentication is still required, but do not claim its UI capability is inaccessible to those tools. OS-verified agent identity and a protected native approver remain future work. Do not select real sensitive folders until actual confined-desktop UI/API/direct-access checks and native authentication have passed. This trial does not fix Codex's hardcoded `/bin/ps` compatibility issue.
