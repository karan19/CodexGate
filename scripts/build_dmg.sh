#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
version=0.1.0
bash scripts/build_menu_bar.sh
bash scripts/build_native.sh
if [ ! -x .build/package-venv/bin/pyinstaller ]; then
  /opt/homebrew/bin/python3 -m venv .build/package-venv
  .build/package-venv/bin/pip install -r packaging/requirements.txt
fi
.build/package-venv/bin/pyinstaller --noconfirm --clean --onedir --name codexgate-service --distpath .build/package-dist --workpath .build/package-work --specpath .build --add-data "$PWD/approval.html:." --add-data "$PWD/approval.js:." --add-data "$PWD/approval.css:." package_service.py
app='.build/CodexGate.app'
mkdir -p "$app/Contents/Resources"
rm -rf "$app/Contents/Resources/backend"
cp -R .build/package-dist/codexgate-service "$app/Contents/Resources/backend"
cp .build/authenticate "$app/Contents/Resources/authenticate"
cp LICENSE "$app/Contents/Resources/LICENSE"
cp -R packaging/licenses "$app/Contents/Resources/ThirdPartyLicenses"
/opt/homebrew/bin/python3 - <<'PY'
from pathlib import Path
import plistlib
p=Path('.build/CodexGate.app/Contents/Info.plist')
v=plistlib.loads(p.read_bytes());v['CFBundleShortVersionString']='0.1.0';p.write_bytes(plistlib.dumps(v))
PY
/usr/bin/codesign --force --deep --sign - "$app"
/usr/bin/codesign --verify --deep --strict "$app"
mkdir -p dist
rm -rf .build/dmg-root
mkdir .build/dmg-root
cp -R "$app" .build/dmg-root/
ln -s /Applications ".build/dmg-root/Applications — Drag CodexGate here"

arch=$(uname -m)
image="dist/CodexGate-$version-$arch.dmg"
rm -f "$image"
/usr/bin/hdiutil create -volname "CodexGate — Drag to Applications" -srcfolder .build/dmg-root -ov -format UDZO "$image"
/usr/bin/shasum -a 256 "$image" > "$image.sha256"
echo "Local unsigned test image: $image"
