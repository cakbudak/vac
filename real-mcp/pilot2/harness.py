"""Probe harness for real MCP servers without state cloning (second slice).

Differences from the first slice (`pilot/harness.py`, frozen):

* **Network isolation with full visibility.**  Each server runs in its own network
  namespace, connected to the harness by one veth pair and nothing else.  The
  harness side (10.200.N.1) runs the logging, refusing proxy and is the server's
  default route and name server; the harness never forwards a packet.  So every
  packet the server's process tree emits either reaches the proxy (logged, refused)
  or dies on the veth, where `tcpdump` records it.  The receipt therefore carries
  *every* outbound attempt -- TCP SYNs and DNS queries with their names -- whether
  or not the server honours proxy variables (Node's `https` module does not).
  Attempts outside any call window (start-up, background timers) are recorded at
  session level.  If the namespace cannot be created (no CAP_NET_ADMIN) the harness
  falls back to the first slice's behaviour and says so in every receipt.
* **Sockets of the server's own namespace.**  The sampler reads `/proc/<pid>/net/*`
  instead of the harness's view.
* **Install digest over relative paths.**  The first slice hashed absolute paths,
  so the same files installed elsewhere got a different digest.
* **Seeds and several sandboxes per run** are handled by `run_pilot.py`.

Everything else -- stdio subprocess in a fresh sandbox (own HOME, TMPDIR, XDG
dirs), before/after content snapshots, kernel process events, the receipt
format -- is unchanged.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from observe import LoggingProxy, ProcSampler, diff, snapshot
from procmon import ProcEventMonitor

HERE = Path(__file__).resolve().parent
PIDWRAP = HERE / "pidwrap.py"
CALL_TIMEOUT = 60.0
SETTLE = 0.05


@dataclass
class Action:
    tool: str
    args: dict
    note: str = ""


@dataclass
class Sandbox:
    root: Path
    home: Path
    tmp: Path
    work: Path
    pidfile: Path
    meta: dict = field(default_factory=dict)


@dataclass
class ServerSpec:
    name: str
    kind: str                      # "reference" | "third_party"
    source: str                    # package@version or repo@commit
    make_sandbox: Callable[[int], Sandbox]
    build_command: Callable[[Sandbox], tuple[list[str], str | None, dict]]   # (argv, cwd, extra_env)
    watched_roots: Callable[[Sandbox], list[str]]
    train_actions: Callable[[Sandbox, int], list[Action]]
    heldout_actions: Callable[[Sandbox, int], list[Action]]
    install_files: Callable[[], list[str]] | None = None   # files whose digest stands for the revision
    description: str = ""
    setup_actions: Callable[[Sandbox, int], list[Action]] | None = None   # calls made before training traffic, not graded
    traffic_profile: str = "scripted"


@dataclass
class Live:
    spec: ServerSpec
    sandbox: Sandbox
    session: ClientSession
    pid: int
    proxy: LoggingProxy
    env: dict
    procmon: ProcEventMonitor | None = None
    net: "NetSandbox | None" = None
    background_net: list = field(default_factory=list)


def fresh_sandbox(name: str, seed: int, base: Path | None = None) -> Sandbox:
    base = base or Path(os.environ.get("VAC_PILOT_SANDBOX", str(HERE.parent / "sandboxes")))
    root = base / f"{name}-{seed}"
    if root.exists():
        shutil.rmtree(root)
    home, tmp, work = root / "home", root / "tmp", root / "work"
    for d in (home, tmp, work):
        d.mkdir(parents=True)
    return Sandbox(root=root, home=home, tmp=tmp, work=work, pidfile=root / "server.pid")


def install_digest(paths: list[str], base: Path | None = None) -> str:
    """Digest of the server's installed implementation files: paths relative to the
    servers directory plus content hashes, so the digest does not depend on where
    the tree was installed."""
    base = base or (HERE.parent / "servers")
    h = hashlib.sha256()
    for p in sorted(paths):
        pp = Path(p)
        if pp.is_dir():
            files = sorted(x for x in pp.rglob("*") if x.is_file() and "__pycache__" not in x.parts)
        else:
            files = [pp]
        for f in files:
            try:
                rel = str(f.relative_to(base))
            except ValueError:
                rel = f.name
            h.update(rel.encode()); h.update(b"\0")
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


# --------------------------------------------------------------------------
# network namespace: private, dead-end, fully recorded
# --------------------------------------------------------------------------

_TCPDUMP_LINE = re.compile(r"^(?P<t>\d+\.\d+) IP6? (?P<src>\S+) > (?P<dst>[^:]+): (?P<rest>.*)$")
_DNS_Q = re.compile(r"\b(?P<qtype>A|AAAA|HTTPS|SRV|TXT|MX|CNAME|PTR|ANY)\? (?P<qname>\S+)")


def _split_hostport(s: str) -> tuple[str, str]:
    if "." in s:
        host, _, port = s.rpartition(".")
        return host, port
    return s, ""


class NetSandbox:
    _counter = 0

    def __init__(self, tag: str, capture_path: Path):
        NetSandbox._counter += 1
        self.n = (os.getpid() + NetSandbox._counter * 7) % 200 + 10        # 10.200.<n>.0/24
        self.ns = f"vac{os.getpid() % 10000}x{NetSandbox._counter}"
        self.veth_h = f"vh{os.getpid() % 10000}x{NetSandbox._counter}"[:15]
        self.veth_s = f"vs{os.getpid() % 10000}x{NetSandbox._counter}"[:15]
        self.host_ip = f"10.200.{self.n}.1"
        self.guest_ip = f"10.200.{self.n}.2"
        self.capture_path = capture_path
        self.tcpdump: subprocess.Popen | None = None
        self._offset = 0
        self.tag = tag

    def _ip(self, *args, check=True):
        return subprocess.run(["ip", *args], check=check, capture_output=True, text=True)

    def up(self):
        self._ip("netns", "add", self.ns)
        self._ip("link", "add", self.veth_h, "type", "veth", "peer", "name", self.veth_s)
        self._ip("link", "set", self.veth_s, "netns", self.ns)
        self._ip("addr", "add", f"{self.host_ip}/24", "dev", self.veth_h)
        self._ip("link", "set", self.veth_h, "up")
        self._ip("netns", "exec", self.ns, "ip", "addr", "add", f"{self.guest_ip}/24", "dev", self.veth_s)
        self._ip("netns", "exec", self.ns, "ip", "link", "set", "lo", "up")
        self._ip("netns", "exec", self.ns, "ip", "link", "set", self.veth_s, "up")
        self._ip("netns", "exec", self.ns, "ip", "route", "add", "default", "via", self.host_ip)
        # name server = the harness side, where nothing listens on 53: every query dies on the veth, recorded
        d = Path("/etc/netns") / self.ns
        d.mkdir(parents=True, exist_ok=True)
        (d / "resolv.conf").write_text(f"nameserver {self.host_ip}\noptions timeout:1 attempts:1\n")
        self.tcpdump = subprocess.Popen(
            ["tcpdump", "-i", self.veth_h, "-l", "-n", "-tt", "-U", "not arp and not icmp6 and not icmp and not igmp"],
            stdout=open(self.capture_path, "a"), stderr=subprocess.DEVNULL)
        time.sleep(0.4)   # tcpdump start-up

    def exec_prefix(self) -> list[str]:
        return ["ip", "netns", "exec", self.ns]

    def drain(self) -> list[dict]:
        """Outbound attempts recorded since the last drain (TCP SYNs, DNS queries, other UDP)."""
        out: list[dict] = []
        if not self.capture_path.exists():
            return out
        with open(self.capture_path) as f:
            f.seek(self._offset)
            data = f.read()
            self._offset = f.tell()
        for line in data.splitlines():
            m = _TCPDUMP_LINE.match(line)
            if not m:
                continue
            src_host, _ = _split_hostport(m["src"])
            if src_host != self.guest_ip and not src_host.startswith("fe80"):
                continue   # only what the server side emits
            dst_host, dst_port = _split_hostport(m["dst"])
            rest = m["rest"]
            if dst_port == "53" and ("?" in rest):
                q = _DNS_Q.search(rest)
                out.append({"t": float(m["t"]), "kind": "dns", "dst": f"{dst_host}:{dst_port}",
                            "qname": (q["qname"].rstrip(".") if q else rest[:60]), "qtype": (q["qtype"] if q else "?")})
            elif rest.startswith("tcp") or "Flags [S]" in rest or rest.startswith("Flags"):
                if "[S]" in rest or "SYN" in rest or rest.startswith("tcp"):
                    out.append({"t": float(m["t"]), "kind": "tcp_syn", "dst": f"{dst_host}:{dst_port}"})
            elif rest.startswith("UDP") or "UDP" in rest:
                out.append({"t": float(m["t"]), "kind": "udp", "dst": f"{dst_host}:{dst_port}"})
        return out

    def down(self):
        if self.tcpdump is not None:
            self.tcpdump.terminate()
            try:
                self.tcpdump.wait(2)
            except subprocess.TimeoutExpired:
                self.tcpdump.kill()
        self._ip("netns", "del", self.ns, check=False)
        self._ip("link", "del", self.veth_h, check=False)
        shutil.rmtree(Path("/etc/netns") / self.ns, ignore_errors=True)


def cleanup_stale_namespaces():
    try:
        out = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    for line in out.splitlines():
        name = line.split()[0] if line.strip() else ""
        if name.startswith("vac"):
            subprocess.run(["ip", "netns", "del", name], capture_output=True)
            shutil.rmtree(Path("/etc/netns") / name, ignore_errors=True)
    out = subprocess.run(["ip", "-o", "link"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) > 1:
            name = parts[1].strip().split("@")[0]
            if name.startswith("vh"):
                subprocess.run(["ip", "link", "del", name], capture_output=True)


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def open_session(spec: ServerSpec, sandbox: Sandbox, isolate: bool = True):
    argv, cwd, extra_env = spec.build_command(sandbox)
    net: NetSandbox | None = None
    if isolate:
        try:
            net = NetSandbox(spec.name, sandbox.root / "net.capture.txt")
            net.up()
        except Exception as exc:   # no CAP_NET_ADMIN, no tcpdump, ...
            with contextlib.suppress(Exception):
                net.down() if net else None
            net = None
            (sandbox.root / "net.isolation.failed").write_text(f"{type(exc).__name__}: {exc}\n")
    proxy = LoggingProxy(host=net.host_ip if net else "127.0.0.1")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(sandbox.home), "TMPDIR": str(sandbox.tmp), "TMP": str(sandbox.tmp), "TEMP": str(sandbox.tmp),
        "XDG_CACHE_HOME": str(sandbox.home / ".cache"), "XDG_CONFIG_HOME": str(sandbox.home / ".config"),
        "XDG_DATA_HOME": str(sandbox.home / ".local/share"),
        "HTTP_PROXY": proxy.url, "HTTPS_PROXY": proxy.url, "ALL_PROXY": proxy.url,
        "http_proxy": proxy.url, "https_proxy": proxy.url, "all_proxy": proxy.url, "NO_PROXY": "",
        "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1", "NODE_OPTIONS": "",
    }
    env.update(extra_env)
    prefix = net.exec_prefix() if net else []
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(PIDWRAP), str(sandbox.pidfile)] + prefix + argv,
                                   env=env, cwd=cwd)
    errlog = open(sandbox.root / "server.stderr.log", "a")
    try:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), 60)
                for _ in range(100):
                    if sandbox.pidfile.exists() and sandbox.pidfile.read_text().strip():
                        break
                    await asyncio.sleep(0.02)
                pid = int(sandbox.pidfile.read_text().strip())
                try:
                    procmon = ProcEventMonitor(pid)
                    procmon.start()
                except OSError:
                    procmon = None
                live = Live(spec=spec, sandbox=sandbox, session=session, pid=pid, proxy=proxy, env=env,
                            procmon=procmon, net=net)
                await asyncio.sleep(0.3)
                live.background_net += [dict(a, phase="startup") for a in (net.drain() if net else [])]
                live.background_net += [dict(a, phase="startup") for a in proxy.drain()]
                try:
                    yield live
                finally:
                    await asyncio.sleep(0.3)
                    live.background_net += [dict(a, phase="shutdown") for a in (net.drain() if net else [])]
                    live.background_net += [dict(a, phase="shutdown") for a in proxy.drain()]
                    if procmon is not None:
                        procmon.close()
    finally:
        proxy.close()
        errlog.close()
        if net is not None:
            net.down()


def _result_text(result) -> str:
    parts = []
    for c in getattr(result, "content", []) or []:
        t = getattr(c, "text", None)
        parts.append(t if t is not None else f"<{type(c).__name__}>")
    return "\n".join(parts)


async def call_observed(live: Live, action: Action, index: int) -> dict:
    roots = live.spec.watched_roots(live.sandbox)
    exclude = (str(live.sandbox.pidfile), str(live.sandbox.root / "server.stderr.log"),
               str(live.sandbox.root / "net.capture.txt"))
    before = snapshot(roots, exclude)
    # anything the server emitted between calls is background, not this call's
    if live.net is not None:
        live.background_net += [dict(a, phase="between_calls", before_index=index) for a in live.net.drain()]
    live.background_net += [dict(a, phase="between_calls", before_index=index) for a in live.proxy.drain()]
    sampler = ProcSampler(live.pid)
    sampler.start()
    if live.procmon is not None:
        live.procmon.begin()
    t0 = time.perf_counter()
    error_text = None
    try:
        result = await asyncio.wait_for(live.session.call_tool(action.tool, action.args), CALL_TIMEOUT)
        is_error = bool(getattr(result, "isError", False))
        text = _result_text(result)
    except Exception as exc:  # transport/protocol failure, not a tool error
        result, is_error, text = None, True, ""
        error_text = f"{type(exc).__name__}: {str(exc)[:300]}"
    wall = time.perf_counter() - t0
    await asyncio.sleep(SETTLE)            # let late children/sockets be sampled
    procs = sampler.stop()
    kernel = live.procmon.end() if live.procmon is not None else None
    after = snapshot(roots, exclude)
    fs = diff(before, after)
    proxied = live.proxy.drain()
    net_attempts = live.net.drain() if live.net is not None else []
    receipt = {
        "index": index, "tool": action.tool, "args": action.args, "note": action.note,
        "is_error": is_error, "transport_error": error_text,
        "response_text": text[:4000], "response_len": len(text),
        "fs": fs,
        "children": (kernel["execs"] if kernel is not None else procs["children"]),
        "children_source": ("kernel_proc_connector" if kernel is not None else "proc_sampling"),
        "forks": (kernel["forks"] if kernel is not None else None),
        "children_sampled": procs["children"],
        "remote_sockets": procs["remote_sockets"],
        "proxy_requests": proxied,
        "net_attempts": net_attempts,
        "net_isolation": ("netns_veth_tcpdump" if live.net is not None else "none"),
        "sampler_samples": procs["samples"],
        "wall_seconds": round(wall, 3),
    }
    receipt["digest"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, default=str).encode()).hexdigest()
    return receipt
