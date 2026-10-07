"""Run from a normal Terminal; never quits or launches Codex."""
from pathlib import Path
import os
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deployment import stage, verify

# The real sandbox checks must run from a normal Terminal, not a sandboxed chat.
# Do not publish a new launcher if any check fails.
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=Path(__file__).resolve().parents[1], check=True)
base = Path.home() / 'Library/Application Support/CodexGate'
release = stage(base / 'releases')
verify(release)
subprocess.run([sys.executable, str(release / 'launch_desktop.py'), '--workspace', str(Path.home() / 'workspace'), '--existing-profile', '--prepare-only'], check=True)
wrapper = base / 'launch-codex.command'
temporary = base / 'launch-codex.command.new'
# execve accepts argument arrays; shell wrapper uses strict single-quote escaping.
quote = lambda s: "'" + str(s).replace("'", "'\"'\"'") + "'"
temporary.write_text('#!/bin/sh\nset -eu\nexec ' + quote(sys.executable) + ' ' + quote(release / 'launch_desktop.py') + ' --workspace ' + quote(Path.home() / 'workspace') + ' --existing-profile\n')
temporary.chmod(0o700)
os.replace(temporary, wrapper)
print('Installed runtime update. Codex was not restarted. Relaunch when active chats are idle.')
