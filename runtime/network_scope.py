"""Per-invocation network declarations.

A tool's ability to read URLs grants network access only to the host of the call's
own URL; README-documented background hosts form a separate class.  Applied to the
recorded Desktop Commander receipts by `research/network_scope_eval.py`.
"""
from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class NetworkFinding:
    host: str
    status: str  # allowed_call, readme_documented, undeclared, uncertain
    reason: str


def _host_from_url(candidate: Any) -> str | None:
    if not isinstance(candidate, str):
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return parsed.hostname.lower().rstrip(".")


def _matches(host: str, patterns: Sequence[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(fnmatch.fnmatchcase(host, str(p).lower().rstrip("."))
               for p in patterns if p)


def allowed_url_hosts(arguments: Mapping[str, Any], *, field: str = "path",
                      url_flag: str = "isUrl") -> tuple[str, ...]:
    # The flag MUST be present and true; passing a URL-like local path is not enough.
    if arguments.get(url_flag) is not True:
        return ()
    host = _host_from_url(arguments.get(field))
    return (host,) if host else ()


def classify_attempts(*, tool: str, arguments: Mapping[str, Any],
                      names: Sequence[str], readme_hosts: Sequence[str] = ()) -> list[NetworkFinding]:
    """Classify the DNS/target names a call produced."""
    scoped = allowed_url_hosts(arguments) if tool == "read_file" else ()
    findings = []
    for raw in names:
        host = str(raw).lower().rstrip(".")
        if not host:
            findings.append(NetworkFinding("", "uncertain", "endpoint has no observed host"))
        elif _matches(host, scoped):
            findings.append(NetworkFinding(host, "allowed_call", "host matches this call's URL"))
        elif _matches(host, readme_hosts):
            findings.append(NetworkFinding(host, "readme_documented", "documented background host"))
        else:
            findings.append(NetworkFinding(host, "undeclared", "host not granted by this invocation"))
    return findings
