"""Normal-Terminal check of installed policy using fresh dummy files only."""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

base = Path.home() / 'Library/Application Support/CodexGate'
wrapper = base / 'launch-codex.command'
line = next(line for line in wrapper.read_text().splitlines() if line.startswith('exec '))
args = shlex.split(line)
launcher = Path(args[2])
policy = launcher.parent / '.local/desktop-policy.sb'
if not policy.is_file():
    raise SystemExit('Installed policy not found; nothing changed.')
workspace = Path.home() / 'workspace'
with tempfile.TemporaryDirectory(dir=workspace, prefix='boundary-inside-') as inside, tempfile.TemporaryDirectory(dir=base, prefix='boundary-outside-') as outside:
    inner, outer = Path(inside), Path(outside)
    (inner / 'probe.txt').write_text('dummy')
    (outer / 'probe.txt').write_text('dummy')
    results = {}
    for label, path, expected in (('workspace', inner, 0), ('outside', outer, 1)):
        for operation, command in (
            ('read', ['/bin/cat', str(path / 'probe.txt')]),
            ('write', ['/bin/sh', '-c', 'printf dummy > "$1"', 'probe', str(path / 'write.txt')]),
        ):
            run = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(policy), *command], cwd=workspace, capture_output=True, timeout=10)
            allowed = run.returncode == 0
            results[label + '_' + operation] = {'allowed': allowed, 'pass': allowed == (expected == 0)}
    print(json.dumps({'policy': str(policy), 'checks': results, 'all_pass': all(item['pass'] for item in results.values())}, indent=2))
print('This checks the installed policy in a new subprocess, not the running desktop tools. No deployment changed.')
