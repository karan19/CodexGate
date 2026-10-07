"""User-run installer for a separate broker trial; does not restart Codex."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

source = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_file_broker.py', '-v'], cwd=source, check=True)
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_approval_ui.py', '-v'], cwd=source, check=True)
subprocess.run(['/bin/bash', str(source / 'scripts/build_native.sh')], cwd=source, check=True)
base = Path.home() / 'Library/Application Support/CodexGate/broker-trials'
base.mkdir(parents=True, exist_ok=True)
release = base / ('trial-' + uuid.uuid4().hex[:12])
release.mkdir(mode=0o700)
files = ('file_broker.py', 'approval_ui.py', 'approval.html', 'approval.js', 'approval.css', '.build/authenticate')
for name in files:
    original = source / name
    if original.is_symlink():
        raise ValueError('Symlinked source rejected')
    target = release / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, target)
(release / 'manifest.json').write_text(json.dumps({name: hashlib.sha256((release / name).read_bytes()).hexdigest() for name in files}, indent=2))
dummy = release / 'dummy-folder'
dummy.mkdir(mode=0o700)
(dummy / 'hello.txt').write_text('Dummy broker test. No personal data.\n')
print('\nPrepared a separate dummy trial. Desktop policy was not changed.')
print('Run this in the same normal Terminal, and leave it open:')
import shlex
print(shlex.join([sys.executable, str(release / 'file_broker.py'), '--root', str(dummy)]))
