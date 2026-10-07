"""Immutable-by-convention snapshots outside the confined agent's writable root.

Manifest checks detect accidental modification, not hostile same-user tampering.
The outer sandbox provides the tested child-process write restriction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

SOURCE = Path(__file__).resolve().parent
FILES = ('app.py', 'index.html', 'isolation.py', 'sandbox_launcher.py', '.build/authenticate', 'launch_desktop.py', 'deployment.py')

def verify(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / 'manifest.json').read_text())
    if set(manifest.get('files', {})) != set(FILES):
        raise ValueError('Deployment manifest has an unexpected file set')
    for name, expected in manifest['files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Deployment file missing or symlinked: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Deployment changed: ' + name)
    return root

def stage(destination=None):
    base = Path(destination).expanduser().resolve() if destination else SOURCE / '.local' / 'deployments'
    base.mkdir(parents=True, exist_ok=True)
    root = base / ('release-' + uuid.uuid4().hex[:12])
    root.mkdir(mode=0o700)
    try:
        digests = {}
        for name in FILES:
            source = SOURCE / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('Build native helper first; missing file: ' + name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            digests[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        (root / 'manifest.json').write_text(json.dumps({'files': digests}, indent=2))
        verify(root)
        return root
    except Exception:
        shutil.rmtree(root)
        raise

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    stage_parser = sub.add_parser('stage'); stage_parser.add_argument('--destination')
    check = sub.add_parser('check'); check.add_argument('release')
    run = sub.add_parser('run'); run.add_argument('release')
    args = parser.parse_args()
    try:
        if args.action == 'stage':
            print(stage(args.destination)); return
        root = verify(args.release)
        if args.action == 'check':
            print('Deployment file hashes verified. OS isolation is a separate check.'); return
        os.chdir(root)
        os.execv(sys.executable, [sys.executable, str(root / 'app.py')])
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')

if __name__ == '__main__': main()
