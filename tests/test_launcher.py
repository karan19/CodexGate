import platform
import subprocess
import tempfile
import unittest
from pathlib import Path
from sandbox_launcher import PROJECT, command_for, policy_for, validate_workspace

class PolicyTests(unittest.TestCase):
    def test_broker_parent_rejected(self):
        for directory in (PROJECT, PROJECT.parent, Path.home(), Path('/')):
            with self.assertRaises(ValueError): validate_workspace(directory)
    def test_missing_rejected(self):
        with self.assertRaises(OSError): validate_workspace(PROJECT / 'nonexistent-folder-for-test')
    def test_command_required(self):
        with tempfile.TemporaryDirectory(dir=PROJECT) as root:
            with self.assertRaises(ValueError): command_for(root, [])

@unittest.skipUnless(platform.system() == 'Darwin', 'macOS sandbox required')
class SandboxTests(unittest.TestCase):
    def test_process_and_child_are_confined(self):
        base = PROJECT / '.local'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            root = Path(temporary).resolve()
            workspace, private = root / 'workspace', root / 'private'
            workspace.mkdir(); private.mkdir()
            (workspace / 'allowed.txt').write_text('dummy')
            (private / 'secret.txt').write_text('dummy')
            (workspace / 'escape').symlink_to(private, target_is_directory=True)
            script = '''
/bin/cat "$1/allowed.txt" >/dev/null || exit 11
printf dummy > "$1/output.txt" || exit 12
if /bin/cat "$2/secret.txt" >/dev/null 2>&1; then exit 13; fi
if (printf dummy > "$2/new.txt") 2>/dev/null; then exit 14; fi
if /bin/cat "$1/escape/secret.txt" >/dev/null 2>&1; then exit 15; fi
if /bin/cat "$3/app.py" >/dev/null 2>&1; then exit 16; fi
if /bin/sh -c '/bin/cat "$1/secret.txt" >/dev/null 2>&1' child "$2"; then exit 17; fi
'''
            result = subprocess.run(command_for(workspace, ['/bin/sh', '-c', script, 'probe', str(workspace), str(private), str(PROJECT)]), cwd=workspace, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertFalse((private / 'new.txt').exists())
