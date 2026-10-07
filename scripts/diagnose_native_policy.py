"""Normal-Terminal dummy-file diagnostic; never installs or starts Codex."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from launch_desktop import desktop_policy, existing_profile_paths
from sandbox_launcher import PROJECT

with tempfile.TemporaryDirectory(dir=PROJECT / '.local', prefix='native-policy-') as temp:
    root = Path(temp).resolve()
    workspace, runtime, home = (root / n for n in ('workspace', 'runtime', 'home'))
    for d in (workspace, runtime, home): d.mkdir()
    helper = home / '.codex/computer-use/Dummy.app'
    helper.mkdir(parents=True)
    helper.chmod(0o700)
    private = home / 'private'
    private.mkdir(mode=0o700)
    (private / 'dummy.txt').write_text('dummy')
    policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), profile_paths=existing_profile_paths(home))
    variants = {
        # Separate macOS sandbox execution constraints from our filesystem rules.
        'allow_all_control': '(version 1)\n(allow default)\n',
        'baseline': '',
        'explicit_mode_denial': '\n(deny file-write-mode (require-not (require-any ' + ' '.join('(subpath ' + json.dumps(str(p)) + ')' for p in (workspace, runtime, *existing_profile_paths(home))) + ')))\n',
        'ps_exec_rule': '\n(allow process-exec (literal "/bin/ps"))\n',
        'helper_mode_rule': '\n(allow file-write-mode (subpath ' + json.dumps(str(helper.parent)) + '))\n',
    }
    result = {}
    for name, extra in variants.items():
        rules = extra if name == 'allow_all_control' else policy + extra
        checks = {}
        r = subprocess.run(['/usr/bin/sandbox-exec', '-p', rules, '/usr/bin/true'], cwd=workspace, capture_output=True, timeout=10)
        checks['ordinary_exec_control'] = {'exit': r.returncode, 'error': r.stderr.decode()[:180]}
        for label, path in (('allowed_helper_chmod', helper), ('outside_chmod', private)):
            path.chmod(0o700)
            command = ['/bin/chmod', '755', str(path)]
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', rules, *command], cwd=workspace, capture_output=True)
            checks[label] = {'exit': r.returncode, 'mode_changed': path.stat().st_mode & 0o777 != 0o700, 'error': r.stderr.decode()[:180]}
        # Codex passes the complete lstat mode (including directory type bits)
        # ORed with owner-write, rather than a plain 0755 mode.
        for label, path in (('helper_codex_chmod', helper), ('outside_codex_chmod', private)):
            path.chmod(0o500)
            code = 'import os,sys; p=sys.argv[1]; os.chmod(p,os.lstat(p).st_mode | 128)'
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', rules, sys.executable, '-c', code, str(path)], cwd=workspace, capture_output=True, timeout=10)
            checks[label] = {'exit': r.returncode, 'mode_changed': path.stat().st_mode & 0o777 != 0o500, 'error': r.stderr.decode()[-220:]}
        r = subprocess.run(['/usr/bin/sandbox-exec', '-p', rules, '/bin/ps', '-p', str(os.getpid()), '-o', 'pid='], cwd=workspace, capture_output=True)
        checks['ps'] = {'exit': r.returncode, 'error': r.stderr.decode()[:180]}
        result[name] = checks
    print(json.dumps({'ps_setuid': bool(Path('/bin/ps').stat().st_mode & 0o4000), 'variants': result}, indent=2))
    print('Diagnostic only: no deployment, profile, or personal files changed.')
