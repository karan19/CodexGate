"""Launch a new protected desktop instance with the menu-bar's saved rules."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from launch_desktop import desktop_policy, existing_profile_paths, prepare


def validate_config(data, control):
    if not isinstance(data, dict) or set(data) != {'workspace', 'folders'}:
        raise ValueError('Invalid permission configuration')
    control = Path(control).resolve(strict=True)
    def folder(value):
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Folders must be absolute paths')
        path = Path(value).resolve(strict=True)
        if not path.is_dir() or path in (Path('/'), Path.home()):
            raise ValueError('Choose an existing folder below root or home')
        if path.is_relative_to(control) or control.is_relative_to(path):
            raise ValueError('Folder rules cannot expose the permission controller')
        return path
    workspace = folder(data['workspace'])
    if not isinstance(data['folders'], list) or len(data['folders']) > 100:
        raise ValueError('Invalid folder rules')
    reads, writes = [], []
    for item in data['folders']:
        if not isinstance(item, dict) or set(item) != {'path', 'access'} or item['access'] not in ('read', 'read-write'):
            raise ValueError('Invalid folder permission')
        path = folder(item['path'])
        (reads if item['access'] == 'read' else writes).append(path)
    return workspace, reads, writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--show-policy', action='store_true')
    args = parser.parse_args()
    try:
        control = Path(__file__).resolve().parent
        if control.is_relative_to(Path.home() / 'workspace'):
            raise ValueError('Use the installed launcher outside workspace')
        workspace, reads, writes = validate_config(json.loads(Path(args.config).read_text()), control)
        workspace, runtime, executable, target, temp = prepare(workspace, existing_profile=True)
        darwin_tmp = Path(subprocess.check_output(['/usr/bin/getconf', 'DARWIN_USER_TEMP_DIR'], text=True).strip()).resolve(strict=True)
        policy = desktop_policy(workspace, runtime, executable.parents[2], temp,
                                (*existing_profile_paths(), *writes), (Path('/private/tmp/codex-browser-use'),),
                                '^' + re.escape(str(darwin_tmp)) + '/xcrun_db(-[A-Za-z0-9]+)?$', read_paths=reads)
        target.write_text(policy)
        if args.show_policy:
            print(policy)
            return
        processes = subprocess.check_output(['/bin/ps', '-axo', 'comm='], text=True)
        if any(line.strip() == str(executable) for line in processes.splitlines()):
            raise ValueError('Fully quit Codex desktop after active tasks finish. No process was stopped.')
        env = {'HOME': str(Path.home()), 'CODEX_HOME': str(Path.home() / '.codex'), 'TMPDIR': str(temp) + '/',
               'MAC_CHROMIUM_TMPDIR': str(temp), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'}
        os.chdir(workspace)
        os.execve('/usr/bin/sandbox-exec', ['/usr/bin/sandbox-exec', '-f', str(target), str(executable), '--no-sandbox'], env)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
