import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from approval_ui import approval_handler
from file_broker import FileBroker


class ApprovalUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / 'dummy.txt').write_text('dummy')
        self.now = 0
        self.auth_calls = []
        # HTTP tests use a known fixture descriptor. Full ancestor/symlink
        # opening tests run separately in test_file_broker from normal Terminal.
        with patch('file_broker.open_root', lambda root: os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)):
            self.broker = FileBroker(self.root, lambda reason: self.auth_calls.append(reason) or True, lambda: self.now)
        self.key = self.broker.request(self.broker.token)['id']
        self.human = 'separate-human-capability'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), approval_handler(self.broker, self.human, 0))
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = approval_handler(self.broker, self.human, self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.broker.close(); self.temp.cleanup()

    def call(self, path='/state', token=None, body=None, origin=None):
        headers = {'Authorization': 'Bearer ' + (token or '')}
        if origin: headers['Origin'] = origin
        req = urllib.request.Request(self.origin + path, headers=headers, data=json.dumps(body).encode() if body else None)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def action(self, name, token=None, origin=None):
        return self.call('/action', token or self.human, {'action': name, 'id': self.key}, origin or self.origin)

    def test_agent_cannot_view_or_approve(self):
        for token in (None, 'forged', self.broker.token):
            self.assertEqual(self.call(token=token)[0], 403)
            self.assertEqual(self.call('/action', token, {'action': 'approve', 'id': self.key}, self.origin)[0], 403)
        self.assertEqual(self.auth_calls, [])
        self.assertEqual(self.broker.requests[self.key]['status'], 'pending')

    def test_human_selects_multiple_roots_and_extension(self):
        second = self.root / 'second'
        second.mkdir()
        (second / 'example.txt').write_text('example')
        body = {'action': 'request', 'id': '', 'folder': str(second)}
        self.assertEqual(self.call('/action', self.broker.token, body, self.origin)[0], 403)
        code, raw, _ = self.call('/action', self.human, body, self.origin)
        self.assertEqual(code, 200)
        key = json.loads(raw)['result']['id']
        self.assertEqual(self.call('/action', self.human, {'action': 'approve', 'id': key}, self.origin)[0], 200)
        self.now = 500
        self.assertEqual(self.call('/action', self.human, {'action': 'extend', 'id': key}, self.origin)[0], 200)
        self.assertEqual(self.broker.status(self.broker.token, key)['remaining'], 600)
        self.assertEqual(len(self.auth_calls), 2)
        self.assertEqual(self.broker.access(self.broker.token, key, 'read', 'example.txt'), 'example')
        self.assertEqual(self.broker.status(self.broker.token, self.key)['status'], 'pending')
        for folder in ('/', str(Path.home()), str(Path(__file__).resolve().parents[1])):
            self.assertEqual(self.call('/action', self.human, {'action': 'request', 'id': '', 'folder': folder}, self.origin)[0], 400)

    def test_origin_required_and_cross_site_denied(self):
        body = {'action': 'approve', 'id': self.key}
        for origin in (None, 'https://example.org'):
            self.assertEqual(self.call('/action', self.human, body, origin)[0], 403)
        self.assertEqual(self.auth_calls, [])

    def test_approval_countdown_activity_and_revoke(self):
        self.assertEqual(self.action('approve')[0], 200)
        self.assertEqual(len(self.auth_calls), 1)
        self.assertIn(str(self.root), self.auth_calls[0])
        self.assertIn(self.broker.session, self.auth_calls[0])
        self.now = 90
        state = json.loads(self.call(token=self.human)[1])
        self.assertEqual(state['requests'][0]['remaining'], 510)
        self.assertNotIn(self.broker.token, json.dumps(state))
        self.assertEqual(self.broker.access(self.broker.token, self.key, 'read', 'dummy.txt'), 'dummy')
        self.assertEqual(self.action('revoke')[0], 200)
        with self.assertRaises(ValueError): self.broker.access(self.broker.token, self.key, 'read', 'dummy.txt')
        events = self.broker.snapshot()['events']
        self.assertEqual(events[0]['action'], 'revoked')
        self.assertNotIn('dummy', json.dumps(events))

    def test_denial_and_failed_authentication(self):
        self.assertEqual(self.action('deny')[0], 200)
        self.assertEqual(self.broker.requests[self.key]['status'], 'denied')
        self.key = self.broker.request(self.broker.token)['id']
        self.broker.authenticate = lambda _: False
        self.assertEqual(self.action('approve')[0], 200)
        self.assertEqual(self.broker.requests[self.key]['status'], 'denied')

    def test_expiry_in_state_and_access(self):
        self.action('approve')
        self.now = 600
        state = json.loads(self.call(token=self.human)[1])
        self.assertEqual(state['requests'][0]['status'], 'expired')
        self.assertEqual(state['requests'][0]['remaining'], 0)
        self.assertEqual(state['events'][0]['action'], 'expired')
        with self.assertRaises(ValueError): self.broker.access(self.broker.token, self.key, 'list')

    def test_static_page_contains_no_credentials_and_has_csp(self):
        status, body, headers = self.call('/')
        self.assertEqual(status, 200)
        self.assertNotIn(self.human.encode(), body)
        self.assertNotIn(self.broker.token.encode(), body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_wrong_host_rejected(self):
        req = urllib.request.Request(self.origin + '/state', headers={'Host': 'evil.example', 'Authorization': 'Bearer ' + self.human})
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(req, timeout=5)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()


if __name__ == '__main__': unittest.main()
