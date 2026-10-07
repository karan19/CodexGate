"""Normal-Terminal opt-in trial. No permission expansion or automatic restart."""
import hashlib
import inspect
import json
import re
from pathlib import Path
import shlex
import subprocess
import sys

FLAG = 'CODEX_ELECTRON_SKIP_COMPUTER_USE_CANONICAL_REFRESH'


def socket_policy(installed, socket):
    anchor = '(subpath "/private/tmp/codex-browser-use")'
    if installed.count(anchor) != 2:
        raise ValueError('Unexpected installed policy layout; refusing automatic modification')
    rule = ' '.join('(literal ' + json.dumps(str(path)) + ')' for path in (socket.parent, socket, Path(str(socket) + '.lock')))
    return installed.replace(anchor, anchor + ' ' + rule)


def screenshot_pattern(temp):
    return '^' + re.escape(str(temp)) + r'/[.]?[^/]{1,180} Screenshot [0-9]{4}-[0-9]{2}-[0-9]{2} at [0-9]{1,2}[.][0-9]{2}[.][0-9]{2} (AM|PM)[.](jpeg|jpg|png)(-[A-Za-z0-9]+)?$'


def screenshot_policy(policy, temp):
    pattern = screenshot_pattern(temp)
    if any(char in pattern for char in ('"', '\n', '\r')):
        raise ValueError('Unsupported temporary directory characters')
    anchor = '(subpath "/private/tmp/codex-browser-use")'
    if policy.count(anchor) != 2:
        raise ValueError('Unexpected policy layout')
    return policy.replace(anchor, anchor + ' (regex #"' + pattern + '")')


