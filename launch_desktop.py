"""Experimental desktop launcher with fresh or existing profile. Requires quitting Codex first."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
from sandbox_launcher import PROJECT

def validate_workspace(path):
    workspace = Path(path).resolve(strict=True)
    if not workspace.is_dir() or workspace in (Path("/"), Path.home()):
        raise ValueError("Select an existing workspace directory, not root or home")
    return workspace

APP_CANDIDATES = (Path('/Applications/ChatGPT.app'), Path('/Applications/Codex.app'))

def find_app():
    for app in APP_CANDIDATES:
        try:
            with (app / 'Contents/Info.plist').open('rb') as handle:
                info = plistlib.load(handle)
            if info.get('CFBundleIdentifier') == 'com.openai.codex':
                executable = app / 'Contents/MacOS' / info['CFBundleExecutable']
                if executable.is_file(): return app, executable
        except (OSError, KeyError, ValueError):
            continue
    raise ValueError('Codex desktop application not found')

def existing_profile_paths(home=None):
    home = Path(home) if home else Path.home()
    return tuple(home / relative for relative in (
        '.codex', '.cache/codex-runtimes', 'Library/Application Support/Codex',
        'Library/Application Support/com.openai.codex',
        'Library/Caches/Codex', 'Library/Caches/com.openai.codex',
        'Library/Logs/com.openai.codex', 'Library/HTTPStorages/com.openai.codex',
        'Library/HTTPStorages/com.openai.codex.binarycookies',
        'Library/Preferences/com.openai.codex.plist'))

def desktop_policy(workspace, runtime, app, socket_temp=None, profile_paths=(), runtime_paths=(), cache_regex=None, read_paths=()):
    workspace = validate_workspace(workspace)
    runtime = Path(runtime).resolve(strict=True)
    if runtime.is_relative_to(workspace) or workspace.is_relative_to(runtime):
        raise ValueError('Desktop runtime must be separate from agent workspace')
    writable = (workspace, runtime) + ((Path(socket_temp).resolve(strict=True),) if socket_temp else ())
    for path in profile_paths:
        if Path(path).resolve() != Path(path):
            raise ValueError('Profile exception cannot contain a symlink: ' + str(path))
    writable += tuple(Path(p) for p in profile_paths)
    for path in runtime_paths:
        if Path(path).resolve() != Path(path):
            raise ValueError('Runtime exception cannot contain a symlink: ' + str(path))
    writable += tuple(Path(p) for p in runtime_paths)
    permitted = ' '.join('(subpath ' + json.dumps(str(p)) + ')' for p in (*writable, app))
    permitted += ' ' + ' '.join('(subpath ' + json.dumps(str(p)) + ')' for p in read_paths)
    write_rules = ' '.join('(subpath ' + json.dumps(str(p)) + ')' for p in writable)
    if cache_regex:
        # SBPL regex literals preserve regex backslashes. JSON escaping turns
        # '\.' into '\\.' and changes which paths the expression matches.
        if any(char in cache_regex for char in ('"', '\n', '\r')):
            raise ValueError('Cache regex contains unsupported literal characters')
        rule = '(regex #"' + cache_regex + '")'
        permitted += ' ' + rule
        write_rules += ' ' + rule
    return '''(version 1)
(allow default)
(deny file-read-data (require-all (require-any (subpath "/Users") (subpath "/Volumes") (subpath "/private/tmp") (subpath "/private/var/folders")) (require-not (require-any %s))))
(deny file-write* (require-all (require-not (require-any %s)) (require-not (literal "/dev/null"))))
''' % (permitted, write_rules)

def prepare(workspace, existing_profile=False):
    workspace = validate_workspace(workspace)
    if (PROJECT / "manifest.json").exists():
        from deployment import verify
        verify(PROJECT)
    app, executable = find_app()
    if PROJECT.is_relative_to(workspace):
        raise ValueError('Install the trusted launcher outside the workspace before preparing desktop launch')
    runtime = PROJECT / '.local' / 'desktop-runtime'
    if runtime.is_symlink(): raise ValueError('Runtime cannot be a symlink')
    runtime.mkdir(parents=True, mode=0o700, exist_ok=True)
    runtime = runtime.resolve()
    for name in ('codex', 'profile', 'tmp'):
        child = runtime / name
        if child.is_symlink(): raise ValueError('Runtime child cannot be a symlink')
        child.mkdir(mode=0o700, exist_ok=True)
    socket_temp = Path.home() / 'Library/Caches/CodexGate/tmp'
    if socket_temp.is_symlink(): raise ValueError('Socket temporary directory cannot be a symlink')
    socket_temp.mkdir(parents=True, mode=0o700, exist_ok=True)
    socket_temp = socket_temp.resolve()
    browser_pipe = Path('/private/tmp/codex-browser-use')
    if browser_pipe.is_symlink(): raise ValueError('Browser pipe directory cannot be a symlink')
    browser_pipe.mkdir(mode=0o700, exist_ok=True)
    if not browser_pipe.is_dir() or browser_pipe.stat().st_uid != os.getuid():
        raise ValueError('Browser pipe directory must be owned by the current user')
    darwin_tmp = Path(subprocess.check_output(['/usr/bin/getconf', 'DARWIN_USER_TEMP_DIR'], text=True).strip()).resolve(strict=True)
    cache_regex = '^' + re.escape(str(darwin_tmp)) + '/xcrun_db(-[A-Za-z0-9]+)?$'
    policy = desktop_policy(workspace, runtime, app, socket_temp, existing_profile_paths() if existing_profile else (), (browser_pipe,), cache_regex)
    target = PROJECT / '.local' / 'desktop-policy.sb'
    target.write_text(policy)
    return workspace, runtime, executable, target, socket_temp

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--existing-profile', action='store_true', help='Use existing chats/settings with explicit Codex data exceptions')
    args = parser.parse_args()
    try:
        workspace, runtime, executable, policy, socket_temp = prepare(args.workspace, args.existing_profile)
        command = ['/usr/bin/sandbox-exec', '-f', str(policy), str(executable), '--no-sandbox']
        if not args.existing_profile:
            command.append('--user-data-dir=' + str(runtime / 'profile'))
        if args.prepare_only:
            print(json.dumps({'status': 'prepared; desktop protection unverified', 'profile_mode': 'existing' if args.existing_profile else 'fresh', 'profile_exceptions': [str(p) for p in existing_profile_paths()] if args.existing_profile else [], 'workspace': str(workspace), 'runtime_exception': str(runtime), 'socket_temp_exception': str(socket_temp), 'workspace_scope': 'All folders, including hidden folders; no project-specific exclusions', 'policy': str(policy), 'executable': str(executable), 'command': command}, indent=2)); return
        # A running instance may capture the launch and silently retain its old permissions.
        processes = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True, text=True, check=True)
        if any(line.strip() == str(executable) for line in processes.stdout.splitlines()):
            raise ValueError('Codex is still running. Fully quit it before using this launcher.')
        env = {'HOME': str(Path.home()), 'CODEX_HOME': str(Path.home() / '.codex') if args.existing_profile else str(runtime / 'codex'), 'TMPDIR': str(socket_temp) + '/', 'MAC_CHROMIUM_TMPDIR': str(socket_temp), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'}
        os.chdir(workspace)
        os.execve(command[0], command, env)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + '\n')

if __name__ == '__main__': main()
