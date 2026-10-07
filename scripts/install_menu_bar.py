"""User-run menu-bar installer. Does not restart Codex or change its policy."""
from pathlib import Path
import shutil
import subprocess

source = Path(__file__).resolve().parents[1]
subprocess.run(['/bin/bash', str(source / 'scripts/build_menu_bar.sh')], cwd=source, check=True)
subprocess.run(['/bin/bash', str(source / 'scripts/build_native.sh')], cwd=source, check=True)
destination = Path.home() / 'Library/Application Support/CodexGate/menu-bar'
if destination.is_symlink():
    raise ValueError('Symlinked installation directory rejected')
destination.mkdir(parents=True, exist_ok=True, mode=0o700)
target = destination / 'CodexGate.app'
if target.is_symlink():
    raise ValueError('Symlinked application rejected')
if target.exists():
    shutil.rmtree(target)
shutil.copytree(source / '.build/CodexGate.app', target, symlinks=False)
for name in ('managed_launch.py', 'launch_desktop.py', 'sandbox_launcher.py', 'file_broker.py', 'approval_ui.py', 'approval.html', 'approval.js', 'approval.css', '.build/authenticate'):
    original = source / name
    installed = destination / name
    if original.is_symlink() or installed.is_symlink():
        raise ValueError('Symlinked launcher rejected')
    installed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, installed)
dummy = destination / 'demo-folder'
if dummy.is_symlink():
    raise ValueError('Symlinked demo folder rejected')
dummy.mkdir(exist_ok=True, mode=0o700)
if not (dummy / 'hello.txt').exists():
    (dummy / 'hello.txt').write_text('CodexGate demo. No personal data.\n')
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(target)], check=True)
print('Installed. Quit only the old CodexGate menu app, then run:')
import shlex
print('open ' + shlex.quote(str(target)))
print('Codex and its active chats were not restarted. No folder policy was changed.')
