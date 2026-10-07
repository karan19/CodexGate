"""Synthetic-only permission workflow. No filesystem access API."""
import json
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from isolation import run_probe

def native_authenticate(request_id):
    helper = Path(__file__).parent / '.build' / 'authenticate'
    try:
        result = subprocess.run([str(helper), request_id], timeout=95, capture_output=True)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

class Broker:
    def __init__(self, clock=time.monotonic, authenticate=native_authenticate):
        self.authenticate = authenticate
        self.auth_lock = threading.Lock()
        self.clock = clock
        self.lock = threading.RLock()
        self.sessions = {}
        self.requests = {}
        self.events = []
        self.isolation = {'status': 'not checked', 'checks': [], 'scope': 'No protection verified'}

    def new_session(self):
        with self.lock:
            token = secrets.token_urlsafe(32)
            self.sessions[token] = 'Demo session ' + secrets.token_hex(4)
            return token

    def event(self, action, request):
        self.events.insert(0, {'action': action, 'id': request['id'], 'folder': request['folder'], 'time': time.strftime('%H:%M:%S')})

    def expire(self):
        for request in self.requests.values():
            if request['status'] == 'active' and self.clock() >= request['expires']:
                request['status'] = 'expired'
                self.event('expired', request)

    def act(self, action, request_id=None, session_token=None):
        if action == 'isolation-check':
            result = run_probe()
            with self.lock:
                self.isolation = result
            return
        if action in ('request', 'read'):
            with self.lock:
                if session_token not in self.sessions:
                    raise ValueError('Unknown or expired agent session')
        if action == 'approve':
            if not self.auth_lock.acquire(blocking=False):
                raise ValueError('Another authentication is in progress')
            try:
                with self.lock:
                    request = self.requests.get(request_id)
                    if not request or request['status'] != 'pending':
                        raise ValueError('Request is not pending')
                    request['status'] = 'authenticating'
                    self.event('authentication requested', request)
                try:
                    allowed = self.authenticate(request_id + ' / ' + request['session'])
                except Exception:
                    allowed = False
                with self.lock:
                    if request['status'] != 'authenticating':
                        raise ValueError('Request cancelled during authentication')
                    request['status'] = 'active' if allowed else 'denied'
                    request['expires'] = self.clock() + 600 if allowed else 0
                    self.event('authenticated approval' if allowed else 'authentication denied', request)
                    if not allowed:
                        raise ValueError('Authentication cancelled, failed, or unavailable. Access remains blocked.')
                return
            finally:
                self.auth_lock.release()
        with self.lock:
            self.expire()
            if action == 'request':
                request = {'id': secrets.token_hex(8), 'folder': 'Demo / Contracts', 'session': self.sessions[session_token], 'scope': 'Read and list', 'status': 'pending', 'expires': 0}
                self.requests[request['id']] = request
                self.event('requested', request)
                return
            request = self.requests.get(request_id)
            if not request:
                raise ValueError('Unknown request')
            if action == 'deny' and request['status'] in ('pending', 'authenticating'):
                request['status'] = 'denied'
                request['expires'] = 0
            elif action == 'revoke' and request['status'] == 'active':
                request['status'] = 'revoked'
            elif action == 'read' and request['status'] == 'active':
                if request['session'] != self.sessions[session_token]:
                    self.event('cross-session read blocked', request)
                    raise ValueError('This approval belongs to a different session')
                self.event('synthetic read allowed', request)
                return 'Synthetic contract: example content only.'
            else:
                raise ValueError('Operation blocked in current state')
            self.event(action, request)

    def snapshot(self):
        with self.lock:
            self.expire()
            return {'isolation': self.isolation, 'requests': [{**r, 'remaining': max(0, int(r['expires'] - self.clock())) if r['status'] == 'active' else 0} for r in self.requests.values()], 'events': self.events[:100]}

broker = Broker()
class Handler(BaseHTTPRequestHandler):
    def valid(self):
        host = self.headers.get('Host', '')
        return host in ('127.0.0.1:8771', 'localhost:8771') and self.headers.get('Origin', f'http://{host}') == f'http://{host}'
    def reply(self, data, status=200, kind='application/json'):
        body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if not self.valid():
            return self.reply({'error': 'Local origin required'}, 403)
        if self.path == '/':
            return self.reply(Path(__file__).with_name('index.html').read_text(), kind='text/html; charset=utf-8')
        if self.path == '/api/session':
            return self.reply({'token': broker.new_session()})
        if self.path == '/api/state':
            return self.reply(broker.snapshot())
        self.reply({'error': 'Not found'}, 404)
    def do_POST(self):
        if not self.valid() or self.path != '/api/action' or self.headers.get('X-Demo-Action') != '1':
            return self.reply({'error': 'Rejected'}, 403)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 2048:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(size))
            result = broker.act(payload['action'], payload.get('id'), self.headers.get('X-Agent-Session'))
            self.reply({'result': result, **broker.snapshot()})
        except (ValueError, KeyError, TypeError) as error:
            self.reply({'error': str(error)}, 400)
    def log_message(self, *args):
        pass

if __name__ == '__main__':
    print('Synthetic demo: http://127.0.0.1:8771 — no filesystem protection', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8771), Handler).serve_forever()
