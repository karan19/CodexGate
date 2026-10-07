"""Experimental filesystem confinement for newly launched child commands only."""
import argparse
import json
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
RUNTIME_READS = ('/System', '/usr', '/bin', '/sbin', '/Library/Apple', '/private/var/db/dyld', '/dev')

def validate_workspace(path):
    workspace = Path(path).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError('Workspace must be an existing directory')
    # Giving the agent access to the broker source permits modification of its authority.
    if PROJECT.is_relative_to(workspace):
        raise ValueError('Workspace cannot contain the broker project')
    if workspace == Path('/') or workspace == Path.home():
        raise ValueError('Select a specific workspace, not root or home')
    for runtime in RUNTIME_READS:
        if workspace.is_relative_to(Path(runtime)):
            raise ValueError('Workspace cannot be a system runtime directory')
    return workspace

def policy_for(path, runtime_files=()):
    workspace = validate_workspace(path)
    # File data in common personal/storage locations is denied outside workspace.
    # Other locations retain runtime reads; this is not a complete allowlist yet.
    blocked = ('/Users', '/Volumes', '/private/tmp', '/private/var/folders')
    locations = ' '.join('(subpath ' + json.dumps(p) + ')' for p in blocked)
    exceptions = ' '.join('(literal ' + json.dumps(str(Path(p).resolve(strict=True))) + ')' for p in runtime_files)
    excluded = '(require-not (require-any ' + exceptions + '))' if exceptions else ''
    return """(version 1)
(allow default)
(deny file-read-data (require-all (require-any %s) (require-not (subpath %s)) %s))
(deny file-write* (require-all (require-not (subpath %s)) (require-not (literal "/dev/null"))))
""" % (locations, json.dumps(str(workspace)), excluded, json.dumps(str(workspace)))

def command_for(workspace, command, runtime_files=()):
    if not command:
        raise ValueError('Provide a command after --')
    return ['/usr/bin/sandbox-exec', '-p', policy_for(workspace, runtime_files), *command]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--show-policy', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        workspace = validate_workspace(args.workspace)
        if args.show_policy:
            print(policy_for(workspace))
            return
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        launch = command_for(workspace, command)
        # Do not forward provider credentials, agent configuration, or library injection
        # environment from the unrestricted parent into the child.
        state = workspace / '.agent-state'
        state.mkdir(mode=0o700, exist_ok=True)
        if state.is_symlink():
            raise ValueError('Agent state cannot be a symlink')
        env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',
               'HOME': str(state), 'CODEX_HOME': str(state / 'codex'),
               'TMPDIR': str(state), 'TERM': os.environ.get('TERM', 'xterm-256color')}
        os.chdir(workspace)
        os.execve(launch[0], launch, env)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')

if __name__ == '__main__':
    main()