def tree_digest(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Helper root must be an existing real directory')
    result = {}
    for path in sorted(root.rglob('*')):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            result[relative] = ['symlink', str(path.readlink())]
        elif path.is_file():
            result[relative] = ['file', hashlib.sha256(path.read_bytes()).hexdigest()]
        elif path.is_dir():
            result[relative] = ['directory']
        else:
            raise ValueError('Unexpected helper file type')
    return result


def main():
    base = Path.home() / 'Library/Application Support/CodexGate'
    wrapper = base / 'launch-codex.command'
    args = shlex.split(next(line for line in wrapper.read_text().splitlines() if line.startswith('exec ')))
    release = Path(args[2]).parent
    policy = release / '.local/desktop-policy.sb'
    app = Path('/Applications/ChatGPT.app')
    source = app / 'Contents/Resources/cua_node/lib/node_modules/@oai/sky/Codex Computer Use.app'
    helper = Path.home() / '.codex/computer-use/Codex Computer Use.app'
    if FLAG.encode() not in (app / 'Contents/Resources/app.asar').read_bytes():
        raise ValueError('Installed build no longer contains the experimental refresh switch')
    if tree_digest(source) != tree_digest(helper):
        raise ValueError('Existing helper differs from bundled version. Trial not prepared; refresh must be handled separately.')
    for bundle in (source, helper):
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(bundle)], check=True, capture_output=True)
    if not policy.is_file():
        raise ValueError('Installed policy is missing')
    native_socket = Path.home() / 'Library/Group Containers/2DC432GLL2.com.openai.sky.CUAService/IPC/computeruse.sock'
    if native_socket.parent.resolve() != native_socket.parent:
        raise ValueError('IPC directory cannot contain symlink ancestors')
    native_socket.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    trial_policy = release / '.local/computer-use-trial-policy.sb'
    darwin_temp = Path(subprocess.check_output(['/usr/bin/getconf', 'DARWIN_USER_TEMP_DIR'], text=True).strip()).resolve(strict=True)
    trial_policy.write_text(screenshot_policy(socket_policy(policy.read_text(), native_socket), darwin_temp))
    # Exercise the screenshot staging/rename path, with dummy bytes only, and
    # require denial of unrelated reads and writes in the same temp directory.
    import tempfile
    with tempfile.TemporaryDirectory(dir=base, prefix='screenshot-probe-') as outside:
        private = Path(outside) / 'dummy.txt'
        private.write_text('dummy')
        code = '''import os,pathlib,secrets,sys
t=pathlib.Path(sys.argv[1]); private=pathlib.Path(sys.argv[2])
name='CodexGate '+secrets.token_hex(6)+' Screenshot 2000-01-01 at 1.00.00 PM.jpeg'
stage=t/('.'+name+'-Test123'); final=t/name
try:
    stage.write_bytes(b'dummy'); stage.rename(final); assert final.read_bytes()==b'dummy'
    for path,op in ((private,'read'),(t/('unrelated-'+secrets.token_hex(6)),'write')):
        try:
            path.read_bytes() if op=='read' else path.write_bytes(b'dummy')
        except PermissionError: pass
        else: raise RuntimeError('Outside operation unexpectedly allowed')
finally:
    stage.unlink(missing_ok=True); final.unlink(missing_ok=True)
'''
        subprocess.run(['/usr/bin/sandbox-exec', '-f', str(trial_policy), sys.executable, '-c', code, str(darwin_temp), str(private)], cwd=Path.home() / 'workspace', check=True, capture_output=True)
    socket_temp = Path.home() / 'Library/Caches/CodexGate/tmp'
    # Exact IPC directory, socket and companion lock; other files stay blocked.
    env = {'HOME': str(Path.home()), 'CODEX_HOME': str(Path.home() / '.codex'),
           'TMPDIR': str(socket_temp) + '/', 'MAC_CHROMIUM_TMPDIR': str(socket_temp),
           'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin', FLAG: '1'}
    command = ['/usr/bin/env', '-i', *(key + '=' + value for key, value in env.items()),
               '/usr/bin/sandbox-exec', '-f', str(trial_policy), str(app / 'Contents/MacOS/ChatGPT'), '--no-sandbox']
    # Store fingerprint checks outside the agent-writable workspace. Fail closed
    # after app/helper/policy updates; the user must prepare a new trial.
    script = base / 'launch-computer-use-trial.command'
    inputs = [policy, trial_policy, app / 'Contents/Resources/app.asar', source / 'Contents/MacOS/SkyComputerUseService', helper / 'Contents/MacOS/SkyComputerUseService']
    fingerprints = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    checks = base / 'computer-use-trial-checks.json'
    checks.write_text(json.dumps({'files': fingerprints, 'trees': {str(source): tree_digest(source), str(helper): tree_digest(helper)}}))
    verifier = base / 'verify-computer-use-trial.py'
    verifier.write_text('import hashlib,json,sys\nfrom pathlib import Path\n' + inspect.getsource(tree_digest)
                        + '\nchecks=json.loads(Path(sys.argv[1]).read_text())\n'
                        + 'if not all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in checks["files"].items()) or not all(tree_digest(p)==d for p,d in checks["trees"].items()):\n    raise SystemExit("Trial inputs changed; prepare again")\n')
    checks.chmod(0o600); verifier.chmod(0o600)
    script.write_text('#!/bin/sh\nset -eu\n' + shlex.join([sys.executable, str(verifier), str(checks)]) + '\n'
                      + 'if /bin/ps -axo comm= | /usr/bin/grep -Fqx ' + shlex.quote(str(app / 'Contents/MacOS/ChatGPT')) + '; then\n  echo "Fully quit Codex before launching this trial." >&2\n  exit 2\nfi\n'
                      + 'cd ' + shlex.quote(str(Path.home() / 'workspace')) + '\nexec ' + shlex.join(command) + '\n')
    script.chmod(0o700)
    print('Experimental trial prepared. Helper files and signatures match.')
    print('Exact IPC directory, socket and socket.lock exceptions added; other container files remain blocked: ' + str(native_socket))
    print('Screenshot filename rule added; dummy staging/rename passed and unrelated temp access remained blocked.')
    print('No app was restarted. When chats are idle, fully quit Codex and run:')
    print(shlex.join(['/bin/bash', str(script)]))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Trial not prepared: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
