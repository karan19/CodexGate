"""Launch a separate Codex CLI; never reads existing auth/config files."""
import argparse
import os
from pathlib import Path
import shutil
from sandbox_launcher import command_for, validate_workspace

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    workspace = validate_workspace(options.workspace)
    found = shutil.which('codex')
    if not found:
        parser.error('Codex CLI not installed')
    binary = Path(found).resolve(strict=True)
    state = workspace / '.agent-state'
    temporary = workspace / '.agent-tmp'
    if temporary.is_symlink():
        parser.error('Agent temporary directory cannot be a symlink')
    temporary.mkdir(mode=0o700, exist_ok=True)
    if state.is_symlink():
        parser.error('Agent state cannot be a symlink')
    state.mkdir(mode=0o700, exist_ok=True)
    codex_home = state / 'codex'
    if codex_home.is_symlink():
        parser.error('Codex home cannot be a symlink')
    codex_home.mkdir(mode=0o700, exist_ok=True)
    args = options.args[1:] if options.args[:1] == ['--'] else options.args
    # Disable the inner sandbox to avoid nested Seatbelt errors. The outer launcher
    # confines the process and descendants. Runtime exception is executable-only.
    command = [str(binary), '-c', 'cli_auth_credentials_store="file"', '--sandbox', 'danger-full-access', *args]
    env = {'HOME': str(state), 'CODEX_HOME': str(codex_home), 'TMPDIR': str(temporary),
           'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin', 'TERM': os.environ.get('TERM', 'xterm-256color')}
    os.chdir(workspace)
    launch = command_for(workspace, command, runtime_files=[binary])
    os.execve(launch[0], launch, env)

if __name__ == '__main__': main()
