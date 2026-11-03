# Note to the maintainers of Desktop Commander

Observed on `@wonderwhy-er/desktop-commander@0.3.1`, started with `node dist/index.js` in a fresh
HOME inside a network namespace with no route to the internet, 30–31 October 2026 on two machines, as part of a
research harness that compares tool descriptions with observed behaviour (receipts available):

1. On every one of 267 tool calls — 219 of them calls of tools that declare no subprocess at all,
   including `get_config`, `list_sessions`, `get_usage_stats` — the server spawned a child process,
   identified by name as `python3 --version` on 263 of them (sometimes twice; on the other 4 the
   child exited before its command line could be read).  `system-info.js: detectPythonInfo()`
   appears to run per call rather than once.  Undocumented; benign, but a controller that counts
   child processes sees it on every call.
2. At start-up, without any call: DNS lookups for `telemetry.desktopcommander.app`,
   `dc-telemetry-proxy-83847352264.europe-west1.run.app`, `desktopcommander.app` (feature flags) and
   `googlechromelabs.github.io` (Chrome-for-Testing download).  The README documents telemetry and
   its opt-out; it names no host, and it does not mention the feature-flag fetch or the browser
   download, which also creates `~/.claude-server-commander/puppeteer-cache/`.
3. `config.json` is rewritten on every `start_process` call (usage statistics).  Documented as the
   configuration file's location; the per-call write is not.
4. The served description of `start_process` embeds the host name and container detection text,
   so clients that pin tool descriptions see a different definition on each machine.

None of this is reported as a vulnerability.  It is reported because an agent controller that
relies on tool descriptions and annotations cannot see any of it, and because the package is
among the most installed MCP servers.
