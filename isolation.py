"""Disposable OS sandbox probe, restricted to generated dummy files."""
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from sandbox_launcher import policy_for, PROJECT

_lock = threading.Lock()
SCRIPT = '''
/bin/cat "$1/input.txt" >/dev/null 2>&1; printf 'workspace_read=%s\\n' "$?"
(printf dummy > "$1/output.txt") 2>/dev/null; printf 'workspace_write=%s\\n' "$?"
/bin/cat "$2/input.txt" >/dev/null 2>&1; printf 'protected_read=%s\\n' "$?"
(printf dummy > "$2/output.txt") 2>/dev/null; printf 'protected_write=%s\\n' "$?"
/bin/cat "$1/escape/input.txt" >/dev/null 2>&1; printf 'symlink_read=%s\\n' "$?"
/bin/cat "$3/app.py" >/dev/null 2>&1; printf 'broker_source_read=%s\\n' "$?"
/bin/sh -c '/bin/cat "$1/input.txt" >/dev/null 2>&1' child "$2"; printf 'child_protected_read=%s\\n' "$?"
'''

def run_probe():
    if not _lock.acquire(blocking=False):
        raise ValueError('An isolation check is already running')
    try:
        base = Path(__file__).parent / '.local'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='isolation-', dir=base) as temporary:
            root = Path(temporary).resolve()
            allowed, protected = root / 'workspace', root / 'protected'
            for directory in (allowed, protected):
                directory.mkdir()
                (directory / 'input.txt').write_text('synthetic test content\n')
            (allowed / 'escape').symlink_to(protected, target_is_directory=True)
            policy = policy_for(allowed)
            args = ['/bin/sh', '-c', SCRIPT, 'probe', str(allowed), str(protected), str(PROJECT)]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(allowed)}
            baseline = subprocess.run(args, cwd=allowed, env=env, capture_output=True, text=True, timeout=10)
            for d in (allowed, protected):
                (d / 'output.txt').unlink(missing_ok=True)
            sandboxed = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, *args], cwd=allowed, env=env, capture_output=True, text=True, timeout=10)
            def parse(result):
                if result.returncode != 0:
                    return {}
                return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
            before, after = parse(baseline), parse(sandboxed)
            expected = {'workspace_read': True, 'workspace_write': True, 'protected_read': False, 'protected_write': False, 'symlink_read': False, 'broker_source_read': False, 'child_protected_read': False}
            checks = [{'name': key, 'passed': before.get(key) == '0' and key in after and (after[key] == '0') == permitted} for key, permitted in expected.items()]
            return {'status': 'passed' if all(c['passed'] for c in checks) else 'failed', 'checks': checks, 'scope': 'Disposable shell subprocess only; this Codex chat and the demo server are not sandboxed.', 'error': (sandboxed.stderr[:500] or 'Sandbox subprocess exited with code ' + str(sandboxed.returncode)) if sandboxed.returncode else None}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'status': 'unavailable', 'checks': [], 'scope': 'No protection verified', 'error': str(error)}
    finally:
        _lock.release()

if __name__ == '__main__':
    print(json.dumps(run_probe(), indent=2))
