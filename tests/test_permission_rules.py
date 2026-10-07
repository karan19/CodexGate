import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from launch_desktop import desktop_policy
from managed_launch import validate_config


class PermissionRuleTests(unittest.TestCase):
    def test_reject_control_exposure_and_invalid_access(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            control = root / 'controller'; control.mkdir()
            workspace = root / 'workspace'; workspace.mkdir()
            config = {'workspace': str(workspace), 'folders': [{'path': str(root), 'access': 'read'}]}
            with self.assertRaises(ValueError):
                validate_config(config, control)
            config['folders'] = [{'path': str(workspace), 'access': 'execute'}]
            with self.assertRaises(ValueError):
                validate_config(config, control)
            config['folders'] = []
            self.assertEqual(validate_config(config, control)[0], workspace.resolve())

    def test_actual_read_only_write_and_outside_boundary(self):
        # Fixtures in the home tree exercise the policy's protected /Users root.
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as root:
            root = Path(root).resolve()
            workspace, runtime, read, write, outside = [root / name for name in ('workspace', 'runtime', 'read', 'write', 'outside')]
            for path in (workspace, runtime, read, write, outside):
                path.mkdir(); (path / 'dummy').write_text('dummy')
            policy = desktop_policy(workspace, runtime, Path('/Applications/ChatGPT.app'), profile_paths=(write,), read_paths=(read,))
            for path, can_read, can_write in ((workspace, True, True), (read, True, False), (write, True, True), (outside, False, False)):
                literal = json.dumps(str(path))
                code = f'from pathlib import Path; p=Path({literal}); '
                r = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/opt/homebrew/bin/python3', '-c', code + '(p/"dummy").read_text()'], cwd=workspace, capture_output=True)
                w = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/opt/homebrew/bin/python3', '-c', code + '(p/"created").write_text("dummy")'], cwd=workspace, capture_output=True)
                self.assertEqual(r.returncode == 0, can_read, r.stderr.decode())
                self.assertEqual(w.returncode == 0, can_write, w.stderr.decode())
