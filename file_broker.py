"""Opt-in read/list broker. Start from normal Terminal, never the agent sandbox.

Approval uses stdin or a separate authenticated human UI, never the agent API.
Use a trusted copy outside workspace before exposing personal files.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def open_root(root):
    # Open every component without following symlinks, including ancestors.
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(root).parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except Exception:
        os.close(fd)
        raise


class FileBroker:
    def __init__(self, root, authenticate, clock=time.monotonic):
        self.root = os.path.abspath(root)
        self.authenticate, self.clock = authenticate, clock
        self.lock = threading.RLock()
        self.auth_lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.session = 'Trial session ' + secrets.token_hex(4)
        self.requests = {}
        self.request_fds = {}
        self.events = []
        self.root_fd = open_root(self.root)

    def close(self):
        os.close(self.root_fd)
        for fd in self.request_fds.values():
            os.close(fd)
        self.request_fds.clear()

    def check_token(self, token):
        if not isinstance(token, str) or not secrets.compare_digest(token, self.token):
            raise ValueError('Invalid session')

    def event(self, action, key):
        self.events.insert(0, {'action': action, 'id': key, 'time': time.strftime('%H:%M:%S')})
        del self.events[100:]

    def request(self, token, folder=None):
        with self.lock:
            self.check_token(token)
            root = self.root if folder is None else os.path.abspath(folder)
            if folder is not None:
                control = os.path.abspath(Path(__file__).parent)
                home = str(Path.home())
                if root in ('/', home) or root == control or control.startswith(root + '/') or root.startswith(control + '/'):
                    raise ValueError('Choose a specific folder outside controller storage')
            fd = open_root(root)
            key = secrets.token_hex(8)
            self.request_fds[key] = fd
            self.requests[key] = {'status': 'pending', 'expires': 0, 'folder': root}
            self.event('requested', key)
            return {'id': key, 'folder': root, 'scope': 'read and list', 'status': 'pending'}

    def status(self, token, key):
        with self.lock:
            self.check_token(token)
            item = self.requests[key]
            if item['status'] == 'active' and self.clock() >= item['expires']:
                item['status'] = 'expired'
                self.event('expired', key)
            return {'id': key, 'folder': item['folder'], 'status': item['status'], 'remaining': max(0, int(item['expires'] - self.clock())) if item['status'] == 'active' else 0}

    def approve(self, key, extending=False):
        if not self.auth_lock.acquire(blocking=False):
            raise ValueError('Another authentication is in progress')
        try:
            return self._approve(key, extending)
        finally:
            self.auth_lock.release()

    def extend(self, key):
        return self.approve(key, extending=True)

    def _approve(self, key, extending=False):
        with self.lock:
            item = self.requests[key]
            if extending:
                if self.status(self.token, key)['status'] != 'active':
                    raise ValueError('Only active grants can be extended')
            elif item['status'] != 'pending':
                raise ValueError('Request is not pending')
            item['status'] = 'authenticating'
            self.event('authentication requested', key)
        try:
            allowed = self.authenticate(f'Allow {self.session} read and list access to {item['folder']} for 10 minutes. Request {key}.')
        except Exception:
            allowed = False
        with self.lock:
            if item['status'] != 'authenticating':
                raise ValueError('Request cancelled')
            item.update(status='active' if allowed else 'denied', expires=self.clock() + 600 if allowed else 0)
            self.event(('extended' if extending else 'approved') if allowed else 'authentication denied', key)
            return item['status']

    def revoke(self, key):
        with self.lock:
            if self.requests[key]['status'] not in ('active', 'pending', 'authenticating'):
                raise ValueError('Request cannot be revoked')
            self.requests[key].update(status='revoked', expires=0)
            self.event('revoked', key)

    def deny(self, key):
        with self.lock:
            if self.requests[key]['status'] not in ('pending', 'authenticating'):
                raise ValueError('Request cannot be denied')
            self.requests[key].update(status='denied', expires=0)
            self.event('denied', key)

    def snapshot(self):
        with self.lock:
            return {'folder': self.root, 'session': self.session, 'scope': 'Read and list',
                    'requests': [self.status(self.token, key) for key in self.requests],
                    'events': list(self.events)}

    def access(self, token, key, action, relative='.'):
        # Serialize revoke/expiry checks with bounded operations.
        with self.lock:
            if self.status(token, key)['status'] != 'active':
                raise ValueError('Access requires an active approval')
            if action not in ('read', 'list'):
                raise ValueError('Only read and list are supported')
            if not isinstance(relative, str) or relative.startswith('/') or '\x00' in relative:
                raise ValueError('A relative path is required')
            parts = relative.split('/')
            if '..' in parts:
                raise ValueError('Parent traversal blocked')
            parts = [p for p in parts if p not in ('', '.')]
            fd = os.dup(self.request_fds[key])
            try:
                for i, part in enumerate(parts):
                    directory = i < len(parts) - 1 or action == 'list'
                    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    if directory:
                        flags |= os.O_DIRECTORY
                    child = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child
                if action == 'list':
                    names = []
                    with os.scandir(fd) as entries:
                        for entry in entries:
                            if len(names) >= 1000:
                                raise ValueError('Directory exceeds 1000 entries; choose a smaller folder')
                            names.append({'name': entry.name, 'directory': entry.is_dir(follow_symlinks=False), 'symlink': entry.is_symlink()})
                    result = sorted(names, key=lambda x: x['name'])
                else:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError('Only regular files with one hard link are supported')
                    if info.st_size > 262144:
                        raise ValueError('File exceeds 256 KiB limit')
                    with os.fdopen(os.dup(fd), 'rb') as stream:
                        data = stream.read(262145)
                    if len(data) > 262144:
                        raise ValueError('File exceeds 256 KiB limit')
                    result = data.decode('utf-8')
                if self.status(token, key)['status'] != 'active':
                    raise ValueError('Approval expired during operation')
                self.event(action + ' allowed', key)
                return result
            finally:
                os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, default=8772)
    parser.add_argument('--ui-port', type=int, default=8773)
    parser.add_argument('--controller', action='store_true', help='Private pipe handshake for the installed menu-bar controller; no interactive Terminal')
    args = parser.parse_args()
    helper = Path(sys.executable).resolve().parents[1] / 'authenticate' if getattr(sys, 'frozen', False) else Path(__file__).parent / '.build/authenticate'
    def authenticate(reason):
        return subprocess.run([str(helper), '--file-access', reason], capture_output=True, timeout=95).returncode == 0
    broker = FileBroker(args.root, authenticate)
    from approval_ui import approval_handler
    human_token = secrets.token_urlsafe(32)
    ui_server = ThreadingHTTPServer(('127.0.0.1', args.ui_port), approval_handler(broker, human_token, args.ui_port))
    ui_server.daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                if self.headers.get('Origin') or self.headers.get('Host') != f'127.0.0.1:{args.port}':
                    raise ValueError('CLI requests to the loopback address only')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('Invalid request size')
                body = json.loads(self.rfile.read(size))
                token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                if self.path == '/request':
                    result = broker.request(token)
                    if not args.controller:
                        print(f"Pending {result['id']}: read/list {broker.root}", flush=True)
                elif self.path == '/status':
                    result = broker.status(token, body['id'])
                elif self.path in ('/read', '/list'):
                    result = broker.access(token, body['id'], self.path[1:], body.get('path', '.'))
                else:
                    raise ValueError('Unknown endpoint; agent API cannot approve')
                status, payload = 200, {'result': result}
            except (ValueError, KeyError, TypeError, OSError):
                status, payload = 403, {'error': 'Request denied or unavailable'}
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=ui_server.serve_forever, daemon=True).start()
    if args.controller:
        print(json.dumps({'ready': True, 'human_token': human_token, 'agent_token': broker.token}), flush=True)
    else:
        print(f'Human approval URL (keep private; open in your own browser): http://127.0.0.1:{args.ui_port}/#{human_token}', flush=True)
        print(f'Broker: http://127.0.0.1:{args.port}\nSession token: {broker.token}\nRoot: {broker.root}\nTerminal commands: approve ID, revoke ID, pending, quit', flush=True)
    try:
        if args.controller:
            # Controller owns stdin. EOF on controller exit ends the service and all grants.
            sys.stdin.read()
            return
        while True:
            words = input('broker> ').split()
            if words == ['quit']:
                break
            try:
                if words == ['pending']:
                    with broker.lock:
                        print(json.dumps(broker.requests, indent=2))
                elif len(words) == 2 and words[0] == 'approve':
                    print(broker.approve(words[1]))
                elif len(words) == 2 and words[0] == 'revoke':
                    broker.revoke(words[1]); print('revoked')
                else:
                    print('Use approve ID, revoke ID, pending, or quit')
            except (ValueError, KeyError):
                print('Request unavailable')
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        server.shutdown()
        server.server_close()
        ui_server.shutdown()
        ui_server.server_close()
        # Process exit closes descriptors; avoid races with in-flight handlers.


if __name__ == '__main__':
    main()
