# Initial design

## Boundary

The application is the permission UI; a trusted broker validates and performs permitted filesystem operations. An independently enforced sandbox must block direct agent access to protected paths. Starting in a workspace directory or showing an approval popup does not enforce that boundary.

A blocked shell read does not automatically generate a popup. Agent integration must explicitly request a broker operation. The broker prompts the user and returns a denial or operation result.

## Temporary grants

Grants last 10 minutes and bind to a verified agent session, canonical folder, and operation scope. Validate every operation against expiry and revocation. Extensions require fresh authentication. Restart should invalidate grants by default. Folder scope includes descendants but must reject traversal and symlink escapes.

Prefer broker-mediated access rather than widening direct filesystem permissions. Static sandbox policies may require relaunch to change; native filesystem interception remains an investigation, not a promised capability.

Revocation must address pending operations and open handles before claiming access has ended. Previously returned data cannot be retracted from an agent or model provider.

## Trusted components

The agent must not be able to edit the deployed broker, approval policies, grant storage, or authentication components. Source code can remain in the workspace for review, but a production trust boundary needs protected deployment. Native authentication should never expose the user's password to the agent or application logs.

## First milestone

1. Implement a local UI with synthetic folders and explicit demo/unverified labeling.
2. Implement a read/list-only broker with synthetic files and native authentication.
3. Establish and test direct-access denial separately from broker approval.
4. Verify denial, expiry, early revoke, session isolation, restart, and path escape handling.
5. Add write operations only after the read boundary is demonstrated.

## Open implementation decisions

- Sandbox mechanism and supported Codex desktop/CLI launch paths.
- Reliable agent session identity and request integration.
- Protected deployment and distribution of the trusted broker.
- Handling in-flight operations at expiry and revocation.

Agent Safehouse and ActionProxy are research references, not installed dependencies. No previous Safehouse configuration is restored by this scaffold.
