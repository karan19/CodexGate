import os
from pathlib import Path
import tempfile
import unittest
from file_broker import FileBroker


class FileBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'approved'
        self.root.mkdir()
        (self.root / 'dummy.txt').write_text('dummy')
        (self.base / 'outside.txt').write_text('outside')
        self.now = 0
        self.broker = FileBroker(self.root, lambda _: True, lambda: self.now)
        self.token = self.broker.token
        self.key = self.broker.request(self.token)['id']

    def tearDown(self):
        self.broker.close()
        self.temp.cleanup()

    def read(self, path='dummy.txt', token=None):
        return self.broker.access(token or self.token, self.key, 'read', path)

    def test_approval_expiry_and_revocation(self):
        with self.assertRaises(ValueError): self.read()
        self.broker.approve(self.key)
        self.assertEqual(self.read(), 'dummy')
        self.assertEqual(self.broker.access(self.token, self.key, 'list')[0]['name'], 'dummy.txt')
        self.now = 600
        with self.assertRaises(ValueError): self.read()
        key = self.broker.request(self.token)['id']
        self.broker.approve(key)
        self.broker.revoke(key)
        with self.assertRaises(ValueError): self.broker.access(self.token, key, 'read', 'dummy.txt')

    def test_extension_reauthenticates_and_resets_expiry(self):
        self.broker.approve(self.key)
        self.now = 500
        calls = []
        self.broker.authenticate = lambda prompt: calls.append(prompt) or True
        self.broker.extend(self.key)
        self.assertEqual(len(calls), 1)
        self.now = 601
        self.assertEqual(self.read(), 'dummy')
        self.now = 1100
        with self.assertRaises(ValueError): self.broker.extend(self.key)
        with self.assertRaises(ValueError): self.read()

    def test_extension_failure_and_revocation_fail_closed(self):
        self.broker.approve(self.key)
        self.broker.authenticate = lambda _: False
        self.assertEqual(self.broker.extend(self.key), 'denied')
        with self.assertRaises(ValueError): self.read()
        key = self.broker.request(self.token)['id']
        self.broker.authenticate = lambda _: True
        self.broker.approve(key)
        def cancel(_):
            self.broker.revoke(key)
            return True
        self.broker.authenticate = cancel
        with self.assertRaises(ValueError): self.broker.extend(key)
        self.assertEqual(self.broker.status(self.token, key)['status'], 'revoked')

    def test_multiple_roots_are_independent_and_pinned(self):
        second = self.base / 'second'
        second.mkdir()
        (second / 'dummy.txt').write_text('second')
        other = self.broker.request(self.token, str(second))['id']
        self.broker.approve(self.key)
        self.broker.approve(other)
        self.assertEqual(self.read(), 'dummy')
        self.assertEqual(self.broker.access(self.token, other, 'read', 'dummy.txt'), 'second')
        second.rename(self.base / 'moved')
        second.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.broker.access(self.token, other, 'read', 'dummy.txt'), 'second')
        self.broker.revoke(other)
        self.assertEqual(self.read(), 'dummy')
        with self.assertRaises(ValueError): self.broker.access(self.token, other, 'list')

    def test_forged_session_and_restart(self):
        self.broker.approve(self.key)
        with self.assertRaises(ValueError): self.read(token='forged')
        other = FileBroker(self.root, lambda _: True)
        try:
            with self.assertRaises(ValueError): other.status(self.token, self.key)
        finally: other.close()

    def test_authentication_fail_closed(self):
        self.broker.authenticate = lambda _: False
        self.assertEqual(self.broker.approve(self.key), 'denied')
        with self.assertRaises(ValueError): self.read()

    def test_auth_exception_and_cancellation(self):
        def fail(_): raise RuntimeError('unavailable')
        self.broker.authenticate = fail
        self.assertEqual(self.broker.approve(self.key), 'denied')
        key = self.broker.request(self.token)['id']
        def cancel(_):
            self.broker.revoke(key)
            return True
        self.broker.authenticate = cancel
        with self.assertRaises(ValueError): self.broker.approve(key)

    def test_escape_symlink_and_hardlink(self):
        self.broker.approve(self.key)
        (self.root / 'link').symlink_to(self.base / 'outside.txt')
        (self.root / 'directory-link').symlink_to(self.base, target_is_directory=True)
        os.link(self.base / 'outside.txt', self.root / 'hardlink')
        for path in ('../outside.txt', str(self.base / 'outside.txt'), 'link', 'directory-link/outside.txt', 'hardlink'):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)): self.read(path)

    def test_root_replacement_cannot_redirect(self):
        self.broker.approve(self.key)
        self.root.rename(self.base / 'original')
        self.root.symlink_to(self.base, target_is_directory=True)
        self.assertEqual(self.read(), 'dummy')

    def test_special_files_and_size_limit(self):
        self.broker.approve(self.key)
        os.mkfifo(self.root / 'pipe')
        (self.root / 'large').write_bytes(b'x' * 262145)
        for path in ('pipe', 'large', '.'):
            with self.subTest(path=path), self.assertRaises(ValueError): self.read(path)

    def test_symlink_root_rejected(self):
        link = self.base / 'alias'
        link.symlink_to(self.root)
        with self.assertRaises(OSError): FileBroker(link, lambda _: True)


if __name__ == '__main__': unittest.main()
