# CodexGate

An unofficial, open-source macOS menu-bar companion for managing Codex folder access.

Choose launch folders, start a protected Codex desktop, and approve temporary read/list access with macOS authentication. A compact glass popover keeps instance status, folder rules, and grants together.

## Status

Experimental source preview. Not affiliated with or endorsed by OpenAI. Experimental Apple Silicon DMG releases are ad-hoc signed and not notarized. macOS may block them.

## Features

- Detect Codex desktop and its backend helpers; distinguish sandbox presence from verified folder rules.
- Save a workspace and additional read-only/read-write folders for the next protected launch.
- Browse and select folders in an adjacent panel.
- Grant multiple folders independently for ten minutes through the local broker.
- Authenticate each grant or extension; revoke individual grants immediately.
- View broker activity without logging file contents or credentials.

## Build

Requires macOS 14+, Xcode Command Line Tools, and Homebrew Python 3 at `/opt/homebrew/bin/python3`. Intel/custom Python paths are not yet supported by the launch flow.

```sh
bash scripts/build_menu_bar.sh
```

## Install from source

```sh
/opt/homebrew/bin/python3 scripts/install_menu_bar.py
open "$HOME/Library/Application Support/CodexGate/menu-bar/CodexGate.app"
```

The installer does not restart Codex or change active permissions. Quit the older Agent Folder Access menu app before using CodexGate: both currently use ports 8772/8773. Quitting the older controller ends its temporary grants.

Choose folders, save rules, finish active Codex work, fully quit Codex yourself, then use **Start protected Codex**. A normal Codex launch is not restricted by CodexGate.

## Important boundaries

- A sandbox indicator is not proof of the exact policy applied to a process.
- Rules take effect on a new protected launch; they cannot be attached to a running instance.
- Temporary grants provide broker-mediated read/list access, not direct filesystem unlock or writes.
- Agents do not automatically request access when a direct operation is blocked.
- Codex profile/runtime exceptions and system reads remain; this is not full system isolation.
- Computer Use and browser channels are outside the filesystem-control guarantee.
- Same-user unrestricted programs are outside the threat boundary.

See [security scope](SECURITY.md), [usage guide](docs/menu-bar.md), and [roadmap](docs/roadmap.md).

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_file_broker.py' -v
python3 -m unittest discover -s tests -p 'test_approval_ui.py' -v
python3 -m unittest discover -s tests -p 'test_controller_service.py' -v
```

Native policy/integration tests require macOS and a normal unsandboxed Terminal. Do not use private files as test fixtures.

## Website

`site/` contains the GitHub Pages landing page and setup guide, published by the included Actions workflow.

## License

MIT. See [LICENSE](LICENSE). Codex and ChatGPT are OpenAI product names; CodexGate is an independent community project.

## Local DMG preview

```sh
bash scripts/build_dmg.sh
python3 scripts/check_packaged_service.py
```

Output: `dist/CodexGate-0.1.0-arm64.dmg` on Apple Silicon, plus a SHA-256 file. Drag the app into Applications and eject the image. The packaged app includes its Python service runtime and authentication helper; target users do not need Homebrew Python. Build tooling still requires Homebrew Python, Swift tools, and the pinned PyInstaller dependency.

The app is ad-hoc signed for local testing, not Developer ID signed or notarized. Only the current build architecture is included. Older macOS compatibility and a clean-machine install remain unverified. Packaged runtime HTTP/asset/shutdown checks pass; real authentication and protected desktop launch must still be tested from Applications after active tasks finish.

`Casks/codexgate.rb.template` is the cask source template. The published tap contains the release URL and checksum. Developer ID signing/notarization and clean-machine testing remain future distribution improvements. Runtime license notices are included in the app.

## Experimental release

Download from [GitHub Releases](https://github.com/karan19/CodexGate/releases), or:

```sh
brew install --cask karan19/tap/codexgate
```

Website: https://karan19.github.io/CodexGate/

The Homebrew cask installs the same ad-hoc signed, unnotarized app. Homebrew does not bypass Gatekeeper. If blocked, see [Apple’s guidance](https://support.apple.com/102445); only use Open Anyway for a copy you trust.
