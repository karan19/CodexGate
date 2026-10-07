"""Exercise the private handshake, capability separation, and controller EOF shutdown."""
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class ControllerServiceTests(unittest.TestCase):
    def test_handshake_auth_and_exit_on_controller_close(self):
        def port():
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                return sock.getsockname()[1]
        agent_port, human_port = port(), port()
        while agent_port == human_port:
            human_port = port()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            # Root walking is covered by FileBroker tests in normal Terminal.
            # Open an authorized fixture directly to test lifecycle in a confined chat.
            code = ('import file_broker,os,sys; '
                    'file_broker.open_root=lambda root:os.open(root,os.O_RDONLY|os.O_DIRECTORY); '
                    'sys.argv=["broker","--controller","--root",sys.argv[1],"--port",sys.argv[2],"--ui-port",sys.argv[3]]; '
                    'file_broker.main()')
            process = subprocess.Popen([sys.executable, '-c', code, folder, str(agent_port), str(human_port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                readable, _, _ = select.select([process.stdout], [], [], 5)
                self.assertTrue(readable, 'No readiness handshake')
                line = process.stdout.readline()
                self.assertTrue(line, 'Service exited before handshake')
                ready = json.loads(line)
                self.assertTrue(ready['ready'])
                self.assertNotEqual(ready['human_token'], ready['agent_token'])
                def state(token):
                    request = Request(f'http://127.0.0.1:{human_port}/state', headers={'Authorization': 'Bearer ' + token})
                    return json.loads(urlopen(request, timeout=3).read())
                self.assertEqual(state(ready['human_token'])['folder'], str(Path(folder).resolve()))
                with self.assertRaises(HTTPError) as error:
                    state(ready['agent_token'])
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
                process.stdin.close()
                self.assertEqual(process.wait(timeout=5), 0)
                self.assertEqual(process.stdout.read(), b'', 'Controller stdout must not include public logs')
            finally:
                if process.poll() is None:
                    process.kill(); process.wait()
                for stream in (process.stdin, process.stdout, process.stderr):
                    if not stream.closed:
                        stream.close()
