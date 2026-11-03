#!/usr/bin/env bash
# The remaining targets (run after setup_env.sh).
set -euo pipefail
cd "$(dirname "$0")/../servers"
npm install --silent @modelcontextprotocol/server-memory@2.0.1 @modelcontextprotocol/server-everything@2.1.0 \
    @wonderwhy-er/desktop-commander@0.3.1 obsidian-mcp@2.0.1
uv pip install -q --python pyenv/bin/python mcp-server-fetch==2026.10.28 mcp-server-time==2026.10.28
echo "v2 environment ready"
