"""Normal-Terminal installed-policy check. Only disposable dummy files change."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

source = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(source))
from launch_desktop import desktop_policy, existing_profile_paths, find_app

base = Path.home() / 'Library/Application Support/CodexGate'
wrapper = base / 'launch-codex.command'
line = next(line for line in wrapper.read_text().splitlines() if line.startswith('exec '))
release = Path(shlex.split(line)[2]).parent
installed_path = release / '.local/desktop-policy.sb'
installed = installed_path.read_text()
helper_parent = Path.home() / '.codex/computer-use'
helper = helper_parent / 'Codex Computer Use.app'
info = helper.lstat()
app, _ = find_app()
runtime = release / '.local/desktop-runtime'
socket_temp = Path.home() / 'Library/Caches/CodexGate/tmp'
generated = desktop_policy(Path.home() / 'workspace', runtime, app, socket_temp, existing_profile_paths(), (Path('/private/tmp/codex-browser-use'),))
result = {'installed_policy': str(installed_path), 'policy_sha256': hashlib.sha256(installed.encode()).hexdigest(),
          'installed_policy_rules': installed.splitlines(),
          'actual_helper_metadata': {'mode': oct(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid, 'flags': info.st_flags, 'symlink': helper.is_symlink()}, 'checks': {}}
with tempfile.TemporaryDirectory(dir=helper_parent, prefix='dummy-policy-') as allowed, tempfile.TemporaryDirectory(dir=base, prefix='dummy-policy-') as outside:
    for label, rules in (('installed', installed), ('generated', generated)):
        checks = {}
        for scope, folder in (('helper', allowed), ('outside', outside)):
            dummy = Path(folder) / 'Dummy.app'
            dummy.mkdir(exist_ok=True)
            dummy.chmod(0o500)
            code = 'import os,sys; p=sys.argv[1]; os.chmod(p,os.lstat(p).st_mode | 128)'
            run = subprocess.run(['/usr/bin/sandbox-exec', '-p', rules, sys.executable, '-c', code, str(dummy)], cwd=Path.home() / 'workspace', capture_output=True, timeout=10)
            checks[scope] = {'exit': run.returncode, 'mode_changed': bool(dummy.stat().st_mode & 0o200), 'error': run.stderr.decode()[-220:]}
            dummy.chmod(0o700)
        result['checks'][label] = checks
print(json.dumps(result, indent=2))
print('No real helper, deployment, or personal file was modified. Only dummy fixtures were created and removed.')
