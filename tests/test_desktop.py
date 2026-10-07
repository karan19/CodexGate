import platform
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from launch_desktop import desktop_policy, find_app, existing_profile_paths
from sandbox_launcher import PROJECT

@unittest.skipUnless(platform.system() == 'Darwin', 'macOS required')
class DesktopPolicyTests(unittest.TestCase):
    def test_workspace_may_contain_source(self):
        from launch_desktop import validate_workspace
        self.assertEqual(validate_workspace(PROJECT.parent), PROJECT.parent)
    def test_short_chromium_socket_directory(self):
        socket_temp = Path.home() / 'Library/Caches/CodexGate/tmp'
        socket_temp.mkdir(parents=True, exist_ok=True)
        base = PROJECT / '.local'
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            root = Path(temporary).resolve()
            workspace, runtime = root / 'workspace', root / 'runtime'
            workspace.mkdir(); runtime.mkdir()
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), socket_temp)
            code = "import socket,tempfile,sys; d=tempfile.TemporaryDirectory(prefix='.com.openai.codex.',dir=sys.argv[1]); s=socket.socket(socket.AF_UNIX); s.bind(d.name+'/SingletonSocket'); s.listen(1); s.close(); d.cleanup()"
            result = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-c', code, str(socket_temp)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
    def test_existing_profile_exception_is_scoped(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.local') as temp:
            root = Path(temp).resolve()
            workspace, runtime, home = root / 'workspace', root / 'runtime', root / 'home'
            for d in (workspace, runtime, home): d.mkdir()
            profile = home / '.codex'; profile.mkdir()
            (profile / 'dummy.txt').write_text('dummy')
            private = home / 'private'; private.mkdir(mode=0o700); (private / 'dummy.txt').write_text('dummy')
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), profile_paths=existing_profile_paths(home))
            script = '/bin/cat "$1/dummy.txt" >/dev/null || exit 11; printf dummy > "$1/write.txt" || exit 12; /bin/chmod 755 "$1" || exit 14; if /bin/cat "$2/dummy.txt" >/dev/null 2>&1; then exit 13; fi; if /bin/chmod 755 "$2" 2>/dev/null; then exit 15; fi'
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/bin/sh', '-c', script, 'probe', str(profile), str(private)], cwd=workspace, capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
    def test_profile_symlink_rejected(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.local') as temp:
            root = Path(temp).resolve(); workspace = root / 'workspace'; workspace.mkdir()
            runtime = root / 'runtime'; runtime.mkdir()
            alias = root / 'alias'; alias.symlink_to(workspace, target_is_directory=True)
            with self.assertRaises(ValueError): desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), profile_paths=(alias,))
    def test_installed_app(self):
        app, executable = find_app()
        self.assertTrue(executable.is_relative_to(app))
    def test_filesystem_exceptions_and_protection(self):
        base = PROJECT / '.local'; base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            root = Path(temporary).resolve()
            workspace, runtime, protected = (root / n for n in ('workspace', 'runtime', 'protected'))
            for directory in (workspace, runtime, protected):
                directory.mkdir(); (directory / 'dummy.txt').write_text('dummy')
            private = workspace / '.local'; private.mkdir(); (private / 'dummy.txt').write_text('dummy')
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'))
            script = '''
/bin/cat "$1/dummy.txt" >/dev/null || exit 11
printf dummy > "$1/new.txt" || exit 12
/bin/cat "$2/dummy.txt" >/dev/null || exit 13
printf dummy > "$2/new.txt" || exit 14
if /bin/cat "$3/dummy.txt" >/dev/null 2>&1; then exit 15; fi
if /bin/cat "$1/.local/dummy.txt" >/dev/null 2>&1; then :; else exit 16; fi
if (: >> "$1/.local/dummy.txt") 2>/dev/null; then :; else exit 17; fi

'''
            result = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/bin/sh', '-c', script, 'probe', str(workspace), str(runtime), str(protected), str(PROJECT)], cwd=workspace, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
    def test_runtime_overlap_rejected(self):
        with tempfile.TemporaryDirectory(dir=PROJECT) as temp:
            with self.assertRaises(ValueError): desktop_policy(temp, temp, Path('/Applications/ChatGPT.app'))
