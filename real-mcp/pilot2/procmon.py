"""Kernel process events (netlink proc connector) for a server's process tree.

Sampling /proc every few milliseconds misses children that live for 3 ms, which
is what `bash -c "echo hello"` takes.  The proc connector delivers every fork,
exec and exit from the kernel, so the harness records each child the server
spawned during a call, with its command line read at exec time.  Needs
CAP_NET_ADMIN (root in the sandbox container); the harness falls back to
sampling when it is unavailable and says so in the receipt.
"""
from __future__ import annotations

import os
import socket
import struct
import threading
import time

NETLINK_CONNECTOR = 11
CN_IDX_PROC = 1
CN_VAL_PROC = 1
PROC_CN_MCAST_LISTEN = 1
PROC_EVENT_FORK = 0x1
PROC_EVENT_EXEC = 0x2
PROC_EVENT_EXIT = 0x80000000


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
        return raw.replace(b"\0", b" ").decode(errors="replace").strip() or "<empty>"
    except OSError:
        return "<exited before cmdline could be read>"


class ProcEventMonitor(threading.Thread):
    """Track descendants of `root_pid`; record forks/execs between begin() and end()."""

    def __init__(self, root_pid: int):
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.tree = {root_pid}
        self.lock = threading.Lock()
        self.events: list[dict] = []
        self.recording = False
        self._stop = threading.Event()
        self.sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_CONNECTOR)
        self.sock.bind((os.getpid(), CN_IDX_PROC))
        data = struct.pack("=I", PROC_CN_MCAST_LISTEN)
        cn = struct.pack("=IIIIHH", CN_IDX_PROC, CN_VAL_PROC, 0, 0, len(data), 0) + data
        nl = struct.pack("=IHHII", 16 + len(cn), 3, 0, 0, os.getpid()) + cn
        self.sock.sendto(nl, (0, 0))
        self.sock.settimeout(0.2)

    def run(self):
        while not self._stop.is_set():
            try:
                msg = self.sock.recv(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            self._parse(msg)

    def _parse(self, msg: bytes):
        off = 0
        while off + 16 <= len(msg):
            nl_len, nl_type = struct.unpack_from("=IH", msg, off)
            if nl_len < 16:
                break
            body = msg[off + 16: off + nl_len]
            off += (nl_len + 3) & ~3
            if len(body) < 20 + 16:
                continue
            # cn_msg: idx val seq ack len flags (20 bytes), then proc_event
            ev = body[20:]
            what, _cpu, _ts = struct.unpack_from("=IIQ", ev, 0)
            payload = ev[16:]
            now = time.time()
            with self.lock:
                if what == PROC_EVENT_FORK and len(payload) >= 16:
                    ppid, ptgid, cpid, ctgid = struct.unpack_from("=IIII", payload, 0)
                    if ptgid in self.tree or ppid in self.tree:
                        self.tree.add(ctgid)
                        if self.recording:
                            self.events.append({"t": now, "event": "fork", "pid": ctgid, "parent": ptgid})
                elif what == PROC_EVENT_EXEC and len(payload) >= 8:
                    pid, tgid = struct.unpack_from("=II", payload, 0)
                    if tgid in self.tree and tgid != self.root_pid and self.recording:
                        self.events.append({"t": now, "event": "exec", "pid": tgid, "cmdline": _cmdline(tgid)})
                elif what == PROC_EVENT_EXIT and len(payload) >= 8:
                    pid, tgid = struct.unpack_from("=II", payload, 0)
                    if tgid in self.tree and tgid != self.root_pid:
                        self.tree.discard(tgid)
                        if self.recording:
                            self.events.append({"t": now, "event": "exit", "pid": tgid})

    def begin(self):
        with self.lock:
            self.events = []
            self.recording = True

    def end(self, settle: float = 0.05) -> dict:
        time.sleep(settle)
        with self.lock:
            self.recording = False
            events = list(self.events)
        forks = [e for e in events if e["event"] == "fork"]
        execs = [e for e in events if e["event"] == "exec"]
        return {"forks": len(forks), "execs": [e["cmdline"] for e in execs], "events": events}

    def close(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
