"""Human UI capability is separate from the agent session capability."""
import json
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler


def approval_handler(broker, human_token, port):
    origin = f'http://127.0.0.1:{port}'
    class Handler(BaseHTTPRequestHandler):
        def reply(self, payload, status=200, content_type='application/json'):
            body = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            supplied = self.headers.get('Authorization', '').removeprefix('Bearer ')
            return self.headers.get('Host') == f'127.0.0.1:{port}' and secrets.compare_digest(supplied, human_token)

        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                return self.reply({'error': 'Invalid host'}, 403)
            assets = {'/': ('approval.html', 'text/html; charset=utf-8'), '/approval.js': ('approval.js', 'text/javascript; charset=utf-8'), '/approval.css': ('approval.css', 'text/css; charset=utf-8')}
            if self.path in assets:
                name, kind = assets[self.path]
                return self.reply(Path(__file__).with_name(name).read_text(), content_type=kind)
            if self.path == '/state' and self.authorized():
                return self.reply(broker.snapshot())
            self.reply({'error': 'Human approval credential required'}, 403)

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2048:
                    raise ValueError('Invalid request size')
                raw = self.rfile.read(size)
            except ValueError:
                return self.reply({'error': 'Invalid request size'}, 400)
            if not self.authorized() or self.headers.get('Origin') != origin or self.path != '/action':
                return self.reply({'error': 'Human approval credential and local origin required'}, 403)
            try:
                data = json.loads(raw)
                actions = {'approve': broker.approve, 'deny': broker.deny, 'revoke': broker.revoke, 'extend': broker.extend, 'request': lambda _: broker.request(broker.token, data.get('folder'))}
                result = actions[data['action']](data['id'])
                self.reply({'result': result, **broker.snapshot()})
            except (ValueError, KeyError, TypeError):
                self.reply({'error': 'Request unavailable or another authentication is in progress'}, 400)

        def log_message(self, *args):
            pass  # Never log URLs, credentials, or bodies.
    return Handler
