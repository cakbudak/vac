# Note to the maintainers of Desktop Commander

Observed on `@wonderwhy-er/desktop-commander@0.3.1`, started with `node dist/index.js` in a fresh
HOME inside a network namespace with no route to the internet, 30–31 October 2026 on two machines, as part of a
research harness that compares tool descriptions with observed behaviour.  Every observation below is in
the public receipts at https://github.com/cakbudak/vac (one JSON line per tool call; paths below):

1. On every one of 267 tool calls — 219 of them calls of tools that declare no subprocess at all,
   including `get_config`, `list_sessions`, `get_usage_stats` — the server spawned a child process,
   identified by name as `python3 --version` on 263 of them (sometimes twice; on the other 4 the
   child exited before its command line could be read).  `system-info.js: detectPythonInfo()`
   appears to run per call rather than once.  Undocumented; benign, but a controller that counts
   child processes sees it on every call.
2. At start-up, without any call: DNS lookups for `telemetry.desktopcommander.app`,
   `dc-telemetry-proxy-83847352264.europe-west1.run.app`, `desktopcommander.app` (feature flags) and
   `googlechromelabs.github.io` (Chrome-for-Testing download).  During calls: DNS lookups of the
   telemetry hosts during 161 of the 267 calls, 81 of them to the Cloud Run fallback host, including
   local `read_file` calls.  The README documents telemetry and its opt-out; it names no host, and it
   does not mention the feature-flag fetch or the browser download.
3. `config.json` is rewritten on every tool call (267 of 267).  Documented as the configuration
   file's location; the per-call write is not.
4. The served description of `start_process` embeds platform and container-detection text
   ("Running on Linux (Docker)", a Docker-environment warning).  The same installation (identical
   install digest) served two different definitions on the two machines, so clients that pin tool
   descriptions see a changed definition without an update.

None of this is reported as a vulnerability.  It is reported because an agent controller that
relies on tool descriptions and annotations cannot see any of it, and because the package is
among the most installed MCP servers.

**Receipts**

- Child process per call: `real-mcp/results2/desktop_commander/seed-1/receipts_heldout.jsonl`,
  lines 3 (`get_config`), 4 (`list_sessions`) and 22 (`get_usage_stats`), field `children`; the
  same on the second machine under `real-mcp/results2_second_machine/desktop_commander/`.
- Start-up DNS: `real-mcp/results2/desktop_commander/seed-1/summary.json`, `background_net`
  entries with `phase: startup`.
- DNS during a local `read_file`: `receipts_heldout.jsonl` line 31, field `net_attempts`; all 81
  fallback-host calls: `research/NETWORK_SCOPE_RESULTS.md`.
- `config.json` write: `receipts_heldout.jsonl` line 1, field `fs.modified`.
- Served definition: `real-mcp/contracts/desktop_commander.tools.json`; `install_digest` and
  `served_definition_digest` in the `summary.json` of both machines.
