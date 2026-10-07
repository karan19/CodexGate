import importlib.util
from pathlib import Path
import tempfile
import re
import unittest

spec = importlib.util.spec_from_file_location('trial', Path(__file__).resolve().parents[1] / 'scripts/prepare_computer_use_trial.py')
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


class HelperMatchTests(unittest.TestCase):
    def test_screenshot_filename_scope(self):
        root = '/private/var/folders/dummy/T'
        pattern = trial.screenshot_pattern(Path(root))
        for name in ('Calculator Screenshot 2026-10-04 at 2.36.08 PM.jpeg', '.Calculator Screenshot 2026-10-04 at 2.36.08 PM.jpeg-0Rs8'):
            self.assertIsNotNone(re.fullmatch(pattern, root + '/' + name))
        for name in ('secret.txt', 'other/Calculator Screenshot 2026-10-04 at 2.36.08 PM.jpeg', 'Calculator Screenshot 2026-10-04 at 2.36.08 PM.jpeg/private'):
            self.assertIsNone(re.fullmatch(pattern, root + '/' + name))
        original = '(subpath "/private/tmp/codex-browser-use")\n(subpath "/private/tmp/codex-browser-use")'
        changed = trial.screenshot_policy(original, Path(root))
        self.assertEqual(changed.count('(regex #"' + pattern + '")'), 2)
    def test_socket_exception_is_literal_and_rejects_unknown_layout(self):
        original = '(read (subpath "/private/tmp/codex-browser-use"))\n(write (subpath "/private/tmp/codex-browser-use"))'
        socket = Path('/Users/dummy/Library/Group Containers/service/IPC/computeruse.sock')
        changed = trial.socket_policy(original, socket)
        rule = '(literal "' + str(socket) + '")'
        self.assertEqual(changed.count(rule), 2)
        rules = ' '.join('(literal "' + str(path) + '")' for path in (socket.parent, socket, Path(str(socket) + '.lock')))
        self.assertEqual(changed.replace(' ' + rules, ''), original)
        self.assertNotIn('(subpath "' + str(socket.parent), changed)
        with self.assertRaises(ValueError): trial.socket_policy('(allow default)', socket)
    def test_content_and_links_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left, right = root / 'left', root / 'right'
            left.mkdir(); right.mkdir()
            for path in (left, right):
                (path / 'file').write_text('dummy')
                (path / 'link').symlink_to('file')
            self.assertEqual(trial.tree_digest(left), trial.tree_digest(right))
            (right / 'file').write_text('changed')
            self.assertNotEqual(trial.tree_digest(left), trial.tree_digest(right))
            (right / 'file').write_text('dummy')
            (right / 'link').unlink(); (right / 'link').symlink_to('other')
            self.assertNotEqual(trial.tree_digest(left), trial.tree_digest(right))

    def test_symlink_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'real').mkdir(); (root / 'alias').symlink_to(root / 'real')
            with self.assertRaises(ValueError): trial.tree_digest(root / 'alias')
