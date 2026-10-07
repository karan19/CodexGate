from pathlib import Path
import platform
import os
import re
import subprocess
import sys
import tempfile
import unittest
from launch_desktop import desktop_policy
from sandbox_launcher import PROJECT

@unittest.skipUnless(platform.system() == 'Darwin', 'macOS required')
class RuntimeExceptionTests(unittest.TestCase):
    def test_process_snapshot_command(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.local') as temp:
            root = Path(temp).resolve()
            workspace, runtime = root / 'workspace', root / 'runtime'
            workspace.mkdir(); runtime.mkdir()
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'))
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/bin/ps', '-p', str(os.getpid()), '-o', 'pid='], cwd=workspace, capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
    def test_regex_preserves_path_escaping(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.local') as temp:
            root = Path(temp).resolve()
            workspace, runtime = root / 'workspace', root / 'runtime'
            workspace.mkdir(); runtime.mkdir()
            pattern = '^' + re.escape(str(root / 'cache.with.dots')) + '/xcrun_db-[A-Za-z0-9]+$'
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), cache_regex=pattern)
            self.assertIn('(regex #"' + pattern + '")', policy)
            self.assertNotIn('\\\\.', policy)
    def test_pipe_and_cache_scope(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.local') as temp:
            root = Path(temp).resolve()
            workspace, runtime, pipes, caches, private = (root / n for n in ('workspace', 'runtime', 'pipes', 'caches', 'private'))
            for d in (workspace, runtime, pipes, caches, private): d.mkdir()
            (private / 'dummy.txt').write_text('dummy')
            pattern = '^' + re.escape(str(caches)) + '/xcrun_db(-[A-Za-z0-9]+)?$'
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), runtime_paths=(pipes,), cache_regex=pattern)
            code = "import pathlib,socket,sys; p=pathlib.Path(sys.argv[1]); s=socket.socket(socket.AF_UNIX); s.bind(str(p/'test.sock')); s.close(); c=pathlib.Path(sys.argv[2])/'xcrun_db-Test123'; c.write_text('dummy'); c.chmod(0o600); c=c.replace(c.with_name('xcrun_db')); assert c.read_text()=='dummy'"
            # A short socket path avoids sockaddr_un's path-length limit in fixture roots.
            # Binding through a relative path still exercises the sandbox's resolved path.
            code = code.replace("str(p/'test.sock')", "'test.sock'")
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-c', code, str(pipes), str(caches)], cwd=pipes, capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            for path in (caches / 'unrelated.txt', caches / 'xcrun_db-private.txt', private / 'new.txt'):
                r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/bin/sh', '-c', 'printf dummy > "$1"', 'probe', str(path)], capture_output=True, timeout=10)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(path.exists())
            r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/bin/cat', str(private / 'dummy.txt')], capture_output=True, timeout=10)
            self.assertNotEqual(r.returncode, 0)
