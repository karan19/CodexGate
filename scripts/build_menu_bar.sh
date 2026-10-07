#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
app='.build/CodexGate.app'
mkdir -p "$app/Contents/MacOS" .build/menu-module-cache
cp native/MenuBar.swift .build/main.swift
/usr/bin/xcrun swiftc .build/main.swift native/PermissionsPanel.swift native/AccessPopover.swift -o "$app/Contents/MacOS/CodexGate" -module-cache-path .build/menu-module-cache -framework AppKit -framework SwiftUI -lproc -lsandbox
/opt/homebrew/bin/python3 -c 'import plistlib; from pathlib import Path; p=Path(".build/CodexGate.app/Contents/Info.plist"); p.write_bytes(plistlib.dumps({"CFBundleIdentifier":"community.codexgate.menubar", "CFBundleName":"CodexGate", "CFBundleExecutable":"CodexGate", "CFBundlePackageType":"APPL", "CFBundleVersion":"1", "CFBundleShortVersionString":"0.1", "LSUIElement":True, "NSHighResolutionCapable":True, "LSMinimumSystemVersion":"14.0"}))'
mkdir -p "$app/Contents/Resources" .build/CodexGate.iconset
/usr/bin/xcrun swift scripts/make_app_icon.swift .build/CodexGate.iconset
/usr/bin/iconutil -c icns .build/CodexGate.iconset -o "$app/Contents/Resources/CodexGate.icns"
/opt/homebrew/bin/python3 -c 'import plistlib; from pathlib import Path; p=Path(".build/CodexGate.app/Contents/Info.plist"); v=plistlib.loads(p.read_bytes()); v["CFBundleIconFile"]="CodexGate.icns"; p.write_bytes(plistlib.dumps(v))'
/usr/bin/codesign --force --sign - "$app"
echo "Built: $(pwd)/$app"
