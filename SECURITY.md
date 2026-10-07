# Security scope

CodexGate is an experimental filesystem-control prototype. The controlled boundary is a desktop and its children launched through the managed macOS sandbox, plus explicit broker read/list grants. Normal launches, unrestricted same-user programs, Computer Use, browser interactions, network access, and arbitrary system services are outside this guarantee.

Sandbox presence is not exact policy attribution. Codex runtime/profile storage remains accessible. Grants are bearer capabilities tied to a broker session, not verified chat identities. No automatic interception exists. Direct directory descriptors and no-follow opening prevent ordinary symlink/root replacement escapes; concurrent hostile filesystem mutation requires further review.

Fail closed on authentication errors, invalid capabilities, expiry, cancellation, and missing setup. Keep human and agent capabilities separate. Do not expose arbitrary-root selection to the agent endpoint.

Before a public release: establish a private vulnerability-reporting channel, validate managed launch attribution, review hostile rename races and resource limits, test compatibility, and prepare signed/notarized distribution. No private reporting channel or public release exists yet; do not publish secrets or exploit details in public issues.
