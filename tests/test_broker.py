import unittest
from app import Broker
class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.b = Broker(lambda: self.now, authenticate=lambda _: True)
        self.token = self.b.new_session()
        self.b.act('request', session_token=self.token)
        self.id = next(iter(self.b.requests))
    def test_other_session_cannot_read(self):
        other = self.b.new_session()
        self.b.act('approve', self.id)
        with self.assertRaises(ValueError): self.b.act('read', self.id, other)
        self.assertIn('Synthetic', self.b.act('read', self.id, self.token))
    def test_missing_or_forged_session(self):
        for token in (None, 'forged'):
            with self.assertRaises(ValueError): self.b.act('request', session_token=token)
    def test_restart_invalidates_session(self):
        with self.assertRaises(ValueError): Broker().act('request', session_token=self.token)
    def test_auth_failure_blocks(self):
        self.b.authenticate = lambda _: False
        with self.assertRaises(ValueError): self.b.act('approve', self.id)
        with self.assertRaises(ValueError): self.b.act('read', self.id, self.token)
    def test_auth_exception_blocks(self):
        def fail(_): raise RuntimeError('unavailable')
        self.b.authenticate = fail
        with self.assertRaises(ValueError): self.b.act('approve', self.id)
        self.assertEqual(self.b.requests[self.id]['status'], 'denied')
    def test_cancel_during_auth(self):
        def cancelled(_):
            self.b.act('deny', self.id)
            return True
        self.b.authenticate = cancelled
        with self.assertRaises(ValueError): self.b.act('approve', self.id)
        self.assertEqual(self.b.requests[self.id]['status'], 'denied')
    def test_denial(self):
        self.b.act('deny', self.id)
        with self.assertRaises(ValueError): self.b.act('read', self.id, self.token)
    def test_expiry(self):
        self.b.act('approve', self.id)
        self.now = 599
        self.assertIn('Synthetic', self.b.act('read', self.id, self.token))
        self.now = 600
        with self.assertRaises(ValueError): self.b.act('read', self.id, self.token)
        self.assertEqual(self.b.snapshot()['requests'][0]['status'], 'expired')
    def test_revoke(self):
        self.b.act('approve', self.id)
        self.b.act('revoke', self.id)
        with self.assertRaises(ValueError): self.b.act('read', self.id, self.token)
    def test_restart_has_no_grants(self):
        self.b.act('approve', self.id)
        self.assertEqual(Broker().snapshot()['requests'], [])
    def test_no_reapproval(self):
        self.b.act('approve', self.id)
        with self.assertRaises(ValueError): self.b.act('approve', self.id)
if __name__ == '__main__': unittest.main()
