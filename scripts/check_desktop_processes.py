"""Read-only runtime check; no file contents, arguments, or environment collected."""
import ctypes
import json
import os

proc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
proc.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
proc.proc_listallpids.restype = ctypes.c_int
proc.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
proc.proc_pidpath.restype = ctypes.c_int
sandbox = ctypes.CDLL('/usr/lib/libsandbox.dylib', use_errno=True)
sandbox.sandbox_check.restype = ctypes.c_int

def presence(pid):
    ctypes.set_errno(0)
    value = sandbox.sandbox_check(ctypes.c_int(pid), ctypes.c_void_p(0), ctypes.c_int(0))
    return {'raw': value, 'errno': ctypes.get_errno(), 'sandboxed': True if value == 1 else False if value == 0 else None}

count = proc.proc_listallpids(None, 0)
if count <= 0:
    raise SystemExit('Process inventory unavailable; protection unverified')
pids = (ctypes.c_int * (count + 1024))()
number = proc.proc_listallpids(pids, ctypes.sizeof(pids))
if number <= 0:
    raise SystemExit('Process inventory unavailable; protection unverified')
results = []
for pid in pids[:number]:
    path = ctypes.create_string_buffer(4096)
    if proc.proc_pidpath(pid, path, len(path)) <= 0:
        continue
    executable = path.value.decode(errors='replace')
    if executable in ('/Applications/ChatGPT.app/Contents/MacOS/ChatGPT', '/Applications/Codex.app/Contents/MacOS/Codex') or ('/Contents/Resources/codex-cli/' in executable and executable.endswith('/codex')):
        results.append({'pid': pid, 'executable': executable, **presence(pid)})
print(json.dumps({'checker': {'pid': os.getpid(), **presence(os.getpid())}, 'desktop_processes': results, 'all_detected_processes_sandboxed': bool(results) and all(row['sandboxed'] is True for row in results), 'scope': 'Sandbox presence only; dummy boundary tests are still required.'}, indent=2))
