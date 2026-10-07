# Implementation milestones

1. **Synthetic workflow — implemented.** Local UI, request/deny, simulated authentication, 10-minute read/list grant, countdown, revoke, synthetic read, memory-only activity, restart invalidation. Eleven broker tests pass. Browser visual review remains outstanding.
2. **Native approval — partially implemented.** Compiled LocalAuthentication helper and fail-closed broker approval are implemented; interactive authentication awaits user testing. Still pending: macOS application and native LocalAuthentication, isolated approver channel, OS-verified session identity. Demo session-token binding is implemented, including cross-session denial and restart invalidation. No agent-accessible approval endpoint in production.
3. **Enforced isolation — probe implemented.** Seven dummy-file OS checks pass, including symlink escape denial. Production confinement remains pending: Protected deployment remains pending. An experimental launcher now excludes broker source from the selected agent workspace; prove direct reads blocked and approved broker reads allowed using dummy files. Test path escapes and revocation during operations.
4. **Codex integration.** Explicit permission-request tool, session binding, actionable denial, verified protection status. Desktop launch support must be verified rather than assumed.
5. **Write access and distribution.** Bounded writes, audit controls, installer, protected configuration, security review.

Current demo approval invokes native authentication, but the helper deployment and local caller identity are not protected. It is synthetic-only. They must never be connected to real protected data.

Codex CLI 0.146.0 version and fresh login-status commands pass under the outer launcher. Interactive login/model tasks and desktop launch remain unverified. 17 automated tests pass.

Desktop launcher preparation is implemented with a separate profile/runtime and explicit private-mail `.local` exclusion. 20 tests pass, including desktop-policy fixture tests. Actual GUI launch, sign-in, tool inheritance, and permission-request integration remain unverified.

Workspace-wide desktop scope is now prepared. Trusted snapshot and launcher live outside workspace in Application Support/CodexGate. No project-specific hidden-folder exclusions remain. 21 tests and a real whole-workspace policy subprocess probe pass. Running desktop app has not been restarted or reconfigured. Actual GUI/tool confinement and broker request integration are still pending.

Existing-profile desktop option implemented; installed wrapper enables it. Explicit Codex state exceptions are visible in --prepare-only. 24 tests pass. Actual profile restoration and desktop tool confinement remain pending user relaunch.
