"""Smoke-test the packaged runtime with dummy data and private ephemeral ports."""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import urllib.request

root = Path(__file__).resolve().parents[1]
executable = root / '.build/CodexGate.app/Contents/Resources/backend/codexgate-service'
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]
with tempfile.TemporaryDirectory() as temporary:
    folder = Path(temporary).resolve()
    (folder / 'dummy.txt').write_text('dummy')
    port, human_port = free_port(), free_port()
    process = subprocess.Popen([str(executable), 'broker', '--root', str(folder), '--controller', '--port', str(port), '--ui-port', str(human_port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready = json.loads(process.stdout.readline())
        assert ready['ready']
        request = urllib.request.Request(f'http://127.0.0.1:{port}/request', data=b'{}', headers={'Authorization': 'Bearer ' + ready['agent_token'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.load(response)['result']['status'] == 'pending'
        request = urllib.request.Request(f'http://127.0.0.1:{human_port}/state', headers={'Authorization': 'Bearer ' + ready['human_token']})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert len(json.load(response)['requests']) == 1
        with urllib.request.urlopen(f'http://127.0.0.1:{human_port}/', timeout=5) as response:
            assert b'<!' in response.read()
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        print('PASS: bundled runtime, assets, pending request, human state and EOF shutdown. No grant approved.')
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)
