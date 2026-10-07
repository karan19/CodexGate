import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from deployment import FILES, verify

class DeploymentTests(unittest.TestCase):
    def test_modified_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = {}
            for name in FILES:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'dummy')
                entries[name] = hashlib.sha256(b'dummy').hexdigest()
            (root / 'manifest.json').write_text(json.dumps({'files': entries}))
            self.assertEqual(verify(root), root.resolve())
            (root / 'app.py').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify(root)
    def test_extra_file_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'manifest.json').write_text(json.dumps({'files': {'../other': 'x'}}))
            with self.assertRaises(ValueError): verify(root)
