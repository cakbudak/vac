"""Observation channels for a tool call on a real, non-clonable server (second slice).

Unchanged from the first slice except: the socket sampler reads the socket table of
the *server's* network namespace (`/proc/<pid>/net/*`), and the logging proxy can
bind to the harness side of the server's veth instead of 127.0.0.1.

  fs        a before/after snapshot of watched directories (content hash,
            size, mode, symlink target) -- "everything the tool was observed
            to touch" instead of "the whole environment"
  procs     child processes the server spawned during the call (kernel process
            events when available, else sampled from /proc)
  sockets   TCP/UDP sockets held by the server's process tree during the call
            (sampled) -- remote endpoints only
  proxy     every HTTP(S) request or CONNECT the server sent to the proxy named
            in HTTP_PROXY/HTTPS_PROXY/ALL_PROXY; the proxy logs and REFUSES
  net       (harness.py) every packet the server's namespace emitted, from tcpdump
  response  the tool's own result text and isError flag
"""
from __future__ import annotations

import hashlib
import http.server
import os
import socket
import socketserver
import stat
import threading
import time
from pathlib import Path


# --------------------------------------------------------------------------
# filesystem snapshots
# --------------------------------------------------------------------------

def _file_entry(p: Path) -> dict:
    st = p.lstat()
    if stat.S_ISLNK(st.st_mode):
        return {"type": "symlink", "target": os.readlink(p)}
    if stat.S_ISDIR(st.st_mode):
        return {"type": "dir", "mode": oct(st.st_mode & 0o777)}
    if stat.S_ISREG(st.st_mode):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return {"type": "file", "sha256": h.hexdigest(), "size": st.st_size, "mode": oct(st.st_mode & 0o777)}
    return {"type": "other"}


def snapshot(roots: list[str], exclude: tuple[str, ...] = ()) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        out[str(rp)] = _file_entry(rp)
        for dirpath, dirnames, filenames in os.walk(rp):
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                sp = str(p)
                if any(sp.startswith(e) for e in exclude):
                    continue
                try:
                    out[sp] = _file_entry(p)
                except (FileNotFoundError, PermissionError):
                    out[sp] = {"type": "vanished"}
    return out


def diff(before: dict[str, dict], after: dict[str, dict]) -> dict[str, list[str]]:
    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    return {"created": created, "deleted": deleted, "modified": modified}


# --------------------------------------------------------------------------
# process-tree sampler: children and sockets of the server during a call
# --------------------------------------------------------------------------

def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return ""


def _descendants(pid: int) -> list[int]:
    out, stack = [], [pid]
    while stack:
        p = stack.pop()
        task_dir = f"/proc/{p}/task"
        try:
            tids = os.listdir(task_dir)
        except (FileNotFoundError, PermissionError):
            continue
        for tid in tids:
            for child in _read(f"{task_dir}/{tid}/children").split():
                c = int(child)
                out.append(c)
                stack.append(c)
    return out


def _socket_table(pid: int) -> dict[str, tuple[str, str, str]]:
    """inode -> (proto, local, remote) for every TCP/UDP socket in the namespace of `pid`."""
    table = {}
    for proto, fname in (("tcp", f"/proc/{pid}/net/tcp"), ("tcp6", f"/proc/{pid}/net/tcp6"),
                         ("udp", f"/proc/{pid}/net/udp"), ("udp6", f"/proc/{pid}/net/udp6")):
        for line in _read(fname).splitlines()[1:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            table[parts[9]] = (proto, _addr(parts[1], proto), _addr(parts[2], proto))
    return table


def _addr(hexaddr: str, proto: str) -> str:
    host, port = hexaddr.split(":")
    port_n = int(port, 16)
    if proto.endswith("6"):
        words = [host[i:i + 8] for i in range(0, 32, 8)]
        b = b"".join(bytes.fromhex(w)[::-1] for w in words)
        try:
            ip = socket.inet_ntop(socket.AF_INET6, b)
        except (ValueError, OSError):
            ip = host
    else:
        b = bytes.fromhex(host)[::-1]
        ip = socket.inet_ntop(socket.AF_INET, b)
    return f"{ip}:{port_n}"


def _sockets_of(pids: list[int], table: dict) -> set[tuple]:
    found = set()
    for p in pids:
        try:
            fds = os.listdir(f"/proc/{p}/fd")
        except (FileNotFoundError, PermissionError):
            continue
        for fd in fds:
            try:
                link = os.readlink(f"/proc/{p}/fd/{fd}")
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            if link.startswith("socket:["):
                inode = link[8:-1]
                if inode in table:
                    proto, local, remote = table[inode]
                    if remote not in ("0.0.0.0:0", ":::0", "[::]:0"):
                        found.add((p, proto, remote))
    return found


class ProcSampler(threading.Thread):
    """Sample children and sockets of a process tree until stopped."""

    def __init__(self, root_pid: int, interval: float = 0.01):
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.interval = interval
        self._stop = threading.Event()
        self.children: dict[int, str] = {}      # pid -> cmdline
        self.sockets: set[tuple] = set()        # (pid, proto, remote)
        self.samples = 0

    def run(self):
        while not self._stop.is_set():
            self.samples += 1
            pids = [self.root_pid] + _descendants(self.root_pid)
            for c in pids[1:]:
                if c not in self.children:
                    cmd = _read(f"/proc/{c}/cmdline").replace("\0", " ").strip()
                    self.children[c] = cmd or "<unreadable>"
            table = _socket_table(self.root_pid)
            self.sockets |= _sockets_of(pids, table)
            time.sleep(self.interval)

    def stop(self) -> dict:
        self._stop.set()
        self.join(timeout=2)
        return {"children": sorted(self.children.values()),
                "remote_sockets": sorted({f"{proto} {remote}" for _, proto, remote in self.sockets}),
                "samples": self.samples}


# --------------------------------------------------------------------------
# logging, refusing HTTP proxy
# --------------------------------------------------------------------------

class _ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _log(self):
        self.server.entries.append({"t": time.time(), "method": self.command,
                                    "target": self.path, "host": self.headers.get("Host")})

    def do_CONNECT(self):   # TLS tunnel request: refuse, never connect onward
        self._log()
        self.send_response(403, "Forbidden by probe sandbox")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _plain(self):
        self._log()
        body = b'{"error":"probe sandbox: outbound network is refused and logged"}'
        self.send_response(403, "Forbidden by probe sandbox")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = do_OPTIONS = _plain

    def log_message(self, *a):  # silence
        pass


class LoggingProxy:
    def __init__(self, host: str = "127.0.0.1"):
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer((host, 0), _ProxyHandler, bind_and_activate=True)
        self.httpd.daemon_threads = True
        self.httpd.entries = []
        self.host = host
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        self._cursor = 0

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def drain(self) -> list[dict]:
        entries = self.httpd.entries[self._cursor:]
        self._cursor = len(self.httpd.entries)
        return [dict(e) for e in entries]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
